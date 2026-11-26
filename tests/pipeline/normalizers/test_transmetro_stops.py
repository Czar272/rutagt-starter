"""Pruebas del adaptador de estaciones de Transmetro."""

from typing import Any

import pytest

from rutagt.pipeline.normalizers import base, transmetro_stops
from rutagt.pipeline.normalizers.models import Severity, StagedStop

SNAPSHOT = "20261126T181403Z"


def feature(fid: Any, name: Any, **overrides: Any) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "FID": fid,
        "Nombre_lug": name,
        "Direccion": "6 avenida y 20 calle zona 1",
        "Zona": 1,
        "Codigoruta": 12000,
    }
    geometry = overrides.pop(
        "geometry", {"type": "Point", "coordinates": [-90.5, 14.6]}
    )
    properties.update(overrides)
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def adapt(*features: dict[str, Any], content: Any = None) -> Any:
    raw = base.RawInput(
        source_id=transmetro_stops.SOURCE_ID,
        snapshot_id=SNAPSHOT,
        content=content
        if content is not None
        else {"type": "FeatureCollection", "features": list(features)},
        provenance={},
    )
    return transmetro_stops.adapt(raw)


def codes(batch: Any) -> list[str]:
    return [issue.code for issue in batch.issues]


def test_is_registered() -> None:
    assert base.get_adapter(transmetro_stops.SOURCE_ID) is transmetro_stops.adapt


def test_maps_a_record_to_a_staged_stop() -> None:
    batch = adapt(feature(42, "Estación El Calvario"))

    (stop,) = batch.records
    assert isinstance(stop, StagedStop)
    assert stop.name == "Estación El Calvario"
    assert stop.position == (-90.5, 14.6)
    assert (stop.zone, stop.route_codes, stop.location_type) == ("1", ("12000",), 0)
    assert stop.source.external_id == "42"
    assert stop.source.raw["Nombre_lug"] == "Estación El Calvario"
    assert batch.issues == ()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "Estación Mariscal Direccion Plaza Barrios",
            ("Estación Mariscal", "Plaza Barrios"),
        ),
        (
            "Estación Reformita Dirección Central Sur",
            ("Estación Reformita", "Central Sur"),
        ),
        ("Granai - Dir. La Merced", ("Granai", "La Merced")),
        ("Colón - Líneas 6 y 18", ("Colón", None)),
        ("Estación Plaza Barrios - Fegua", ("Estación Plaza Barrios - Fegua", None)),
    ],
)
def test_split_name(name: str, expected: tuple[str, str | None]) -> None:
    assert transmetro_stops.split_name(name) == expected


def test_cleans_spaces_and_keeps_the_original() -> None:
    nbsp = chr(0xA0)
    batch = adapt(
        feature(
            19,
            f"Francos Monroy{nbsp} - Líneas 6 y 18",
            Direccion=" 11 avenida  y 15 calle zona 1",
        )
    )

    (stop,) = batch.records
    assert (stop.name, stop.address) == (
        "Francos Monroy",
        "11 avenida y 15 calle zona 1",
    )
    assert stop.source.raw["Nombre_lug"] == f"Francos Monroy{nbsp} - Líneas 6 y 18"
    assert codes(batch) == ["espacios_anomalos", "espacios_anomalos"]
    assert {i.severity for i in batch.issues} == {Severity.INFO}


def test_reports_zone_contradicting_the_address() -> None:
    batch = adapt(
        feature(
            44,
            "Estación Bolívar",
            Direccion="avenida bolivar y 32 calle zona 8",
            Zona=3,
        )
    )

    assert batch.records[0].zone == "3"
    (issue,) = batch.issues
    assert (issue.code, issue.severity) == ("zona_discrepante", Severity.WARNING)
    assert issue.evidence == {"zona": "3", "zona_direccion": "8"}


def test_address_without_zone_is_not_a_discrepancy() -> None:
    batch = adapt(
        feature(168, "Portales", Direccion="CA-9 NORTE Ruta al Atlantico", Zona=17)
    )

    assert batch.issues == ()


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"Zona": None}, "zona_invalida"),
        ({"Zona": 0}, "zona_invalida"),
        ({"Codigoruta": "12000"}, "sin_ruta"),
        ({"Direccion": None}, None),
    ],
)
def test_optional_fields_produce_warnings(
    overrides: dict[str, Any], code: str | None
) -> None:
    batch = adapt(feature(1, "Estación Trébol", **overrides))

    assert len(batch.records) == 1
    assert codes(batch) == ([code] if code else [])


@pytest.mark.parametrize(
    ("record", "code"),
    [
        (feature(1, "X", geometry=None), "geometria_invalida"),
        (
            feature(
                1, "X", geometry={"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
            ),
            "geometria_invalida",
        ),
        (
            feature(1, "X", geometry={"type": "Point", "coordinates": [-190.0, 14.6]}),
            "geometria_invalida",
        ),
        (
            feature(1, "X", geometry={"type": "Point", "coordinates": ["a", 14.6]}),
            "geometria_invalida",
        ),
        (
            feature(1, "X", geometry={"type": "Point", "coordinates": [1.0]}),
            "geometria_invalida",
        ),
        (feature(1, "   "), "sin_nombre"),
        (feature(1, None), "sin_nombre"),
        (feature(None, "X"), "sin_identificador"),
    ],
)
def test_unusable_records_are_errors(record: dict[str, Any], code: str) -> None:
    batch = adapt(record, feature(2, "Estación Trébol"))

    assert [r.source.external_id for r in batch.records] == ["2"]
    assert codes(batch) == [code]
    assert batch.has_errors


def test_invalid_content_is_an_error() -> None:
    batch = adapt(content={"type": "FeatureCollection"})

    assert (batch.records, codes(batch)) == ((), ["sin_features"])


def test_non_dict_features_are_errors() -> None:
    batch = adapt(content={"features": ["x"]})

    assert codes(batch) == ["sin_identificador"]


def test_reports_the_same_direction_at_two_positions() -> None:
    batch = adapt(
        feature(144, "Granai - Dir. La Merced", Codigoruta=7000),
        feature(
            145,
            "Granai - Dir. La Merced",
            Codigoruta=7000,
            geometry={"type": "Point", "coordinates": [-90.56, 14.60]},
        ),
        feature(146, "Rodolfo Robles - Dir. La Merced", Codigoruta=7000),
    )

    (issue,) = batch.issues
    assert issue.code == "sentido_duplicado"
    assert issue.evidence == {"external_ids": ["144", "145"], "route_code": "7000"}
