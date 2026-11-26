"""Consultas origen–destino sobre la ruta 801 (RGT-132).

Planifica viajes entre dos puntos cualesquiera combinando caminata de acceso,
espera, viaje en bus sobre el grafo dirigido (RGT-131) y caminata final, y
ejecuta un conjunto de consultas de ejemplo para evaluar la calidad de los
itinerarios.

Supuestos sin fuente oficial, declarados con calidad `unverified`:

- caminata: distancia en línea recta × factor de rodeo, a 4–5 km/h (no hay
  todavía red peatonal de OpenStreetMap);
- espera: la mitad de un intervalo supuesto de 10–20 min entre buses (no hay
  frecuencias publicadas);
- tiempos de viaje: los del grafo (velocidad comercial supuesta).

Los tiempos se presentan como rangos (ADR-0024) y las alternativas se ordenan
por el peor caso del rango.

Uso, desde la raíz del repositorio:

    uv run python prototype/routing/plan_trip.py
"""

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from route_graph import ENRICHED_FILE, RouteGraph, build_graph

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
RESULTS_FILE = OUTPUT_DIR / "route_801_od_queries.json"
REPORT_FILE = OUTPUT_DIR / "route_801_od_queries.md"

EARTH_RADIUS_M = 6_371_000
WALK_DETOUR_FACTOR = 1.3
WALK_SPEED_KMH_RANGE = (4.0, 5.0)
MAX_WALK_M = 1_000
HEADWAY_MIN_RANGE = (10.0, 20.0)
MAX_ALTERNATIVES = 3
HEADSIGNS = {0: "Terminal 4a av. y 4a calle, zona 9", 1: "Parque Los Pinos, zona 7"}


