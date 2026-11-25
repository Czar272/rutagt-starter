"""Pruebas del collector de enlaces en páginas HTML de referencia."""

import json
from pathlib import Path
from typing import Any

import pytest

from rutagt.pipeline.collectors import html_links
from rutagt.pipeline.collectors.http import HttpResponse

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html"
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
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    content_type: str = "text/html; charset=utf-8",
) -> None:
    def fake_http_get(url: str, **_: Any) -> Any:
        return HttpResponse(body, url, 200, {"content-type": content_type})

    monkeypatch.setattr(html_links, "http_get", fake_http_get)


def test_collects_only_documents_with_kept_extensions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    serve_page(monkeypatch, (FIXTURES / "catalogo_rutas.html").read_bytes())
    destination = tmp_path / SOURCE["output"]

    metadata = html_links.collect_html_links(SOURCE, destination)

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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    serve_page(monkeypatch, (FIXTURES / "catalogo_rutas.html").read_bytes())
    source = {**SOURCE, "keep_extensions": []}

    metadata = html_links.collect_html_links(source, tmp_path / "links.json")

    assert metadata["record_count"] == 6


def test_decodes_declared_charset_and_flags_replacement_characters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    body = '<a href="estación.pdf">Estación</a>'.encode("latin-1") + b"\xff\xfe"
    serve_page(monkeypatch, body, "text/html; charset=utf-8")

    metadata = html_links.collect_html_links(SOURCE, tmp_path / "links.json")

    assert metadata["quality_warnings"] == [
        "El HTML contiene caracteres de reemplazo Unicode"
    ]


def test_link_parser_resolves_relative_urls_and_ignores_data_urls() -> None:
    parser = html_links.LinkParser("https://example.test/catalog/")
    parser.feed(
        '<a href="docs/mapa.pdf">Mapa</a>'
        '<img src="/img/ruta.png">'
        '<img src="data:image/png;base64,AAAA">'
    )

    assert parser.links == {
        "https://example.test/catalog/docs/mapa.pdf",
        "https://example.test/img/ruta.png",
    }


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("text/html; charset=ISO-8859-1", "ISO-8859-1"),
        ("text/html; charset=utf-8; boundary=x", "utf-8"),
        ("text/html", "utf-8"),
    ],
)
def test_charset_from_content_type(content_type: str, expected: str) -> None:
    assert html_links.charset_from_content_type(content_type) == expected
