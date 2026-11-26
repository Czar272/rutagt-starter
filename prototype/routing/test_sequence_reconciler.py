"""Pruebas del reconciliador ordenado con casos conflictivos sintéticos.

Ejecutar desde la raíz del repositorio:

    uv run pytest prototype/routing
"""

from typing import Any

import pytest
from linear_reference import Polyline
from sequence_reconciler import (
    address_score,
    align_in_order,
    reconcile_sequence,
    street_numbers,
)

# Trazado recto de oeste a este, de unos 2,2 km.
LINE = Polyline([[-90.52, 14.60], [-90.50, 14.60]])


def record(fid: int, lon: float, name: str, address: str) -> dict[str, Any]:
    return {
        "geometry": {"type": "Point", "coordinates": [lon, 14.6001]},
        "properties": {"FID": fid, "Nombre_lug": name, "Direccion": address},
    }


def stop(sequence: int, code: str, address: str) -> dict[str, Any]:
    return {"sequence": sequence, "stop_code": code, "address": address, "zone": 7}


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("Calz. San Juan y 8a avenida, Colonia Quinta Samayoa", {("8", "av")}),
        ("Calzada San Juan y 8 avenida zona 7", {("8", "av")}),
        ("Diagonal 24 y 13 calle", {("24", "diagonal"), ("13", "calle")}),
        ("9a calle y 15 avenida", {("9", "calle"), ("15", "av")}),
        ("Anillo Periférico, Colonia El Incienso", set()),
        (None, set()),
    ],
)
def test_street_numbers(address: str | None, expected: set[tuple[str, str]]) -> None:
    assert street_numbers(address) == expected


def test_address_score_distinguishes_street_numbers() -> None:
    official = "Calz. San Juan y 8a avenida, Colonia Quinta Samayoa"

    right = address_score(official, "Calzada San Juan y 8 avenida zona 7")
    wrong = address_score(
        official, "Calzada San Juan y 7a avenida, Colonia Quinta Samayoa"
    )

    assert right > wrong


def test_align_in_order_uses_each_column_once_in_order() -> None:
    scores = [
        [0.9, 0.8, 0.1, 0.0],
        [0.9, 0.2, 0.1, 0.7],
    ]

    assignment = align_in_order(scores)

    assert assignment == [0, 3]


def test_align_in_order_prefers_global_optimum_over_greedy_choice() -> None:
    # Una asignación voraz daría la columna 1 a la primera fila (0,9) y dejaría
    # a la segunda solo la columna 2 (total 0,9); el óptimo es [0, 1] (1,75).
    scores = [
        [0.8, 0.9, 0.0],
        [0.0, 0.95, 0.0],
    ]

    assert align_in_order(scores) == [0, 1]


def test_align_in_order_requires_enough_columns() -> None:
    with pytest.raises(ValueError, match="menos registros"):
        align_in_order([[1.0], [1.0]])


def test_reconcile_handles_shifted_names_and_extra_record() -> None:
    """Reproduce los problemas de la capa municipal en la ruta 801.

    Los nombres de los registros están corridos en +1 respecto del rutero y hay
    un registro adicional que no corresponde a ninguna parada.
    """
    official = [
        stop(1, "094", "Calzada Roosevelt y 4a avenida"),
        stop(2, "095", "Calz. San Juan y 8a avenida"),
        stop(3, "096", "10a avenida y 5a calle"),
    ]
    features = [
        record(90, -90.519, "Parada 947", "Calzada Roosevelt y 4a avenida"),
        record(91, -90.515, "Funerales Reforma", "Calzada San Juan y 7a avenida"),
        record(208, -90.512, "Parada 096", "Calzada San Juan y 8 avenida zona 7"),
        record(93, -90.505, "Parada 097", "10 Avenida y 5a calle"),
    ]

    assignments, unassigned = reconcile_sequence(official, features, LINE)

    assert [item.fid for item in assignments] == [90, 208, 93]
    assert [record["fid"] for record in unassigned] == [91]
    assert [item.name_code_mismatch for item in assignments] == [True, True, True]


def test_reconcile_never_reuses_a_record() -> None:
    official = [
        stop(1, "001", "33 avenida y 26 calle"),
        stop(2, "002", "33 avenida y 26 calle"),
    ]
    features = [
        record(1, -90.515, "Parada 001", "33 avenida y 26 calle"),
        record(2, -90.505, "Parada 002", "33 avenida y 30 calle"),
    ]

    assignments, unassigned = reconcile_sequence(official, features, LINE)

    assert [item.fid for item in assignments] == [1, 2]
    assert unassigned == []


def test_reconcile_orders_records_by_position_not_by_input_order() -> None:
    official = [stop(1, "001", "1a calle"), stop(2, "002", "2a calle")]
    features = [
        record(2, -90.505, "Parada 002", "2a calle"),
        record(1, -90.515, "Parada 001", "1a calle"),
    ]

    assignments, _ = reconcile_sequence(official, features, LINE)

    assert [item.fid for item in assignments] == [1, 2]
    assert assignments[0].position_m < assignments[1].position_m


def test_polyline_projection() -> None:
    projection = LINE.project([-90.51, 14.6001])

    assert projection.position_m == pytest.approx(LINE.length_m / 2, rel=0.01)
    assert projection.offset_m == pytest.approx(11, abs=1)
