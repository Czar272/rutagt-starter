"""Collectors: descargan fuentes externas a la capa `data/raw/`.

Importar este paquete registra los collectors incluidos en RutaGT.
"""

from rutagt.pipeline.collectors import arcgis, html_links
from rutagt.pipeline.collectors.base import (
    collect_source,
    register_collector,
    registered_types,
)

__all__ = [
    "arcgis",
    "collect_source",
    "html_links",
    "register_collector",
    "registered_types",
]
