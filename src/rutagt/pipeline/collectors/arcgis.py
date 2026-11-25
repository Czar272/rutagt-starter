"""Collector de capas publicadas como ArcGIS Feature Service.

Descubre el ítem público vigente por consulta al catálogo de ArcGIS (los
identificadores cambian entre publicaciones, ADR-0006), descarga la capa como
GeoJSON paginado en EPSG:4326 y escribe su archivo de procedencia.
"""

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rutagt.core.errors import SourceError
from rutagt.core.io import provenance_path, sha256_bytes, utc_now, write_json
from rutagt.pipeline.collectors.base import (
    CollectionResult,
    Source,
    register_collector,
)
from rutagt.pipeline.collectors.http import get_json
from rutagt.pipeline.validators.geojson import validate_geojson

ARCGIS_SEARCH = "https://www.arcgis.com/sharing/rest/search"
ARCGIS_ITEM = "https://www.arcgis.com/sharing/rest/content/items/{item_id}"
DEFAULT_PAGE_SIZE = 1000
MAX_PAGES = 10_000


def discover_item(source: Source) -> dict[str, Any]:
    """Devuelve el Feature Service público más reciente o el ítem de respaldo."""
    query = source.get("discover_query")
    if query:
        payload, _ = get_json(
            ARCGIS_SEARCH,
            {
                "f": "json",
                "q": query,
                "num": 20,
                "sortField": "modified",
                "sortOrder": "desc",
            },
        )
        candidates: list[dict[str, Any]] = [
            item
            for item in payload.get("results", [])
            if item.get("type") == "Feature Service" and item.get("access") == "public"
        ]
        if candidates:
            return candidates[0]

    item_id = source.get("fallback_item_id")
    if not item_id:
        raise SourceError(f"{source['id']}: no se encontró un Feature Service público")
    item, _ = get_json(ARCGIS_ITEM.format(item_id=item_id), {"f": "json"})
    if not isinstance(item, dict) or not item.get("url"):
        raise SourceError(
            f"{source['id']}: el ítem de respaldo no tiene URL de servicio"
        )
    return item


def layer_url(service_url: str, layer: int) -> str:
    """URL de la capa; respeta la capa si la URL del servicio ya la incluye."""
    service_url = service_url.rstrip("/")
    tail = urlparse(service_url).path.rsplit("/", 1)[-1]
    if tail.isdigit():
        return service_url
    return f"{service_url}/{layer}"


def fetch_features(
    endpoint: str, page_size: int, object_id_field: str | None, source_id: str
) -> list[dict[str, Any]]:
    """Descarga todas las entidades de una capa respetando la paginación."""
    features: list[dict[str, Any]] = []
    offset = 0
    for _page in range(MAX_PAGES):
        params: dict[str, Any] = {
            "f": "geojson",
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        if object_id_field:
            params["orderByFields"] = object_id_field
        page, _ = get_json(f"{endpoint}/query", params)
        current = page.get("features", [])
        features.extend(current)
        exceeded = bool(page.get("properties", {}).get("exceededTransferLimit"))
        if not current or (len(current) < page_size and not exceeded):
            return features
        offset += len(current)
    raise SourceError(f"{source_id}: se excedió el límite de paginación")


@register_collector("arcgis_feature_service")
def collect_arcgis(source: Source, destination: Path) -> CollectionResult:
    """Descarga una capa ArcGIS a GeoJSON y escribe su procedencia."""
    item = discover_item(source)
    item_id = item.get("id") or source.get("fallback_item_id")
    if item_id:
        full_item, _ = get_json(ARCGIS_ITEM.format(item_id=item_id), {"f": "json"})
        item.update(full_item)

    service_url = item.get("url")
    if not service_url:
        raise SourceError(
            f"{source['id']}: ArcGIS no publicó la URL del Feature Service"
        )
    endpoint = layer_url(service_url, int(source.get("layer", 0)))
    layer_meta, _ = get_json(endpoint, {"f": "json"})
    object_id_field = layer_meta.get("objectIdField") or layer_meta.get(
        "objectIdFieldName"
    )
    max_records = int(layer_meta.get("maxRecordCount") or DEFAULT_PAGE_SIZE)
    page_size = min(max_records, DEFAULT_PAGE_SIZE)
    features = fetch_features(endpoint, page_size, object_id_field, source["id"])

    feature_collection = {
        "type": "FeatureCollection",
        "name": source["id"],
        "features": features,
    }
    body = write_json(destination, feature_collection)
    metadata: CollectionResult = {
        "source_id": source["id"],
        "source_name": source.get("name"),
        "authority": source.get("authority"),
        "source_type": source["type"],
        "catalog_url": source.get("catalog_url"),
        "resolved_item_id": item_id,
        "resolved_service_url": service_url,
        "resolved_layer_url": endpoint,
        "fetched_at": utc_now(),
        "record_count": len(features),
        "sha256": sha256_bytes(body),
        "license_note": source.get("license_note"),
        "arcgis": {
            "title": item.get("title"),
            "owner": item.get("owner"),
            "created": item.get("created"),
            "modified": item.get("modified"),
            "access": item.get("access"),
            "access_information": item.get("accessInformation"),
            "license_info_html": item.get("licenseInfo"),
            "object_id_field": object_id_field,
        },
        "quality_warnings": validate_geojson(feature_collection, source),
    }
    write_json(provenance_path(destination), metadata)
    return metadata
