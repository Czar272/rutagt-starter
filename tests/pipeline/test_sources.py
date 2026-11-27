"""Pruebas de carga y selección del catálogo de fuentes."""

from pathlib import Path

import pytest

from rutagt.core.errors import ConfigurationError
from rutagt.core.settings import Settings
from rutagt.pipeline import collectors
from rutagt.pipeline.sources import is_enabled, load_sources, select_sources

SOURCES = [{"id": "a"}, {"id": "b"}, {"id": "c", "disabled_reason": "HTTP 403"}]


def test_project_catalog_is_valid() -> None:
    sources = load_sources(Settings.from_env({}).sources_config)

    assert len(sources) >= 4
    assert {source["type"] for source in sources} <= set(collectors.registered_types())


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ('{"sources": {}}', "lista 'sources'"),
        ("[]", "lista 'sources'"),
        ('{"sources": [{"id": "x"}, {"id": "x"}]}', "duplicados"),
        ("{no es json", "No se pudo leer"),
        ('{"sources": [{"id": "x", "disabled_reason": " "}]}', "vacío"),
        ('{"sources": [{"id": "x", "disabled_reason": 1}]}', "vacío"),
        ('{"sources": [{"id": "x", "shapes_source": "y"}]}', "desconocida: y"),
        ('{"sources": [{"id": "x", "agency": "Trans Metro"}]}', "'agency' inválida"),
        ('{"sources": [{"id": "x", "agency": 1}]}', "'agency' inválida"),
        ('{"sources": [{"id": "x", "group_stations": "si"}]}', "no booleano"),
    ],
)
def test_rejects_invalid_catalogs(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "sources.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=message):
        load_sources(path)


def test_missing_catalog_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="No se pudo leer"):
        load_sources(tmp_path / "no-existe.json")


def test_select_sources() -> None:
    assert select_sources(SOURCES, [], fetch_all=True) == SOURCES[:2]
    assert select_sources(SOURCES, ["b"], fetch_all=False) == [SOURCES[1]]


def test_disabled_sources_can_still_be_requested_explicitly() -> None:
    assert not is_enabled(SOURCES[2])
    assert select_sources(SOURCES, ["c"], fetch_all=False) == [SOURCES[2]]


def test_project_catalog_disabled_sources_explain_why() -> None:
    sources = load_sources(Settings.from_env({}).sources_config)

    disabled = [source for source in sources if not is_enabled(source)]
    assert all(len(source["disabled_reason"]) > 20 for source in disabled)
    assert any(is_enabled(source) for source in sources)


@pytest.mark.parametrize(
    ("requested", "message"),
    [(["z"], "desconocidas: z"), ([], "Indique --all")],
)
def test_select_sources_rejects_invalid_requests(
    requested: list[str], message: str
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        select_sources(SOURCES, requested, fetch_all=False)
