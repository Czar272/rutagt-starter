"""Pruebas del planificador origen–destino con un circuito sintético."""

from typing import Any

import pytest
from plan_trip import offset, plan, walk
from route_graph import build_graph

# Circuito rectangular: ida hacia el este por el sur (A → B → C, terminal) y
# regreso hacia el oeste por el norte (D → E). A y E están en la misma
# esquina, en lados opuestos de la calle.
BASE = [-90.53, 14.63]
COORDINATES = {
    "A": offset(BASE, 0, 0),
    "B": offset(BASE, 0, 1500),
    "C": offset(BASE, 0, 3000),
    "D": offset(BASE, 40, 1500),
    "E": offset(BASE, 40, 0),
}


def stop(sequence: int, code: str, position_m: int, quality: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": COORDINATES[code]},
        "properties": {
            "feature_type": "stop",
            "sequence": sequence,
            "stop_code": code,
            "position_m": position_m,
            "official_address": f"Dirección {code}",
            "quality": {"location": quality},
        },
    }


ENRICHED = {
    "metadata": {"route_code": "999", "route_name": "Circuito de prueba"},
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": []},
            "properties": {"feature_type": "shape", "length_m": 6080},
        },
        stop(1, "A", 0, "probable"),
        stop(2, "B", 1500, "probable"),
        stop(3, "C", 3000, "unverified"),
        stop(4, "D", 4540, "probable"),
        stop(5, "E", 6040, "probable"),
    ],
}


@pytest.fixture
def graph() -> Any:
    return build_graph(ENRICHED, terminal="C")


def test_walk_applies_detour_factor() -> None:
    distance, minutes = walk(BASE, offset(BASE, 0, 1000))

    assert distance == pytest.approx(1300, abs=5)
    assert minutes[0] < minutes[1]


def test_long_trip_uses_the_bus_in_the_direction_of_travel(graph: Any) -> None:
    origin = offset(COORDINATES["A"], -100, 0)
    destination = offset(COORDINATES["C"], -100, 0)

    best = plan(graph, origin, destination)[0]

    assert best.kind == "bus"
    assert (best.board, best.alight) == ("A", "C")
    assert best.unverified_stops == ("C",)
    assert best.data_quality == "unverified"


def test_boards_on_the_correct_side_of_the_street(graph: Any) -> None:
    # B (ida) y D (regreso) están enfrentadas a mitad del recorrido. Desde el
    # lado de D hacia la terminal C hay que cruzar y abordar en B, aunque D esté
    # más cerca: desde D el bus da toda la vuelta al circuito.
    origin = offset(COORDINATES["D"], 20, 0)
    destination = offset(COORDINATES["C"], -60, 0)

    best = plan(graph, origin, destination)[0]

    assert (best.board, best.alight) == ("B", "C")


def test_short_trip_prefers_walking(graph: Any) -> None:
    origin = offset(COORDINATES["A"], 0, 100)
    destination = offset(COORDINATES["A"], 0, 400)

    assert plan(graph, origin, destination)[0].kind == "walk"


def test_no_itinerary_far_from_the_route(graph: Any) -> None:
    origin = offset(BASE, -5000, 0)
    destination = offset(COORDINATES["C"], -100, 0)

    assert plan(graph, origin, destination) == []


def test_alternatives_are_sorted_by_worst_case_time(graph: Any) -> None:
    origin = offset(COORDINATES["A"], -100, 0)
    destination = offset(COORDINATES["C"], -100, 0)

    options = plan(graph, origin, destination)

    worst_cases = [option.total_min[1] for option in options]
    assert worst_cases == sorted(worst_cases)
    assert len(options) <= 3
