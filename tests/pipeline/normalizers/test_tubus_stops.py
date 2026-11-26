"""Pruebas del adaptador de paradas de TuBus."""

from typing import Any

import pytest

from rutagt.pipeline.normalizers import base, tubus_stops
from rutagt.pipeline.normalizers.models import Severity

SNAPSHOT = "20261126T181403Z"


def feature(fid: int, name: str, **overrides: Any) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "FID": fid,
        "Nombre_lug": name,
        "Codigoruta": 801,
        "Direccion": "33 avenida y 26 calle, Colonia Bethania",
        "Zona": 7,
    }
    coordinates = overrides.pop("coordinates", [-90.53, 14.64])
    properties.update(overrides)
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coordinates},
        "properties": properties,
    }


def adapt(*features: dict[str, Any]) -> Any:
    raw = base.RawInput(
        source_id=tubus_stops.SOURCE_ID,
        snapshot_id=SNAPSHOT,
        content={"type": "FeatureCollection", "features": list(features)},
        provenance={},
    )
    return tubus_stops.adapt(raw)


def test_is_registered() -> None:
    assert base.get_adapter(tubus_stops.SOURCE_ID) is tubus_stops.adapt


def test_maps_a_record_with_the_route_code_as_text() -> None:
    batch = adapt(feature(1, "Canchas Barrio San Antonio", Codigoruta=104))

    (stop,) = batch.records
    assert (stop.name, stop.route_codes, stop.zone) == (
        "Canchas Barrio San Antonio",
        ("104",),
        "7",
    )
    assert stop.address == "33 avenida y 26 calle, Colonia Bethania"
    assert stop.direction_hint is None
    assert batch.issues == ()


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Parada 068", "68"), ("parada 06", "6"), ("Parada", None), ("PNC", None)],
)
def test_generic_number(name: str, expected: str | None) -> None:
    assert tubus_stops.generic_number(name) == expected


def test_generic_names_are_kept_and_reported() -> None:
    batch = adapt(feature(64, "Parada 068"))

    assert batch.records[0].name == "Parada 068"
    (issue,) = batch.issues
    assert (issue.code, issue.severity) == ("nombre_generico", Severity.INFO)
    assert issue.evidence == {"numero": "68"}


def test_repeated_numbers_within_a_route_are_warnings() -> None:
    batch = adapt(
        feature(101, "Parada 105"),
        feature(102, "Parada 105", coordinates=[-90.54, 14.64]),
        feature(238, "Parada 105", Codigoruta=802),
    )

    repeated = [i for i in batch.issues if i.code == "numero_repetido"]
    assert len(repeated) == 1
    assert repeated[0].severity is Severity.WARNING
    assert repeated[0].evidence == {
        "external_ids": ["101", "102"],
        "route_code": "801",
        "numero": "105",
    }


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("8a avenida zona 13. Aeropuerto Nacional La Aurora dirección norte", "norte"),
        ("8a avenida zona 13. Aeropuerto La Aurora Dirección Sur", "sur"),
        ("Bulevar Aeropuerto y 6a calle zona 13", None),
    ],
)
def test_direction_written_in_the_address(address: str, expected: str | None) -> None:
    batch = adapt(feature(163, "Aeropuerto", Direccion=address, Zona=13))

    assert batch.records[0].direction_hint == expected
    assert tubus_stops.address_direction(None) is None


def test_shared_rules_apply() -> None:
    batch = adapt(
        feature(205, "Parque", Direccion="4 avenida y 7 calle zona 3", Zona=7),
        feature(214, "Estación Matamoros" + chr(0xA0)),
    )

    assert [i.code for i in batch.issues] == ["zona_discrepante", "espacios_anomalos"]
    assert batch.records[1].name == "Estación Matamoros"
