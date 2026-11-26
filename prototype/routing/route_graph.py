"""Grafo dirigido experimental de la ruta 801 (RGT-131).

Modela la ruta como una secuencia dirigida de paradas sobre un circuito:

- nodos: las paradas oficiales con su ubicación y sentido;
- aristas de viaje: de cada parada a la siguiente, con la distancia medida
  sobre el trazado oficial y el tiempo estimado como rango;
- arista de cierre: de la última parada a la primera, porque el trazado es
  un circuito cerrado.

El sentido (`direction_id`) sigue el modelo ruta + variante + sentido
(ADR-0008): 0 desde la parada de origen hasta la terminal y 1 desde la
terminal hasta el regreso.

El rutero no publica tiempos de recorrido, por lo que el tiempo se estima con
un rango de velocidad comercial y un tiempo de detención supuestos; ambos se
declaran en los metadatos con calidad `unverified` (ADR-0024).

Uso, desde la raíz del repositorio:

    uv run python prototype/routing/route_graph.py
"""

import heapq
import itertools
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
ENRICHED_FILE = OUTPUT_DIR / "route_801_enriched.geojson"
GRAPH_FILE = OUTPUT_DIR / "route_801_graph.json"

# Parada terminal según el rutero oficial («Terminal, 4a avenida y 4a calle»).
TERMINAL_STOP = "087"
# Supuestos de operación, sin fuente oficial (a solicitar a la Municipalidad).
SPEED_KMH_RANGE = (12.0, 18.0)
DWELL_SECONDS = 20


@dataclass(frozen=True)
class Edge:
    origin: str
    destination: str
    kind: str
    direction_id: int
    distance_m: int
    time_min: tuple[float, float]
    quality: str


@dataclass
class RouteGraph:
    nodes: dict[str, dict[str, Any]]
    edges: list[Edge]
    adjacency: dict[str, list[Edge]] = field(init=False)

    def __post_init__(self) -> None:
        self.adjacency = {code: [] for code in self.nodes}
        for edge in self.edges:
            self.adjacency[edge.origin].append(edge)

    def shortest_path(self, origin: str, destination: str) -> dict[str, Any] | None:
        """Recorrido más corto en distancia entre dos paradas (Dijkstra).

        Devuelve las paradas visitadas, la distancia y el rango de tiempo, o
        None si el destino no es alcanzable.
        """
        if origin not in self.nodes or destination not in self.nodes:
            raise KeyError("Parada inexistente en el grafo")
        best = {origin: 0}
        previous: dict[str, Edge] = {}
        queue = [(0, origin)]
        while queue:
            distance, code = heapq.heappop(queue)
            if code == destination:
                break
            if distance > best.get(code, sys.maxsize):
                continue
            for edge in self.adjacency[code]:
                candidate = distance + edge.distance_m
                if candidate < best.get(edge.destination, sys.maxsize):
                    best[edge.destination] = candidate
                    previous[edge.destination] = edge
                    heapq.heappush(queue, (candidate, edge.destination))
        if destination not in best:
            return None

        path_edges: list[Edge] = []
        code = destination
        while code != origin:
            edge = previous[code]
            path_edges.append(edge)
            code = edge.origin
        path_edges.reverse()
        return {
            "origin": origin,
            "destination": destination,
            "stops": [origin, *(edge.destination for edge in path_edges)],
            "distance_m": best[destination],
            "time_min": (
                round(sum(edge.time_min[0] for edge in path_edges), 1),
                round(sum(edge.time_min[1] for edge in path_edges), 1),
            ),
            "directions": sorted({edge.direction_id for edge in path_edges}),
        }


def travel_time_range(distance_m: float) -> tuple[float, float]:
    """Rango de minutos para recorrer una distancia y detenerse en la parada."""
    slow, fast = SPEED_KMH_RANGE
    dwell = DWELL_SECONDS / 60
    return (
        round(distance_m / (fast * 1000 / 60) + dwell, 1),
        round(distance_m / (slow * 1000 / 60) + dwell, 1),
    )


