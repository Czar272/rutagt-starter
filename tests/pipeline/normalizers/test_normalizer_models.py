"""Pruebas de los modelos de staging y del registro de adaptadores."""

from typing import Any

import pytest
from pydantic import ValidationError

from rutagt.core.errors import ConfigurationError
from rutagt.pipeline.normalizers import base
from rutagt.pipeline.normalizers.models import (
    Issue,
    Severity,
    SourceRef,
    StagedRoute,
    StagedShape,
    StagedStop,
    StagingBatch,
)

SNAPSHOT = "20261126T181403Z"


def ref(external_id: str = "1") -> SourceRef:
    return SourceRef(source_id="muni_paradas", external_id=external_id, raw={"FID": 1})


def stop(**overrides: Any) -> StagedStop:
    values: dict[str, Any] = {
        "source": ref(),
        "name": "Parada 1",
        "position": (-90.5, 14.6),
    }
    return StagedStop(**{**values, **overrides})


def test_valid_records_and_defaults() -> None:
    record = stop(route_codes=("801",))
    route = StagedRoute(
        source=ref("2"), route_code="12", variant_code="1", short_name="12"
    )
    shape = StagedShape(
        source=ref("3"),
        route_code="12",
        coordinates=((-90.5, 14.6), (-90.4, 14.7)),
        length_m=1500.0,
    )

    assert (record.entity_type, record.location_type) == ("stop", 0)
    assert route.route_type == 3
    assert shape.entity_type == "shape"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"position": (-190.0, 14.6)},
        {"position": (-90.5, 95.0)},
        {"location_type": 5},
        {"zone": 1},
        {"unknown": "campo"},
    ],
    ids=[
        "nombre-vacio",
        "longitud",
        "latitud",
        "location-type",
        "sin-conversion",
        "extra",
    ],
)
def test_invalid_stops_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        stop(**overrides)


@pytest.mark.parametrize(
    "values",
    [
        {"source_id": "Muni-Paradas", "external_id": "1", "raw": {}},
        {"source_id": "muni", "external_id": "", "raw": {}},
    ],
)
def test_invalid_source_refs(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SourceRef(**values)


def test_shapes_need_two_positions_and_positive_length() -> None:
    with pytest.raises(ValidationError):
        StagedShape(
            source=ref(), route_code="1", coordinates=((-90.5, 14.6),), length_m=1.0
        )
    with pytest.raises(ValidationError):
        StagedShape(
            source=ref(),
            route_code="1",
            coordinates=((-90.5, 14.6), (-90.4, 14.6)),
            length_m=0.0,
        )


def test_records_are_immutable() -> None:
    with pytest.raises(ValidationError):
        stop().name = "otro"


def test_batch_errors_and_json_round_trip() -> None:
    warning = Issue(severity=Severity.WARNING, code="zona_discrepante", message="Zona")
    error = Issue(
        severity=Severity.ERROR, code="sin_geometria", message="Falta", external_id="9"
    )
    batch = StagingBatch(
        source_id="muni_paradas",
        snapshot_id=SNAPSHOT,
        records=(stop(),),
        issues=(warning,),
    )

    assert batch.has_errors is False
    assert batch.model_copy(update={"issues": (warning, error)}).has_errors is True
    restored = StagingBatch.model_validate_json(batch.model_dump_json())
    assert restored == batch
    assert isinstance(restored.records[0], StagedStop)


@pytest.mark.parametrize("snapshot_id", ["latest", "2026-11-26"])
def test_batch_requires_a_valid_snapshot_id(snapshot_id: str) -> None:
    with pytest.raises(ValidationError):
        StagingBatch(source_id="muni", snapshot_id=snapshot_id, records=())


def test_issue_codes_are_snake_case() -> None:
    with pytest.raises(ValidationError):
        Issue(severity=Severity.INFO, code="Zona Mala", message="x")


def test_adapter_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base, "_REGISTRY", {})

    @base.register_adapter("muni_paradas")
    def adapter(raw: base.RawInput) -> StagingBatch:
        return StagingBatch(
            source_id=raw.source_id, snapshot_id=raw.snapshot_id, records=()
        )

    assert base.registered_sources() == ["muni_paradas"]
    assert base.get_adapter("muni_paradas") is adapter
    with pytest.raises(ValueError, match="Ya existe"):
        base.register_adapter("muni_paradas")(adapter)
    with pytest.raises(ConfigurationError, match="No hay adaptador"):
        base.get_adapter("otra")
