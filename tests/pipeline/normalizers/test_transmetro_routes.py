"""Pruebas del adaptador de rutas de Transmetro."""

from typing import Any

import pytest

from rutagt.pipeline.normalizers import base, transmetro_routes
from rutagt.pipeline.normalizers.models import Severity, StagedRoute, StagedShape

SNAPSHOT = "20261126T181403Z"
LINE = [[-90.50, 14.60], [-90.49, 14.60], [-90.48, 14.60]]


def feature(fid: Any, name: Any, code: Any, geometry: Any = None) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": geometry
        if geometry is not None
        else {"type": "LineString", "coordinates": LINE},
        "properties": {
            "FID": fid,
            "Nombre": name,
            "Codigoruta": code,
            "Shape__Length": 2230.0,
        },
    }


def adapt(*features: dict[str, Any], content: Any = None) -> Any:
    raw = base.RawInput(
        source_id=transmetro_routes.SOURCE_ID,
        snapshot_id=SNAPSHOT,
        content=content
        if content is not None
        else {"type": "FeatureCollection", "features": list(features)},
        provenance={},
    )
    return transmetro_routes.adapt(raw)


def codes(batch: Any) -> list[str]:
    return [issue.code for issue in batch.issues]


def test_is_registered() -> None:
    assert base.get_adapter(transmetro_routes.SOURCE_ID) is transmetro_routes.adapt


def test_maps_a_record_to_route_and_shape() -> None:
    batch = adapt(feature(10, "Línea 12 (Directo Amate)", 12001))

    route, shape = batch.records
    assert isinstance(route, StagedRoute)
    assert isinstance(shape, StagedShape)
    assert (route.route_code, route.variant_code, route.short_name) == (
        "12",
        "12001",
        "12",
    )
    assert route.long_name == "Línea 12 (Directo Amate)"
    assert (shape.route_code, shape.variant_code) == ("12", "12001")
    assert shape.coordinates == ((-90.50, 14.60), (-90.49, 14.60), (-90.48, 14.60))
    # Longitud geodésica, no `Shape__Length` (Web Mercator).
    assert shape.length_m == pytest.approx(2152.1, abs=0.1)
    assert route.source.raw["Shape__Length"] == 2230.0
    assert batch.issues == ()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Línea 13 Extención", "Línea 13 Extensión"),
        (
            "Línea 18 Expres (Directo San Rafael)",
            "Línea 18 Exprés (Directo San Rafael)",
        ),
        ("Línea 18 Expreso", "Línea 18 Expreso"),
    ],
)
def test_correct_spelling(name: str, expected: str) -> None:
    assert transmetro_routes.correct_spelling(name) == expected


def test_reports_corrected_names() -> None:
    batch = adapt(feature(6, "Línea 13 Extención", 13001))

    assert batch.records[0].long_name == "Línea 13 Extensión"
    (issue,) = batch.issues
    assert (issue.code, issue.severity) == ("nombre_corregido", Severity.INFO)
    assert issue.evidence["original"] == "Línea 13 Extención"


def test_joins_multilinestrings_and_records_the_order() -> None:
    geometry = {
        "type": "MultiLineString",
        "coordinates": [LINE[:2], [LINE[2], LINE[1]]],
    }

    batch = adapt(feature(7, "Línea 18", 18000, geometry))

    shape = batch.records[1]
    assert len(shape.coordinates) == 3
    (issue,) = batch.issues
    assert issue.code == "tramos_unidos"
    assert issue.evidence["orden"] == [
        {"tramo": 0, "invertido": False},
        {"tramo": 1, "invertido": True},
    ]


def test_marks_variants_with_the_same_shape() -> None:
    batch = adapt(
        feature(4, "Línea 12", 12000),
        feature(10, "Línea 12 (Directo Amate)", 12001),
        feature(1, "Línea 1", 1000, {"type": "LineString", "coordinates": LINE[:2]}),
    )

    (issue,) = batch.issues
    assert issue.code == "trazado_compartido"
    assert issue.evidence["variant_codes"] == ["12000", "12001"]


def test_reports_code_contradicting_the_name() -> None:
    batch = adapt(feature(3, "Línea 6", 7000))

    assert codes(batch) == ["codigo_contradice_nombre"]
    assert batch.records[0].route_code == "7"


def test_name_is_optional() -> None:
    batch = adapt(feature(3, None, 6000))

    assert batch.records[0].long_name is None
    assert batch.issues == ()


@pytest.mark.parametrize(
    ("record", "code"),
    [
        (feature(None, "Línea 1", 1000), "sin_identificador"),
        (feature(1, "Línea 1", 999), "codigo_invalido"),
        (feature(1, "Línea 1", "1000"), "codigo_invalido"),
        (
            feature(1, "Línea 1", 1000, {"type": "Point", "coordinates": [0, 0]}),
            "geometria_invalida",
        ),
        (
            feature(
                1, "Línea 1", 1000, {"type": "LineString", "coordinates": [[0, 0]]}
            ),
            "geometria_invalida",
        ),
        (
            feature(
                1,
                "Línea 1",
                1000,
                {"type": "MultiLineString", "coordinates": [LINE, [[0, 0]]]},
            ),
            "geometria_invalida",
        ),
        (
            feature(
                1,
                "Línea 1",
                1000,
                {
                    "type": "MultiLineString",
                    "coordinates": [LINE[:2], [[-90.0, 15.0], [-90.1, 15.0]]],
                },
            ),
            "tramos_discontinuos",
        ),
    ],
)
def test_unusable_records_are_errors(record: dict[str, Any], code: str) -> None:
    batch = adapt(record)

    assert batch.records == ()
    assert codes(batch) == [code]
    assert batch.has_errors


def test_invalid_content_is_an_error() -> None:
    assert codes(adapt(content={"type": "FeatureCollection"})) == ["sin_features"]
    assert codes(adapt(content={"features": ["x"]})) == ["sin_identificador"]
