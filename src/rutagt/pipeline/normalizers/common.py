"""Funciones puras compartidas por los adaptadores de fuente.

Ninguna corrige datos con criterio propio: limpian formato (espacios), leen
geometría GeoJSON y extraen información explícita del texto. Las correcciones
con evidencia viven en cada adaptador.
"""

import itertools
import math
import re
from typing import Any

from rutagt.pipeline.normalizers.models import Issue, Position, Severity

_ADDRESS_ZONE = re.compile(r"\bzona\s*(\d{1,2})\b", re.IGNORECASE)

EARTH_RADIUS_M = 6_371_008.8
"""Radio medio de la Tierra (IUGG), suficiente para longitudes de rutas urbanas."""

JOIN_TOLERANCE_M = 1.0
"""Separación máxima entre el final de un tramo y el inicio del siguiente."""


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


def position(value: Any) -> Position | None:
    """Posición `(lon, lat)` de una coordenada GeoJSON válida, o `None`."""
    if not isinstance(value, list) or len(value) < 2:
        return None
    lon, lat = value[0], value[1]
    if not all(
        isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
        for v in (lon, lat)
    ):
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return float(lon), float(lat)


def point_position(geometry: Any) -> Position | None:
    """Posición de un `Point` GeoJSON válido, o `None`."""
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        return None
    return position(geometry.get("coordinates"))


def line_positions(value: Any) -> list[Position] | None:
    """Posiciones de las coordenadas de un `LineString`, o `None` si alguna falla."""
    if not isinstance(value, list) or len(value) < 2:
        return None
    positions = [position(item) for item in value]
    if any(p is None for p in positions):
        return None
    return [p for p in positions if p is not None]


def haversine_m(a: Position, b: Position) -> float:
    """Distancia geodésica aproximada en metros entre dos posiciones."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def line_length_m(positions: list[Position]) -> float:
    """Longitud geodésica de una línea en metros."""
    return sum(haversine_m(a, b) for a, b in itertools.pairwise(positions))


def chain_segments(
    segments: list[list[Position]], tolerance_m: float = JOIN_TOLERANCE_M
) -> tuple[list[Position], list[tuple[int, bool]]] | None:
    """Une tramos en una sola línea continua que los recorre todos una vez.

    Prueba primero el orden y el sentido originales y retrocede solo cuando un
    tramo no continúa donde termina el anterior. Devuelve la línea y el orden
    usado (`(índice, invertido)`), o `None` si los tramos no se pueden unir.
    """
    used = [False] * len(segments)
    order: list[tuple[int, bool]] = []

    def oriented(index: int, reverse: bool) -> list[Position]:
        segment = segments[index]
        return segment[::-1] if reverse else segment

    def search(end: Position) -> bool:
        if len(order) == len(segments):
            return True
        for index in range(len(segments)):
            if used[index]:
                continue
            for reverse in (False, True):
                candidate = oriented(index, reverse)
                if haversine_m(end, candidate[0]) <= tolerance_m:
                    used[index] = True
                    order.append((index, reverse))
                    if search(candidate[-1]):
                        return True
                    used[index] = False
                    order.pop()
        return False

    if not segments:
        return None
    used[0] = True
    order.append((0, False))
    if not search(segments[0][-1]):
        return None
    line = list(segments[0])
    for index, reverse in order[1:]:
        line.extend(oriented(index, reverse)[1:])
    return line, order


def issue(
    severity: Severity, code: str, message: str, external_id: str, **evidence: Any
) -> Issue:
    """Problema de un registro con su evidencia."""
    return Issue(
        severity=severity,
        code=code,
        message=message,
        external_id=external_id,
        evidence=evidence,
    )
