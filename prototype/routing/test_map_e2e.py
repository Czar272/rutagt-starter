"""Prueba de extremo a extremo del mapa de la ruta 801 (RGT-135).

Abre el mapa generado en Chromium sin interfaz y verifica que MapLibre
dibuje el trazado y las paradas, que el panel muestre el resumen y que la
lista de discrepancias abra la ventana de una parada.

El mapa base se sustituye por un estilo mínimo local para no depender de
servicios externos; MapLibre se descarga del CDN, lo que además verifica que
su hash de integridad (SRI) siga siendo válido.

Ejecutar desde la raíz del repositorio:

    uv run playwright install chromium   # una sola vez
    uv run pytest prototype/routing -m e2e
"""

import json
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page, Route, expect
from render_map import BASEMAP_STYLE, ENRICHED_FILE, render_map

pytestmark = pytest.mark.e2e

STUB_STYLE = {
    "version": 8,
    "glyphs": "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    "sources": {},
    "layers": [
        {"id": "fondo", "type": "background", "paint": {"background-color": "#f2efe9"}}
    ],
}


@pytest.fixture(scope="session")
def browser_type_launch_args(
    browser_type_launch_args: dict[str, Any],
) -> dict[str, Any]:
    """Habilita WebGL por software para que MapLibre funcione sin GPU."""
    return {
        **browser_type_launch_args,
        "args": ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    }


@pytest.fixture
def enriched() -> dict[str, Any]:
    return json.loads(ENRICHED_FILE.read_text(encoding="utf-8"))


@pytest.fixture
def map_page(page: Page, tmp_path: Path, enriched: dict[str, Any]) -> Page:
    """Página con el mapa cargado y la lista de errores de consola."""

    def serve_basemap(route: Route) -> None:
        if route.request.url == BASEMAP_STYLE:
            route.fulfill(json=STUB_STYLE)
        else:
            # Fuentes y teselas del mapa base: respuesta vacía.
            route.fulfill(status=200, body=b"", content_type="application/x-protobuf")

    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            errors.append(message.text) if message.type == "error" else None
        ),
    )
    page.route("https://tiles.openfreemap.org/**", serve_basemap)

    html_file = tmp_path / "route_801_map.html"
    html_file.write_text(render_map(enriched), encoding="utf-8")
    page.goto(html_file.as_uri())
    page.wait_for_function(
        "() => typeof map !== 'undefined' && map.loaded() && !!map.getLayer('stops')",
        timeout=30_000,
    )
    page.wait_for_function(
        "() => map.queryRenderedFeatures({ layers: ['stops'] }).length > 0",
        timeout=30_000,
    )
    page.errors = errors  # type: ignore[attr-defined]
    return page


def feature_count(enriched: dict[str, Any], *types: str) -> int:
    return sum(
        feature["properties"]["feature_type"] in types
        for feature in enriched["features"]
    )


def test_map_renders_route_and_every_stop(
    map_page: Page, enriched: dict[str, Any]
) -> None:
    rendered_stops = map_page.evaluate(
        """() => new Set(
            map.queryRenderedFeatures({ layers: ['stops'] })
              .map((f) => f.properties.layer_fid)
        ).size"""
    )
    rendered_route = map_page.evaluate(
        "() => map.queryRenderedFeatures({ layers: ['route-line'] }).length"
    )

    assert rendered_stops == feature_count(enriched, "stop", "excluded_stop")
    assert rendered_route > 0


def test_panel_shows_summary_and_discrepancies(
    map_page: Page, enriched: dict[str, Any]
) -> None:
    summary = enriched["metadata"]["summary"]

    expect(map_page.locator("h1")).to_contain_text("Ruta 801")
    expect(map_page.locator("#summary dd").first).to_have_text(str(summary["stops"]))
    expect(map_page.locator("#issues button")).to_have_count(
        summary["with_discrepancies"]
    )


def test_discrepancy_button_flies_to_stop_and_opens_popup(map_page: Page) -> None:
    button = map_page.locator("#issues button").first
    stop_code = button.inner_text().split(" ")[0]

    button.click()

    popup = map_page.locator(".maplibregl-popup")
    expect(popup).to_be_visible()
    expect(popup).to_contain_text(f"Parada {stop_code}")
    map_page.wait_for_function("() => !map.isMoving() && map.getZoom() > 15")


def test_map_loads_without_errors(map_page: Page) -> None:
    assert map_page.errors == []  # type: ignore[attr-defined]
