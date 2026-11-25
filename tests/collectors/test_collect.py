"""Pruebas de validación, configuración y utilidades del recolector."""

from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_link_parser_resolves_relative_urls_and_ignores_data_urls(
    collect: ModuleType,
) -> None:
    parser = collect.LinkParser("https://example.test/catalog/")
    parser.feed(
        '<a href="docs/mapa.pdf">Mapa</a>'
        '<img src="/img/ruta.png">'
        '<img src="data:image/png;base64,AAAA">'
    )

    assert parser.links == {
        "https://example.test/catalog/docs/mapa.pdf",
        "https://example.test/img/ruta.png",
    }


def test_validation_reports_missing_fields_and_bad_encoding(
    collect: ModuleType,
) -> None:
    collection = {
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [-90.5, 14.6]},
                "properties": {"Nombre_lug": "Estaci�n", "Codigoruta": None},
            }
        ]
    }
    source = {
        "expected_geometry": ["Point"],
        "required_fields": ["Nombre_lug", "Codigoruta"],
    }

    warnings = collect.validate_geojson(collection, source)

    assert any("Codigoruta" in warning for warning in warnings)
    assert any("Unicode" in warning for warning in warnings)


def test_validation_rejects_unexpected_geometry(collect: ModuleType) -> None:
    collection = {
        "features": [
            {"geometry": {"type": "LineString", "coordinates": []}, "properties": {}}
        ]
    }

    warnings = collect.validate_geojson(
        collection, {"expected_geometry": ["Point"], "required_fields": []}
    )

    assert any("Geometrías" in warning for warning in warnings)


def test_validation_warns_on_empty_source(collect: ModuleType) -> None:
    assert collect.validate_geojson({"features": []}, {}) == [
        "La fuente no devolvió registros"
    ]


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://example.test/data", "datos.json"]
)
def test_http_get_rejects_non_http_schemes(collect: ModuleType, url: str) -> None:
    with pytest.raises(collect.CollectorError, match="Esquema de URL no permitido"):
        collect.http_get(url, attempts=1)


def test_project_configuration_loads(collect: ModuleType) -> None:
    sources = collect.load_sources(PROJECT_ROOT / "config" / "sources.json")

    assert len(sources) >= 4
    assert len({source["id"] for source in sources}) == len(sources)


def test_write_json_is_utf8_and_repeatable(collect: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "dato.json"

    body = collect.write_json(path, {"nombre": "Línea 13"})

    assert body == path.read_bytes()
    assert "Línea".encode() in body
