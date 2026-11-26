"""Mapa interactivo de la ruta 801 a partir del GeoJSON enriquecido (RGT-130).

Genera un HTML autocontenido (los datos van incrustados, por lo que se abre
con doble clic, sin servidor) con MapLibre GL JS y el mapa base vectorial de
OpenFreeMap. Las paradas se colorean según la calidad de su ubicación.

Uso, desde la raíz del repositorio:

    uv run python prototype/routing/enrich_route.py
    uv run python prototype/routing/render_map.py
"""

import json
from pathlib import Path
from string import Template
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
ENRICHED_FILE = OUTPUT_DIR / "route_801_enriched.geojson"
MAP_FILE = OUTPUT_DIR / "route_801_map.html"

# MapLibre 5.x es la última versión distribuida como paquete UMD de un solo
# archivo; la PWA usará la versión 6 (módulos ES) mediante npm y Vite.
MAPLIBRE_VERSION = "5.24.1"
MAPLIBRE_JS_SRI = (
    "sha384-nXMl9YiLoSG5KBPTFgvxVuIqQQcqIvo0bFrvoEaGJC6r7IibIzF1S36Zbf/sKBtL"
)
MAPLIBRE_CSS_SRI = (
    "sha384-uTttxo/aOKbdE5RlD/SPzSDoDmNvGlUYPjONi2MN/b7c9HPSvW07OIuyP7uL6jxK"
)
BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty"

TEMPLATE_FILE = Path(__file__).resolve().parent / "map_template.html"


def embed_json(value: Any) -> str:
    """Serializa JSON para incrustarlo de forma segura en un elemento <script>."""
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def with_flat_properties(enriched: dict[str, Any]) -> dict[str, Any]:
    """Copia el nivel de calidad de la ubicación a una propiedad plana.

    MapLibre serializa las propiedades anidadas al evaluar estilos, por lo que
    el color de cada parada se calcula a partir de `location_quality`.
    """
    features = []
    for feature in enriched["features"]:
        properties = dict(feature["properties"])
        quality = properties.get("quality", {})
        if "location" in quality:
            properties["location_quality"] = quality["location"]
        features.append({**feature, "properties": properties})
    return {**enriched, "features": features}


def render_map(enriched: dict[str, Any]) -> str:
    """HTML autocontenido del mapa para un GeoJSON enriquecido."""
    enriched = with_flat_properties(enriched)
    template = Template(TEMPLATE_FILE.read_text(encoding="utf-8"))
    return template.substitute(
        route_code=enriched["metadata"]["route_code"],
        maplibre_version=MAPLIBRE_VERSION,
        js_sri=MAPLIBRE_JS_SRI,
        css_sri=MAPLIBRE_CSS_SRI,
        basemap_style=BASEMAP_STYLE,
        data=embed_json(enriched),
    )


def main() -> None:
    enriched = json.loads(ENRICHED_FILE.read_text(encoding="utf-8"))
    MAP_FILE.write_text(render_map(enriched), encoding="utf-8", newline="\n")
    print(f"Mapa: {MAP_FILE}")


if __name__ == "__main__":
    main()
