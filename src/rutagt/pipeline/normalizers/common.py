"""Funciones puras compartidas por los adaptadores de fuente.

Ninguna corrige datos con criterio propio: limpian formato (espacios), leen
geometría GeoJSON y extraen información explícita del texto. Las correcciones
con evidencia viven en cada adaptador.
"""

import math
import re
from typing import Any

from rutagt.pipeline.normalizers.models import Position

_ADDRESS_ZONE = re.compile(r"\bzona\s*(\d{1,2})\b", re.IGNORECASE)


def clean_spaces(text: str) -> str:
    """Quita espacios al inicio y al final y colapsa los repetidos.

    `str.split()` sin argumentos separa también por espacios no separables y
    otros espacios Unicode, así que también se normalizan.
    """
    return " ".join(text.split())


def clean_optional(value: Any) -> str | None:
    """Texto limpio, o `None` si el valor no es texto o queda vacío."""
    if not isinstance(value, str):
        return None
    return clean_spaces(value) or None


def address_zone(address: str | None) -> str | None:
    """Zona escrita en una dirección («... zona 12»), si la hay."""
    if address is None:
        return None
    match = _ADDRESS_ZONE.search(address)
    return str(int(match.group(1))) if match else None


def point_position(geometry: Any) -> Position | None:
    """Posición `(lon, lat)` de un `Point` GeoJSON válido, o `None`."""
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None
    lon, lat = coordinates[0], coordinates[1]
    if not all(
        isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
        for v in (lon, lat)
    ):
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return float(lon), float(lat)
