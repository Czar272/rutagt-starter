"""Pruebas de los límites geográficos de referencia."""

import pytest

from rutagt.core.geo import GUATEMALA_BOUNDS, METRO_AREA_BOUNDS, contains


@pytest.mark.parametrize(
    ("lon", "lat", "guatemala", "metro"),
    [
        (-90.51, 14.64, True, True),  # Centro histórico, zona 1
        (-90.75, 14.85, True, True),  # Esquina del área metropolitana
        (-91.52, 14.83, True, False),  # Quetzaltenango
        (-90.5, -14.6, False, False),  # Latitud con el signo invertido
        (0.0, 0.0, False, False),
    ],
)
def test_contains(lon: float, lat: float, guatemala: bool, metro: bool) -> None:
    assert contains(GUATEMALA_BOUNDS, lon, lat) is guatemala
    assert contains(METRO_AREA_BOUNDS, lon, lat) is metro


def test_metro_area_is_inside_guatemala() -> None:
    min_lon, min_lat, max_lon, max_lat = METRO_AREA_BOUNDS
    assert contains(GUATEMALA_BOUNDS, min_lon, min_lat)
    assert contains(GUATEMALA_BOUNDS, max_lon, max_lat)