def haversine_m(a: list[float], b: list[float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def walk(
    origin: list[float], destination: list[float]
) -> tuple[int, tuple[float, float]]:
    """Distancia estimada a pie y su rango de minutos."""
    distance = haversine_m(origin, destination) * WALK_DETOUR_FACTOR
    slow, fast = WALK_SPEED_KMH_RANGE
    return round(distance), (
        round(distance / (fast * 1000 / 60), 1),
        round(distance / (slow * 1000 / 60), 1),
    )


def wait_time() -> tuple[float, float]:
    low, high = HEADWAY_MIN_RANGE
    return (low / 2, high / 2)


def add(*ranges: tuple[float, float]) -> tuple[float, float]:
    return (round(sum(r[0] for r in ranges), 1), round(sum(r[1] for r in ranges), 1))


@dataclass(frozen=True)
class Itinerary:
    kind: str
    total_min: tuple[float, float]
    walk_m: int
    steps: list[str]
    board: str | None = None
    alight: str | None = None
    stops_ridden: int = 0
    ride_m: int = 0
    data_quality: str = "unverified"
    unverified_stops: tuple[str, ...] = ()


def nearby_stops(graph: RouteGraph, point: list[float]) -> list[tuple[str, int]]:
    """Paradas a una caminata estimada no mayor que el máximo, ordenadas."""
    found = []
    for code, node in graph.nodes.items():
        distance, _ = walk(point, node["coordinates"])
        if distance <= MAX_WALK_M:
            found.append((code, distance))
    return sorted(found, key=lambda item: item[1])


def describe_minutes(minutes: tuple[float, float]) -> str:
    low, high = round(minutes[0]), round(minutes[1])
    return f"{low} min" if low == high else f"{low}–{high} min"


def bus_itinerary(
    graph: RouteGraph,
    origin: list[float],
    destination: list[float],
    board: str,
    alight: str,
) -> Itinerary | None:
    path = graph.shortest_path(board, alight)
    if path is None or board == alight:
        return None
    access_m, access_min = walk(origin, graph.nodes[board]["coordinates"])
    egress_m, egress_min = walk(graph.nodes[alight]["coordinates"], destination)
    waiting = wait_time()
    total = add(access_min, waiting, tuple(path["time_min"]), egress_min)
    first_direction = graph.nodes[path["stops"][1]]["direction_id"]
    # Solo importa la ubicación de las paradas donde la persona sube y baja.
    unverified = tuple(
        code
        for code in (board, alight)
        if graph.nodes[code]["location_quality"] != "probable"
    )
    steps = [
        f"Camina unos {access_m} m ({describe_minutes(access_min)}) hasta la parada "
        f"#{board}: {graph.nodes[board]['official_address']}.",
        f"Toma la ruta 801 con dirección a {HEADSIGNS[first_direction]}; "
        f"pasa aproximadamente cada {describe_minutes(HEADWAY_MIN_RANGE)}.",
        f"Viaja {len(path['stops']) - 1} paradas "
        f"({describe_minutes(path['time_min'])}) y bájate en la parada "
        f"#{alight}: {graph.nodes[alight]['official_address']}.",
        f"Camina unos {egress_m} m ({describe_minutes(egress_min)}) hasta tu destino.",
    ]
    if len(path["directions"]) > 1:
        steps.insert(
            2,
            "El bus pasa por la terminal o el extremo del circuito sin que debas "
            "bajarte.",
        )
    return Itinerary(
        kind="bus",
        total_min=total,
        walk_m=access_m + egress_m,
        steps=steps,
        board=board,
        alight=alight,
        stops_ridden=len(path["stops"]) - 1,
        ride_m=path["distance_m"],
        data_quality="unverified" if unverified else "probable",
        unverified_stops=unverified,
    )


def plan(
    graph: RouteGraph, origin: list[float], destination: list[float]
) -> list[Itinerary]:
    """Alternativas ordenadas por el peor caso del tiempo total."""
    options: list[Itinerary] = []
    walk_m, walk_min = walk(origin, destination)
    if walk_m <= 2 * MAX_WALK_M:
        options.append(
            Itinerary(
                kind="walk",
                total_min=walk_min,
                walk_m=walk_m,
                steps=[f"Camina unos {walk_m} m ({describe_minutes(walk_min)})."],
            )
        )
    for board, _ in nearby_stops(graph, origin):
        for alight, _ in nearby_stops(graph, destination):
            itinerary = bus_itinerary(graph, origin, destination, board, alight)
            if itinerary is not None:
                options.append(itinerary)

    options.sort(key=lambda option: (option.total_min[1], option.walk_m))
    unique: list[Itinerary] = []
    for option in options:
        if option.kind == "bus" and any(
            other.kind == "bus" and other.alight == option.alight for other in unique
        ):
            continue
        unique.append(option)
    return unique[:MAX_ALTERNATIVES]


# Consultas de ejemplo dentro del área piloto. Cada extremo se define como un
# desplazamiento desde la ubicación de una parada real, para no depender de
# coordenadas de lugares escritas a mano.
SAMPLE_QUERIES: list[dict[str, Any]] = [
    {
        "id": "Q1",
        "description": "Cerca de Parque Kaminaljuyú (#075) → cerca de Parque de la "
        "Industria (#086)",
        "origin": {"near_stop": "075", "north_m": 150, "east_m": 0},
        "destination": {"near_stop": "086", "north_m": 0, "east_m": 200},
        "purpose": "Viaje largo en el sentido 0, hacia la terminal",
    },
    {
        "id": "Q2",
        "description": "Cerca de la terminal (#087) → Colonia Bethania (#106)",
        "origin": {"near_stop": "087", "north_m": -100, "east_m": 100},
        "destination": {"near_stop": "106", "north_m": 100, "east_m": 0},
        "purpose": "Viaje en el sentido 1, de regreso",
    },
    {
        "id": "Q3",
        "description": "Ciudad de Plata, lado del regreso (#101) → Colonia Kjell "
        "Laugerud (#069)",
        "origin": {"near_stop": "101", "north_m": 0, "east_m": 30},
        "destination": {"near_stop": "069", "north_m": 80, "east_m": 0},
        "purpose": "En la misma esquina hay paradas de ida (#074) y de regreso "
        "(#101): el planificador debe abordar en el sentido correcto",
    },
    {
        "id": "Q4",
        "description": "Trayecto corto en Colonia Bethania (#106 → #105)",
        "origin": {"near_stop": "106", "north_m": 50, "east_m": 0},
        "destination": {"near_stop": "105", "north_m": -50, "east_m": 0},
        "purpose": "Caminar debería ser mejor que tomar el bus",
    },
    {
        "id": "Q5",
        "description": "Punto a 2 km al este de la terminal (#087) → Parque Los Pinos "
        "(#063)",
        "origin": {"near_stop": "087", "north_m": 0, "east_m": 2000},
        "destination": {"near_stop": "063", "north_m": 100, "east_m": 0},
        "purpose": "Fuera de la cobertura de la ruta: no debería haber itinerario",
    },
]


def offset(point: list[float], north_m: float, east_m: float) -> list[float]:
    """Desplaza una coordenada [lon, lat] una distancia en metros."""
    lat = point[1] + north_m / 110_540
    lon = point[0] + east_m / (111_320 * math.cos(math.radians(point[1])))
    return [round(lon, 6), round(lat, 6)]


def resolve(graph: RouteGraph, place: dict[str, Any]) -> list[float]:
    return offset(
        graph.nodes[place["near_stop"]]["coordinates"],
        place["north_m"],
        place["east_m"],
    )


LIMITATIONS = [
    "Una sola ruta (801): no hay transbordos con otras rutas de TuBus ni con "
    "Transmetro.",
    "Caminata estimada en línea recta con factor de rodeo; no considera la red "
    "peatonal, pasarelas ni cruces (requiere OpenStreetMap).",
    "Sin frecuencias ni horarios oficiales: la espera es un supuesto y no se "
    "consideran las ventanas de servicio (5:30–19:00 de lunes a sábado).",
    "Tiempos de viaje estimados con una velocidad comercial supuesta; no "
    "reflejan tráfico ni variación por hora del día.",
    "Ubicaciones de paradas tomadas de la capa municipal sin validación en "
    "campo: 14 de 47 tienen la ubicación no verificada y 23 alguna "
    "discrepancia con el rutero.",
    "Sin tarifas ni medios de pago estructurados.",
]


def evaluate(query: dict[str, Any], options: list[Itinerary]) -> list[str]:
    """Observaciones de calidad sobre el resultado de una consulta."""
    notes = []
    best = options[0] if options else None
    if best is None:
        notes.append("Sin itinerario: ninguna parada a una caminata razonable.")
    elif best.kind == "walk":
        notes.append("La mejor opción es caminar.")
    unverified = sorted(
        {code for option in options for code in option.unverified_stops}
    )
    if unverified:
        notes.append(
            "Paradas de abordaje o descenso con ubicación no verificada: "
            + ", ".join(f"#{code}" for code in unverified)
            + "; requieren validación en campo."
        )
    if options and all(option.kind == "walk" for option in options):
        notes.append(
            "Sin alternativa en bus dentro de la distancia máxima de caminata."
        )
    return notes


def run_queries(graph: RouteGraph) -> list[dict[str, Any]]:
    results = []
    for query in SAMPLE_QUERIES:
        origin, destination = (
            resolve(graph, query["origin"]),
            resolve(graph, query["destination"]),
        )
        options = plan(graph, origin, destination)
        results.append(
            {
                **query,
                "origin_coordinates": origin,
                "destination_coordinates": destination,
                "alternatives": [
                    {**option.__dict__, "total_min": list(option.total_min)}
                    for option in options
                ],
                "evaluation": evaluate(query, options),
            }
        )
    return results


def render_markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Consultas origen–destino — ruta 801",
        "",
        "Supuestos (calidad `unverified`): caminata en línea recta × "
        f"{str(WALK_DETOUR_FACTOR).replace('.', ',')} a {WALK_SPEED_KMH_RANGE[0]:g}–"
        f"{WALK_SPEED_KMH_RANGE[1]:g} km/h, caminata máxima {MAX_WALK_M} m por "
        f"extremo, intervalo entre buses {HEADWAY_MIN_RANGE[0]:g}–"
        f"{HEADWAY_MIN_RANGE[1]:g} min y tiempos de viaje del grafo (RGT-131). "
        "Alternativas ordenadas por el peor caso del rango de tiempo.",
        "",
        "## Resumen",
        "",
        "| Consulta | Mejor opción | Tiempo | A pie | Resultado esperado |",
        "| - | - | - | - | - |",
    ]
    for result in results:
        best = result["alternatives"][0] if result["alternatives"] else None
        if best is None:
            option = "Sin itinerario"
            minutes = walked = "—"
        else:
            option = (
                "Caminar"
                if best["kind"] == "walk"
                else f"Ruta 801 #{best['board']} → #{best['alight']}"
            )
            minutes = describe_minutes(tuple(best["total_min"]))
            walked = f"{best['walk_m']} m"
        lines.append(
            f"| {result['id']} | {option} | {minutes} | {walked} | "
            f"{result['purpose']} |"
        )
    lines += ["", "## Limitaciones", ""]
    lines += [f"- {item}" for item in LIMITATIONS]
    lines.append("")
    for result in results:
        lines += [
            f"## {result['id']}. {result['description']}",
            "",
            f"_Propósito:_ {result['purpose']}",
            "",
        ]
        if not result["alternatives"]:
            lines += ["Sin alternativas.", ""]
        for number, option in enumerate(result["alternatives"], start=1):
            label = (
                "Caminar"
                if option["kind"] == "walk"
                else (f"Ruta 801: #{option['board']} → #{option['alight']}")
            )
            lines += [
                f"**Alternativa {number} — {label}** · "
                f"{describe_minutes(tuple(option['total_min']))} · "
                f"{option['walk_m']} m a pie",
                "",
            ]
            lines += [
                f"{index}. {step}" for index, step in enumerate(option["steps"], 1)
            ]
            lines.append("")
        if result["evaluation"]:
            lines += ["**Evaluación:**", ""]
            lines += [f"- {note}" for note in result["evaluation"]]
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    graph = build_graph(json.loads(ENRICHED_FILE.read_text(encoding="utf-8")))
    results = run_queries(graph)
    RESULTS_FILE.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    REPORT_FILE.write_text(render_markdown(results), encoding="utf-8", newline="\n")
    for result in results:
        best = result["alternatives"][0] if result["alternatives"] else None
        summary = (
            "sin itinerario"
            if best is None
            else f"{best['kind']} {best.get('board') or ''}→{best.get('alight') or ''} "
            f"{best['total_min']} min, {best['walk_m']} m a pie"
        )
        print(f"{result['id']}: {summary}")
    print(f"Reporte: {REPORT_FILE}")


if __name__ == "__main__":
    main()
