"""Pruebas de extracción de enlaces desde páginas HTML de referencia."""

import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"
PAGE_URL = "https://movilidad.example.test/tubus/"

SOURCE: dict[str, Any] = {
    "id": "catalogo_prueba",
    "name": "Catálogo de prueba",
    "type": "html_links",
    "url": PAGE_URL,
    "output": "prueba/catalogo_links.json",
    "keep_extensions": [".pdf", ".png", ".webp"],
}


def serve_page(
    collect: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    content_type: str = "text/html; charset=utf-8",
) -> None:
    def fake_http_get(url: str, **_: Any) -> Any:
        return collect.HttpResponse(body, url, 200, {"content-type": content_type})

    monkeypatch.setattr(collect, "http_get", fake_http_get)


def test_collects_only_documents_with_kept_extensions(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    serve_page(collect, monkeypatch, (FIXTURES / "catalogo_rutas.html").read_bytes())
    destination = tmp_path / SOURCE["output"]

    metadata = collect.collect_html_links(SOURCE, destination)

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["links"] == [
        "https://cdn.example.test/mapas/Ruta-105.PNG",
        "https://movilidad.example.test/img/logo.webp",
        "https://movilidad.example.test/tubus/docs/Rutero-Ruta-801.pdf",
    ]
    assert metadata["record_count"] == 3
    assert metadata["quality_warnings"] == []
    assert destination.with_name("catalogo_links.json.provenance.json").exists()


def test_keeps_every_link_when_no_extensions_are_configured(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    serve_page(collect, monkeypatch, (FIXTURES / "catalogo_rutas.html").read_bytes())
    source = {**SOURCE, "keep_extensions": []}

    metadata = collect.collect_html_links(source, tmp_path / "links.json")

    assert metadata["record_count"] == 6


def test_decodes_declared_charset_and_flags_replacement_characters(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    body = '<a href="estación.pdf">Estación</a>'.encode("latin-1") + b"\xff\xfe"
    serve_page(collect, monkeypatch, body, "text/html; charset=utf-8")

    metadata = collect.collect_html_links(SOURCE, tmp_path / "links.json")

    assert metadata["quality_warnings"] == [
        "El HTML contiene caracteres de reemplazo Unicode"
    ]


def test_collect_source_dispatches_by_type(
    collect: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(collect, "collect_html_links", lambda source, dest: {"d": dest})

    result = collect.collect_source(SOURCE, tmp_path)

    assert result == {"d": tmp_path / SOURCE["output"]}


def test_collect_source_rejects_unknown_type(
    collect: ModuleType, tmp_path: Path
) -> None:
    with pytest.raises(collect.CollectorError, match="no soportado"):
        collect.collect_source({**SOURCE, "type": "ftp"}, tmp_path)
