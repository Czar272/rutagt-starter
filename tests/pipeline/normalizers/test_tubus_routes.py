"""Pruebas del adaptador de rutas de TuBus."""

from typing import Any

import pytest

from rutagt.pipeline.normalizers import base, tubus_routes
from rutagt.pipeline.normalizers.models import StagedRoute, StagedShape

SNAPSHOT = "20261126T181403Z"
LINE = [[-90.50, 14.60], [-90.49, 14.60], [-90.48, 14.60]]


def feature(fid: Any, code: Any, geometry: Any = None) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": geometry
        if geometry is not None
        else {"type": "LineString", "coordinates": LINE},
        "properties": {"FID": fid, "Codigoruta": code, "Shape__Length": 2230.0},
    }


def adapt(*features: dict[str, Any]) -> Any:
    raw = base.RawInput(
        source_id=tubus_routes.SOURCE_ID,
        snapshot_id=SNAPSHOT,
        content={"type": "FeatureCollection", "features": list(features)},
        provenance={},
    )
    return tubus_routes.adapt(raw)


def codes(batch: Any) -> list[str]:
    return [issue.code for issue in batch.issues]


def test_is_registered() -> None:
    assert base.get_adapter(tubus_routes.SOURCE_ID) is tubus_routes.adapt


def test_maps_a_record_to_route_and_shape() -> None:
    batch = adapt(feature(1, "801"))

    route, shape = batch.records
    assert isinstance(route, StagedRoute)
    assert isinstance(shape, StagedShape)
    assert (route.route_code, route.short_name, route.variant_code) == (
        "801",
        "801",
        None,
    )
    assert route.long_name is None
    assert (shape.route_code, len(shape.coordinates)) == ("801", 3)
    assert shape.length_m == pytest.approx(2152.1, abs=0.1)
    assert route.source.raw["Codigoruta"] == "801"
    assert batch.issues == ()


@pytest.mark.parametrize(
    ("value", "expected"),
    [("801", "801"), (" 5 ", "5"), (104, "104"), ("0402", "402"), ("A1", None)],
)
def test_route_code_of(value: Any, expected: str | None) -> None:
    assert tubus_routes.route_code_of(value) == expected


@pytest.mark.parametrize(
    ("record", "code"),
    [
        (feature(None, "801"), "sin_identificador"),
        (feature(1, None), "codigo_invalido"),
        (feature(1, True), "codigo_invalido"),
        (
            feature(1, "801", {"type": "Point", "coordinates": [0, 0]}),
            "geometria_invalida",
        ),
    ],
)
def test_unusable_records_are_errors(record: dict[str, Any], code: str) -> None:
    batch = adapt(record, feature(2, "802"))

    assert [r.route_code for r in batch.records] == ["802", "802"]
    assert codes(batch) == [code]
    assert batch.has_errors


def test_repeated_routes_are_errors() -> None:
    batch = adapt(feature(1, "801"), feature(9, 801), feature(2, "5"))

    assert [r.route_code for r in batch.records] == ["5", "5"]
    (issue,) = batch.issues
    assert issue.code == "ruta_repetida"
    assert issue.evidence == {"external_ids": ["1", "9"], "route_code": "801"}
