"""Pruebas del contrato y el registro de collectors."""

from pathlib import Path
from typing import Any

import pytest

from rutagt.core.errors import ConfigurationError
from rutagt.pipeline import collectors
from rutagt.pipeline.collectors import base


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    registry: dict[str, Any] = {}
    monkeypatch.setattr(base, "_REGISTRY", registry)
    return registry


def test_builtin_collectors_are_registered() -> None:
    assert collectors.registered_types() == ["arcgis_feature_service", "html_links"]


def test_collect_source_dispatches_by_type_and_output(
    isolated_registry: dict[str, Any], tmp_path: Path
) -> None:
    @base.register_collector("prueba")
    def collect_prueba(source: dict[str, Any], destination: Path) -> dict[str, Any]:
        return {"source_id": source["id"], "destination": destination}

    result = base.collect_source(
        {"id": "x", "type": "prueba", "output": "a/x.json"}, tmp_path
    )

    assert result == {"source_id": "x", "destination": tmp_path / "a" / "x.json"}


def test_register_rejects_duplicate_types(isolated_registry: dict[str, Any]) -> None:
    base.register_collector("prueba")(lambda source, destination: {})

    with pytest.raises(ValueError, match="Ya existe"):
        base.register_collector("prueba")(lambda source, destination: {})


def test_unknown_source_type_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="no soportado: ftp"):
        base.collect_source({"id": "x", "type": "ftp", "output": "x"}, tmp_path)
