"""Pruebas del generador del mapa HTML."""

import json
import re
from typing import Any

from render_map import (
    MAPLIBRE_CSS_SRI,
    MAPLIBRE_JS_SRI,
    embed_json,
    render_map,
    with_flat_properties,
)

ENRICHED: dict[str, Any] = {
    "type": "FeatureCollection",
    "metadata": {"route_code": "801", "route_name": "Ruta de prueba"},
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-90.5, 14.6]},
            "properties": {
                "feature_type": "stop",
                "layer_fid": 1,
                "layer_name": "</script><script>alert(1)</script>",
                "quality": {"location": "probable"},
                "discrepancies": [],
            },
        }
    ],
}


def embedded_data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="route-data" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    assert match
    return json.loads(match.group(1))


def test_embed_json_escapes_html_sensitive_characters() -> None:
    text = embed_json({"x": "</script>&<b>"})

    assert "<" not in text
    assert ">" not in text
    assert "&" not in text
    assert json.loads(text) == {"x": "</script>&<b>"}


def test_render_map_embeds_data_safely_and_fills_template() -> None:
    html = render_map(ENRICHED)

    assert "$" not in html.split('<script id="route-data"')[0]
    assert MAPLIBRE_JS_SRI in html
    assert MAPLIBRE_CSS_SRI in html
    assert html.count("<script>alert(1)</script>") == 0
    data = embedded_data(html)
    assert data["features"][0]["properties"]["layer_name"].startswith("</script>")


def test_with_flat_properties_exposes_location_quality() -> None:
    flat = with_flat_properties(ENRICHED)

    assert flat["features"][0]["properties"]["location_quality"] == "probable"
    assert "location_quality" not in ENRICHED["features"][0]["properties"]