def build_graph(enriched: dict[str, Any], terminal: str = TERMINAL_STOP) -> RouteGraph:
    """Construye el grafo dirigido a partir del GeoJSON enriquecido (RGT-129)."""
    stops = sorted(
        (f for f in enriched["features"] if f["properties"]["feature_type"] == "stop"),
        key=lambda feature: feature["properties"]["sequence"],
    )
    shape = next(
        f for f in enriched["features"] if f["properties"]["feature_type"] == "shape"
    )
    codes = [stop["properties"]["stop_code"] for stop in stops]
    if terminal not in codes:
        raise ValueError(f"La terminal #{terminal} no está en la secuencia")
    terminal_index = codes.index(terminal)

    nodes = {}
    for index, stop in enumerate(stops):
        properties = stop["properties"]
        nodes[properties["stop_code"]] = {
            "sequence": properties["sequence"],
            "direction_id": 0 if index <= terminal_index else 1,
            "coordinates": stop["geometry"]["coordinates"],
            "position_m": properties["position_m"],
            "official_address": properties["official_address"],
            "location_quality": properties["quality"]["location"],
            "is_terminal": properties["stop_code"] == terminal,
        }

    def edge_quality(origin: str, destination: str) -> str:
        qualities = {
            nodes[origin]["location_quality"],
            nodes[destination]["location_quality"],
        }
        return "probable" if qualities == {"probable"} else "unverified"

    edges = []
    for origin, destination in itertools.pairwise(codes):
        distance = nodes[destination]["position_m"] - nodes[origin]["position_m"]
        edges.append(
            Edge(
                origin=origin,
                destination=destination,
                kind="ride",
                # El tramo pertenece al sentido de la parada a la que llega: el
                # que sale de la terminal ya es parte del regreso.
                direction_id=nodes[destination]["direction_id"],
                distance_m=round(distance),
                time_min=travel_time_range(distance),
                quality=edge_quality(origin, destination),
            )
        )
    closure = (
        shape["properties"]["length_m"]
        - nodes[codes[-1]]["position_m"]
        + nodes[codes[0]]["position_m"]
    )
    edges.append(
        Edge(
            origin=codes[-1],
            destination=codes[0],
            kind="circuit_closure",
            direction_id=1,
            distance_m=round(closure),
            time_min=travel_time_range(closure),
            quality=edge_quality(codes[-1], codes[0]),
        )
    )
    return RouteGraph(nodes=nodes, edges=edges)


def graph_document(graph: RouteGraph, enriched: dict[str, Any]) -> dict[str, Any]:
    """Representación serializable del grafo con sus supuestos."""
    total = sum(edge.distance_m for edge in graph.edges)
    return {
        "route_code": enriched["metadata"]["route_code"],
        "route_name": enriched["metadata"]["route_name"],
        "experimental": True,
        "ticket": "RGT-131",
        "assumptions": {
            "speed_kmh_range": list(SPEED_KMH_RANGE),
            "dwell_seconds": DWELL_SECONDS,
            "terminal_stop": TERMINAL_STOP,
            "quality": "unverified",
            "note": "El rutero no publica tiempos de recorrido; los tiempos son "
            "estimaciones a reemplazar por datos operativos oficiales.",
        },
        "summary": {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "circuit_length_m": total,
            "circuit_time_min": [
                round(sum(edge.time_min[0] for edge in graph.edges)),
                round(sum(edge.time_min[1] for edge in graph.edges)),
            ],
            "direction_0_stops": sum(
                n["direction_id"] == 0 for n in graph.nodes.values()
            ),
            "direction_1_stops": sum(
                n["direction_id"] == 1 for n in graph.nodes.values()
            ),
        },
        "nodes": graph.nodes,
        "edges": [
            {**edge.__dict__, "time_min": list(edge.time_min)} for edge in graph.edges
        ],
    }


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    enriched = json.loads(ENRICHED_FILE.read_text(encoding="utf-8"))
    graph = build_graph(enriched)
    document = graph_document(graph, enriched)
    GRAPH_FILE.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(document["summary"], ensure_ascii=False))
    print(f"Grafo: {GRAPH_FILE}")


if __name__ == "__main__":
    main()
