#!/usr/bin/env python3
"""Recolector reproducible de fuentes públicas para RutaGT.

Usa únicamente la biblioteca estándar. Descarga capas ArcGIS como GeoJSON,
descubre la versión pública más reciente por consulta de catálogo y genera un
archivo de procedencia con URL, fecha, checksum y advertencias de calidad.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "RutaGT-data-collector/0.1 (+contacto-pendiente)"
ARCGIS_SEARCH = "https://www.arcgis.com/sharing/rest/search"
ARCGIS_ITEM = "https://www.arcgis.com/sharing/rest/content/items/{item_id}"
DEFAULT_TIMEOUT = 45
DEFAULT_PAGE_SIZE = 1000


class CollectorError(RuntimeError):
    """Falla controlada de una fuente."""


@dataclass
class HttpResponse:
    body: bytes
    final_url: str
    status: int
    headers: dict[str, str]


class LinkParser(HTMLParser):
    """Extrae enlaces y recursos declarados en HTML sin ejecutar JavaScript."""

    ATTRS = {
        "a": "href",
        "img": "src",
        "iframe": "src",
        "script": "src",
        "link": "href",
        "source": "src",
    }

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        wanted = self.ATTRS.get(tag.lower())
        if not wanted:
            return
        values = dict(attrs)
        value = values.get(wanted)
        if not value or value.startswith(("data:", "javascript:", "mailto:", "tel:")):
            return
        self.links.add(urljoin(self.base_url, value))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(body)
    return body


def http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    attempts: int = 3,
) -> HttpResponse:
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(params)}"

    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return HttpResponse(
                    body=response.read(),
                    final_url=response.geturl(),
                    status=getattr(response, "status", 200),
                    headers={key.lower(): value for key, value in response.headers.items()},
                )
        except (HTTPError, URLError, TimeoutError) as exc:
            error = exc
            if isinstance(exc, HTTPError) and 400 <= exc.code < 500 and exc.code != 429:
                break
            if attempt < attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
    raise CollectorError(f"No fue posible consultar {url}: {error}")


def get_json(url: str, params: dict[str, Any] | None = None) -> tuple[Any, HttpResponse]:
    response = http_get(url, params=params)
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectorError(f"Respuesta JSON inválida de {response.final_url}: {exc}") from exc
    if isinstance(payload, dict) and payload.get("error"):
        raise CollectorError(f"ArcGIS devolvió un error: {payload['error']}")
    return payload, response


def discover_arcgis_item(source: dict[str, Any]) -> dict[str, Any]:
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
        candidates = [
            item
            for item in payload.get("results", [])
            if item.get("type") == "Feature Service" and item.get("access") == "public"
        ]
        if candidates:
            return candidates[0]

    item_id = source.get("fallback_item_id")
    if not item_id:
        raise CollectorError(f"{source['id']}: no se encontró un Feature Service público")
    item, _ = get_json(ARCGIS_ITEM.format(item_id=item_id), {"f": "json"})
    if not item.get("url"):
        raise CollectorError(f"{source['id']}: el ítem de respaldo no tiene URL de servicio")
    return item


def layer_url(service_url: str, layer: int) -> str:
    service_url = service_url.rstrip("/")
    parsed = urlparse(service_url)
    tail = parsed.path.rsplit("/", 1)[-1]
    if tail.isdigit():
        return service_url
    return f"{service_url}/{layer}"


def collect_arcgis(source: dict[str, Any], destination: Path) -> dict[str, Any]:
    item = discover_arcgis_item(source)
    item_id = item.get("id") or source.get("fallback_item_id")
    if item_id:
        full_item, _ = get_json(ARCGIS_ITEM.format(item_id=item_id), {"f": "json"})
        item.update(full_item)

    service_url = item.get("url")
    if not service_url:
        raise CollectorError(f"{source['id']}: ArcGIS no publicó la URL del Feature Service")
    endpoint = layer_url(service_url, int(source.get("layer", 0)))
    layer_meta, _ = get_json(endpoint, {"f": "json"})
    object_id_field = layer_meta.get("objectIdField") or layer_meta.get("objectIdFieldName")
    max_records = int(layer_meta.get("maxRecordCount") or DEFAULT_PAGE_SIZE)
    page_size = min(max_records, DEFAULT_PAGE_SIZE)

    features: list[dict[str, Any]] = []
    offset = 0
    for _page in range(10000):
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
            break
        offset += len(current)
    else:
        raise CollectorError(f"{source['id']}: se excedió el límite de paginación")

    feature_collection = {
        "type": "FeatureCollection",
        "name": source["id"],
        "features": features,
    }
    body = write_json(destination, feature_collection)
    warnings = validate_geojson(feature_collection, source)
    metadata = {
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
        "quality_warnings": warnings,
    }
    write_json(destination.with_suffix(destination.suffix + ".provenance.json"), metadata)
    return metadata


def validate_geojson(collection: dict[str, Any], source: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    features = collection.get("features", [])
    allowed = set(source.get("expected_geometry", []))
    required = set(source.get("required_fields", []))
    geometry_types: set[str] = set()
    missing_counts = {field: 0 for field in required}
    replacement_characters = 0

    for feature in features:
        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type")
        if geometry_type:
            geometry_types.add(geometry_type)
        properties = feature.get("properties") or {}
        for field in required:
            if properties.get(field) in (None, ""):
                missing_counts[field] += 1
        replacement_characters += json.dumps(properties, ensure_ascii=False).count("�")

    unexpected = geometry_types - allowed if allowed else set()
    if unexpected:
        warnings.append(f"Geometrías no esperadas: {sorted(unexpected)}")
    for field, count in sorted(missing_counts.items()):
        if count:
            warnings.append(f"{count} registros sin el campo requerido {field}")
    if replacement_characters:
        warnings.append(
            f"Se encontraron {replacement_characters} caracteres de reemplazo Unicode; "
            "conservar el dato original y corregirlo en una capa normalizada."
        )
    if not features:
        warnings.append("La fuente no devolvió registros")
    return warnings


def collect_html_links(source: dict[str, Any], destination: Path) -> dict[str, Any]:
    response = http_get(source["url"])
    content_type = response.headers.get("content-type", "")
    encoding = "utf-8"
    if "charset=" in content_type:
        encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
    html = response.body.decode(encoding, errors="replace")
    parser = LinkParser(response.final_url)
    parser.feed(html)
    extensions = {extension.lower() for extension in source.get("keep_extensions", [])}
    selected = sorted(
        link
        for link in parser.links
        if not extensions or Path(urlparse(link).path).suffix.lower() in extensions
    )
    payload = {
        "source_id": source["id"],
        "source_url": source["url"],
        "final_url": response.final_url,
        "fetched_at": utc_now(),
        "links": selected,
    }
    body = write_json(destination, payload)
    metadata = {
        "source_id": source["id"],
        "source_name": source.get("name"),
        "authority": source.get("authority"),
        "source_type": source["type"],
        "source_url": source["url"],
        "final_url": response.final_url,
        "fetched_at": payload["fetched_at"],
        "record_count": len(selected),
        "http_status": response.status,
        "content_type": content_type,
        "sha256": sha256_bytes(body),
        "source_page_sha256": sha256_bytes(response.body),
        "license_note": source.get("license_note"),
        "quality_warnings": (["El HTML contiene caracteres de reemplazo Unicode"] if "�" in html else []),
    }
    write_json(destination.with_suffix(destination.suffix + ".provenance.json"), metadata)
    return metadata


def collect_source(source: dict[str, Any], output_root: Path) -> dict[str, Any]:
    destination = output_root / source["output"]
    source_type = source["type"]
    if source_type == "arcgis_feature_service":
        return collect_arcgis(source, destination)
    if source_type == "html_links":
        return collect_html_links(source, destination)
    raise CollectorError(f"Tipo de fuente no soportado: {source_type}")


def load_sources(config_path: Path) -> list[dict[str, Any]]:
    config = read_json(config_path)
    sources = config.get("sources")
    if not isinstance(sources, list):
        raise CollectorError("La configuración debe contener una lista 'sources'")
    ids = [source.get("id") for source in sources]
    if len(ids) != len(set(ids)):
        raise CollectorError("Hay identificadores de fuente duplicados")
    return sources


def select_sources(
    sources: list[dict[str, Any]], requested: Iterable[str], fetch_all: bool
) -> list[dict[str, Any]]:
    if fetch_all:
        return sources
    requested_set = set(requested)
    selected = [source for source in sources if source["id"] in requested_set]
    missing = requested_set - {source["id"] for source in selected}
    if missing:
        raise CollectorError(f"Fuentes desconocidas: {', '.join(sorted(missing))}")
    if not selected:
        raise CollectorError("Indique --all o al menos un --source")
    return selected


def default_config() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "sources.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recolector de fuentes públicas de RutaGT")
    parser.add_argument("--config", type=Path, default=default_config())
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="Lista las fuentes configuradas")
    fetch = subparsers.add_parser("fetch", help="Descarga una o varias fuentes")
    fetch.add_argument("--source", action="append", default=[], help="ID de la fuente")
    fetch.add_argument("--all", action="store_true", help="Descarga todas las fuentes")
    fetch.add_argument(
        "--output",
        type=Path,
        default=Path(os.environ.get("RUTAGT_DATA_DIR", "data/raw")),
        help="Directorio para datos crudos",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        sources = load_sources(args.config)
        if args.command == "list":
            for source in sources:
                print(f"{source['id']:<42} {source['type']:<24} {source.get('name', '')}")
            return 0

        selected = select_sources(sources, args.source, args.all)
        results: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for source in selected:
            print(f"[RutaGT] Recolectando {source['id']}...", flush=True)
            try:
                result = collect_source(source, args.output)
                results.append(result)
                warnings = len(result.get("quality_warnings", []))
                print(
                    f"[RutaGT] OK {source['id']}: {result.get('record_count', 0)} "
                    f"registros, {warnings} advertencias"
                )
            except Exception as exc:  # continuar con las demás fuentes y resumir al final
                failures.append({"source_id": source["id"], "error": str(exc)})
                print(f"[RutaGT] ERROR {source['id']}: {exc}", file=sys.stderr)

        run_manifest = {
            "project": "RutaGT",
            "started_by": USER_AGENT,
            "finished_at": utc_now(),
            "config": str(args.config.resolve()),
            "output": str(args.output.resolve()),
            "successful": results,
            "failed": failures,
        }
        write_json(args.output / "run_manifest.json", run_manifest)
        print(f"[RutaGT] Manifiesto: {(args.output / 'run_manifest.json').resolve()}")
        return 1 if failures else 0
    except CollectorError as exc:
        print(f"[RutaGT] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
