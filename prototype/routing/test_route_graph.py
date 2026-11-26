"""Pruebas del grafo dirigido con un circuito sintético."""

from typing import Any

import pytest
from route_graph import build_graph, graph_document, travel_time_range


def stop(sequence: int, code: str, position_m: int, quality: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-90.5 + sequence / 1000, 14.6]},
        "properties": {
            "feature_type": "stop",
            "sequence": sequence,
            "stop_code": code,
            "position_m": position_m,
            "official_address": f"Dirección {code}",
            "quality": {"location": quality},
        },
    }


# Circuito de 4 km: A (inicio) → B → C (terminal) → D → regreso a A.
ENRICHED: dict[str, Any] = {
    "metadata": {"route_code": "999", "route_name": "Circuito de prueba"},
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": []},
            "properties": {"feature_type": "shape", "length_m": 4000},
        },
        stop(1, "A", 100, "probable"),
        stop(2, "B", 1100, "probable"),
        stop(3, "C", 2100, "unverified"),
        stop(4, "D", 3100, "probable"),
    ],
}


@pytest.fixture
def graph() -> Any:
    return build_graph(ENRICHED, terminal="C")


def test_builds_one_edge_per_stop_including_circuit_closure(graph: Any) -> None:
    edges = [(e.origin, e.destination, e.kind, e.distance_m) for e in graph.edges]

    assert edges == [
        ("A", "B", "ride", 1000),
        ("B", "C", "ride", 1000),
        ("C", "D", "ride", 1000),
        ("D", "A", "circuit_closure", 1000),
    ]


def test_directions_split_at_terminal(graph: Any) -> None:
    assert [graph.nodes[code]["direction_id"] for code in "ABCD"] == [0, 0, 0, 1]
    assert graph.nodes["C"]["is_terminal"] is True
    assert [edge.direction_id for edge in graph.edges] == [0, 0, 1, 1]


def test_edge_quality_requires_both_locations_probable(graph: Any) -> None:
    assert [edge.quality for edge in graph.edges] == [
        "probable",
        "unverified",
        "unverified",
        "probable",
    ]


def test_travel_time_is_a_range_including_dwell() -> None:
    fast, slow = travel_time_range(1000)

    assert fast == pytest.approx(1000 / (18000 / 60) + 1 / 3, abs=0.1)
    assert slow == pytest.approx(1000 / (12000 / 60) + 1 / 3, abs=0.1)
    assert fast < slow


def test_shortest_path_follows_direction_of_travel(graph: Any) -> None:
    forward = graph.shortest_path("A", "C")
    around = graph.shortest_path("C", "B")

    assert forward["stops"] == ["A", "B", "C"]
    assert forward["distance_m"] == 2000
    assert forward["directions"] == [0]
    # De C a B no se puede ir hacia atrás: hay que completar el circuito.
    assert around["stops"] == ["C", "D", "A", "B"]
    assert around["distance_m"] == 3000
    assert around["time_min"][0] < around["time_min"][1]


def test_shortest_path_rejects_unknown_stops(graph: Any) -> None:
    with pytest.raises(KeyError):
        graph.shortest_path("A", "Z")


def test_unknown_terminal_is_rejected() -> None:
    with pytest.raises(ValueError, match="terminal"):
        build_graph(ENRICHED, terminal="Z")


def test_graph_document_declares_assumptions(graph: Any) -> None:
    document = graph_document(graph, ENRICHED)

    assert document["summary"]["circuit_length_m"] == 4000
    assert document["summary"]["nodes"] == 4
    assert document["assumptions"]["quality"] == "unverified"
    assert document["experimental"] is True
