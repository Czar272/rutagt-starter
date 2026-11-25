"""Collector de enlaces y documentos publicados en páginas HTML oficiales.

Extrae enlaces declarados en el HTML sin ejecutar JavaScript y conserva solo
las extensiones configuradas (PDF, imágenes, CSV, etc.).
"""

from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar
from urllib.parse import urljoin, urlparse

from rutagt.core.io import provenance_path, sha256_bytes, utc_now, write_json
from rutagt.pipeline.collectors.base import (
    CollectionResult,
    Source,
    register_collector,
)
from rutagt.pipeline.collectors.http import http_get

REPLACEMENT_CHARACTER = "�"
IGNORED_PREFIXES = ("data:", "javascript:", "mailto:", "tel:")


class LinkParser(HTMLParser):
    """Extrae enlaces y recursos declarados en HTML sin ejecutar JavaScript."""

    ATTRS: ClassVar[dict[str, str]] = {
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
        value = dict(attrs).get(wanted)
        if not value or value.startswith(IGNORED_PREFIXES):
            return
        self.links.add(urljoin(self.base_url, value))


def charset_from_content_type(content_type: str, default: str = "utf-8") -> str:
    """Obtiene la codificación declarada en un encabezado Content-Type."""
    if "charset=" not in content_type:
        return default
    return content_type.split("charset=", 1)[1].split(";", 1)[0].strip()


@register_collector("html_links")
def collect_html_links(source: Source, destination: Path) -> CollectionResult:
    """Descarga una página, filtra sus enlaces y escribe su procedencia."""
    response = http_get(source["url"])
    content_type = response.headers.get("content-type", "")
    html = response.body.decode(
        charset_from_content_type(content_type), errors="replace"
    )
    parser = LinkParser(response.final_url)
    parser.feed(html)
    extensions = {extension.lower() for extension in source.get("keep_extensions", [])}
    selected = sorted(
        link
        for link in parser.links
        if not extensions or Path(urlparse(link).path).suffix.lower() in extensions
    )
    fetched_at = utc_now()
    body = write_json(
        destination,
        {
            "source_id": source["id"],
            "source_url": source["url"],
            "final_url": response.final_url,
            "fetched_at": fetched_at,
            "links": selected,
        },
    )
    metadata: CollectionResult = {
        "source_id": source["id"],
        "source_name": source.get("name"),
        "authority": source.get("authority"),
        "source_type": source["type"],
        "source_url": source["url"],
        "final_url": response.final_url,
        "fetched_at": fetched_at,
        "record_count": len(selected),
        "http_status": response.status,
        "content_type": content_type,
        "sha256": sha256_bytes(body),
        "source_page_sha256": sha256_bytes(response.body),
        "license_note": source.get("license_note"),
        "quality_warnings": (
            ["El HTML contiene caracteres de reemplazo Unicode"]
            if REPLACEMENT_CHARACTER in html
            else []
        ),
    }
    write_json(provenance_path(destination), metadata)
    return metadata
