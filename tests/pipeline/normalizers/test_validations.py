"""Pruebas de las validaciones geoespaciales de staging (ADR-0034)."""

from typing import Any

import pytest

from rutagt.pipeline.normalizers import validations
from rutagt.pipeline.normalizers.models import (
    Position,
    Severity,
    SourceRef,
    StagedRecord,
    StagedRoute,
    StagedShape,
    StagedStop,
    StagingBatch,
)

SNAPSHOT = "20261126T181403Z"
LINE: tuple[Position, ...] = ((-90.50, 14.60), (-90.49, 14.60), (-90.48, 14.60))


def ref(external_id: str, source_id: str = "muni_paradas") -> SourceRef:
    return SourceRef(source_id=source_id, external_id=external_id, raw={})


def stop(external_id: str, position: Position, *codes: str) -> StagedStop:
    return StagedStop(
        source=ref(external_id),
        name=f"P{external_id}",
        position=position,
        route_codes=codes,
    )


def shape(
    external_id: str,
    route_code: str,
    coordinates: tuple[Position, ...] = LINE,
    variant_code: str | None = None,
    length_m: float = 2152.1,
) -> StagedShape:
    return StagedShape(
        source=ref(external_id, "muni_rutas"),
        route_code=route_code,
        variant_code=variant_code,
        coordinates=coordinates,
        length_m=length_m,
    )


def batch(*records: StagedRecord, source_id: str = "muni_paradas") -> StagingBatch:
    return StagingBatch(source_id=source_id, snapshot_id=SNAPSHOT, records=records)


def codes(issues: list[Any]) -> list[tuple[str, Severity]]:
    return [(issue.code, issue.severity) for issue in issues]


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        ((-90.51, 14.64), []),
        ((-91.52, 14.83), [("fuera_de_cobertura", Severity.WARNING)]),
        ((-90.51, -14.64), [("fuera_de_guatemala", Severity.ERROR)]),
    ],
    ids=["zona-1", "quetzaltenango", "signo-invertido"],
)
def test_stop_coverage(position: Position, expected: list[Any]) -> None:
    assert codes(validations.validate_batch(batch(stop("1", position)))) == expected


def test_shape_coverage_counts_positions() -> None:
    coordinates = ((-90.50, 14.60), (-90.49, 14.60), (0.0, 0.0), (0.1, 0.0))
    issues = validations.validate_batch(batch(shape("1", "1", coordinates)))

    error = next(i for i in issues if i.code == "fuera_de_guatemala")
    assert error.evidence == {"posiciones": 2}


def test_shape_jumps_and_short_shapes() -> None:
    jumpy = ((-90.50, 14.60), (-90.50, 14.62), (-90.50, 14.621))
    short = ((-90.50, 14.60), (-90.50, 14.601))

    issues = validations.validate_batch(
        batch(shape("1", "1", jumpy), shape("2", "2", short, length_m=111.2))
    )

    assert codes(issues) == [
        ("salto_en_trazado", Severity.WARNING),
        ("trazado_corto", Severity.WARNING),
    ]
    assert issues[0].evidence == {"saltos_m": [2224]}


def test_routes_are_not_validated() -> None:
    route = StagedRoute(source=ref("1"), route_code="1", short_name="1")

    assert validations.validate_batch(batch(route)) == []


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        ((-90.49, 14.6001), []),
        ((-90.49, 14.601), [("parada_lejos_de_ruta", Severity.WARNING)]),
        ((-90.49, 14.61), [("parada_lejos_de_ruta", Severity.ERROR)]),
    ],
    ids=["11-m", "111-m", "1-km"],
)
def test_stop_distance_to_its_route(position: Position, expected: list[Any]) -> None:
    issues = validations.validate_stops_against_shapes(
        batch(stop("1", position, "801")),
        batch(shape("9", "801"), source_id="muni_rutas"),
    )

    assert codes(issues) == expected


def test_stops_match_variant_codes_and_report_missing_routes() -> None:
    stops = batch(
        stop("1", (-90.49, 14.60), "12001"),
        stop("2", (-90.49, 14.60), "99"),
        stop("3", (-90.49, 14.60), "99"),
        StagedRoute(source=ref("4"), route_code="99", short_name="99"),
    )
    shapes = batch(
        shape("9", "12", variant_code="12001"),
        StagedRoute(source=ref("9", "muni_rutas"), route_code="12", short_name="12"),
        source_id="muni_rutas",
    )

    (issue,) = validations.validate_stops_against_shapes(stops, shapes)

    assert (issue.code, issue.severity) == ("ruta_sin_trazado", Severity.WARNING)
    assert issue.evidence == {"route_code": "99", "external_ids": ["2", "3"]}


def test_shape_key() -> None:
    assert validations.shape_key(shape("1", "12", variant_code="12001")) == "12001"
    assert validations.shape_key(shape("1", "801")) == "801"
