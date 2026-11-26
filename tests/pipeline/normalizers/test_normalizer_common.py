"""Pruebas de las funciones de geometría compartidas por los adaptadores."""

from typing import Any

import pytest

from rutagt.pipeline.normalizers.common import (
    chain_segments,
    haversine_m,
    line_length_m,
    line_positions,
)
from rutagt.pipeline.normalizers.models import Position

A: Position = (-90.50, 14.60)
B: Position = (-90.49, 14.60)
C: Position = (-90.48, 14.60)
D: Position = (-90.49, 14.61)


def test_haversine_and_line_length() -> None:
    # Un grado de latitud mide unos 111,2 km.
    assert haversine_m((0.0, 0.0), (0.0, 1.0)) == pytest.approx(111_195, rel=1e-3)
    assert line_length_m([A, B, C]) == pytest.approx(2 * haversine_m(A, B))
    assert line_length_m([A]) == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([[-90.5, 14.6], [-90.4, 14.7, 1500]], [(-90.5, 14.6), (-90.4, 14.7)]),
        ([[-90.5, 14.6]], None),
        ([[-90.5, 14.6], [-90.4, "x"]], None),
        ("no", None),
    ],
)
def test_line_positions(value: Any, expected: list[Position] | None) -> None:
    assert line_positions(value) == expected


def test_chain_keeps_the_original_order_when_continuous() -> None:
    line, order = chain_segments([[A, B], [B, C]]) or ([], [])

    assert line == [A, B, C]
    assert order == [(0, False), (1, False)]


def test_chain_reverses_segments_when_needed() -> None:
    line, order = chain_segments([[A, B], [C, B]]) or ([], [])

    assert line == [A, B, C]
    assert order == [(0, False), (1, True)]


def test_chain_backtracks_through_loops() -> None:
    # Como la Línea 18: lazo en A, A→B, B→A y lazo en B. Seguir el orden
    # original (B→A) dejaría el lazo de B sin recorrer.
    loop_a = [A, D, A]
    loop_b = [B, C, B]

    line, order = chain_segments([loop_a, [A, B], [B, A], loop_b]) or ([], [])

    assert order == [(0, False), (1, False), (3, False), (2, False)]
    assert line == [A, D, A, B, C, B, A]


@pytest.mark.parametrize("segments", [[], [[A, B], [C, D]]])
def test_chain_fails_without_a_continuous_path(
    segments: list[list[Position]],
) -> None:
    assert chain_segments(segments) is None
