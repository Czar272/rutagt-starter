"""Secuencia de paradas de cada variante (ADR-0036).

Las capas municipales dicen qué variantes sirven a cada parada, pero no en qué
orden. La secuencia se construye así:

1. **Proyección**: cada parada de la variante se ubica a lo largo de su
   trazado (metros desde el inicio). El orden por esa posición es la
   secuencia `probable` cuando no hay rutero, con la incidencia
   `secuencia_sin_rutero`.
2. **Rutero oficial**: si la variante tiene rutero transcrito, cada parada del
   rutero se asigna a una parada distinta de la capa con una alineación
   monótona sobre el orden proyectado (programación dinámica), por similitud
   de dirección que distingue números de vía. El número de «Parada NNN» no se
   usa: en la ruta 801 está corrido entre 094 y 104. En un circuito se prueba
   cada punto de inicio del recorrido y se elige el de mejor alineación.
   Si el rutero trae la revisión manual (`layer_external_id`), la
   asignación se confirma contra ella; si no, la dirección debe coincidir
   (puntaje ≥ `MATCH_THRESHOLD`). Una asignación confirmada da una secuencia
   `official`; una sin confirmar, `probable`.

Reimplementa el reconciliador del spike de la ruta 801 (RGT-128), que
reprodujo la revisión manual 47 de 47.
"""

import itertools
import math
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from rutagt.pipeline.canonical.models import (
    PatternStop,
    Position,
    Quality,
    Rutero,
    Shape,
    Stop,
)
from rutagt.pipeline.normalizers.common import EARTH_RADIUS_M, haversine_m

TEXT_WEIGHT = 0.6
NUMBER_WEIGHT = 0.4
NEUTRAL_NUMBER_SCORE = 0.5
"""Puntaje de números de vía cuando una de las direcciones no tiene."""

MATCH_THRESHOLD = 0.75
"""Similitud de dirección desde la que la asignación no requiere revisión."""

CLOSED_SHAPE_M = 50.0
"""Distancia entre los extremos del trazado hasta la que se trata como circuito."""

_ABBREVIATIONS = {
    "avenida": "av",
    "calzada": "calz",
    "bulevar": "blvr",
    "colonia": "col",
    "condominio": "cond",
}
_STREET_TYPES = {
    "calle": "calle",
    "av": "av",
    "diag": "diagonal",
    "diagonal": "diagonal",
}
_STREET = r"(calle|av|diag|diagonal)"
_NUMBER_BEFORE = re.compile(rf"\b(\d+)\s*(?:a|va|ta|o|ra|da)?\s+{_STREET}\b")
_NUMBER_AFTER = re.compile(rf"\b{_STREET}\s+(\d+)\b")


def normalize_address(value: str | None) -> str:
    """Dirección sin tildes ni signos, en minúsculas y con abreviaturas comunes."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char)).lower()
    for word, abbreviation in _ABBREVIATIONS.items():
        text = re.sub(rf"\b{word}\b", abbreviation, text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def street_numbers(address: str | None) -> set[tuple[str, str]]:
    """Pares (número, tipo de vía) de una dirección: «8a avenida» da `("8", "av")`."""
    text = normalize_address(address)
    numbers = {
        (str(int(number)), _STREET_TYPES[kind])
        for number, kind in _NUMBER_BEFORE.findall(text)
    }
    numbers |= {
        (str(int(number)), _STREET_TYPES[kind])
        for kind, number in _NUMBER_AFTER.findall(text)
    }
    return numbers


def number_agreement(left: str | None, right: str | None) -> float:
    """Coincidencia de números de vía (Jaccard); neutral si alguna no tiene."""
    a, b = street_numbers(left), street_numbers(right)
    if not a or not b:
        return NEUTRAL_NUMBER_SCORE
    return len(a & b) / len(a | b)


def address_score(official: str | None, record: str | None) -> float:
    """Similitud combinada de texto normalizado y números de vía, entre 0 y 1."""
    text = SequenceMatcher(None, normalize_address(official), normalize_address(record))
    return TEXT_WEIGHT * text.ratio() + NUMBER_WEIGHT * number_agreement(
        official, record
    )


def align_in_order(scores: Sequence[Sequence[float]]) -> tuple[list[int], float]:
    """Asigna cada fila a una columna distinta, en orden creciente.

    Maximiza la suma de puntajes: `best[i][j]` es el mejor total asignando las
    primeras `i` filas con las primeras `j` columnas. Devuelve la columna de
    cada fila y el total. Las columnas que no convienen quedan sin asignar.
    """
    rows = len(scores)
    columns = len(scores[0]) if rows else 0
    if columns < rows:
        raise ValueError("Hay menos paradas en la capa que en el rutero")
    best = [[-math.inf] * (columns + 1) for _ in range(rows + 1)]
    best[0] = [0.0] * (columns + 1)
    for i in range(1, rows + 1):
        for j in range(i, columns + 1):
            best[i][j] = max(best[i][j - 1], best[i - 1][j - 1] + scores[i - 1][j - 1])
    assignment = [0] * rows
    i, j = rows, columns
    while i > 0:
        if j > i and best[i][j] == best[i][j - 1]:
            j -= 1
        else:
            assignment[i - 1] = j - 1
            i -= 1
            j -= 1
    return assignment, best[rows][columns]


@dataclass(frozen=True)
class Projection:
    """Ubicación de un punto a lo largo de un trazado."""

    position_m: float
    """Metros recorridos sobre el trazado hasta el punto proyectado."""
    offset_m: float
    """Distancia perpendicular del punto al trazado."""


def project(point: Position, line: Sequence[Position]) -> Projection:
    """Proyecta un punto sobre el segmento más cercano de una línea.

    Usa un plano local equirectangular centrado en el punto para elegir el
    segmento y la fracción recorrida, y longitudes geodésicas para acumular la
    distancia, igual que `distance_m` del trazado.
    """
    lat0 = math.radians(point[1])
    meters_lon = math.radians(1) * EARTH_RADIUS_M * math.cos(lat0)
    meters_lat = math.radians(1) * EARTH_RADIUS_M
    best = Projection(position_m=0.0, offset_m=math.inf)
    travelled = 0.0
    for a, b in itertools.pairwise(line):
        ax, ay = (a[0] - point[0]) * meters_lon, (a[1] - point[1]) * meters_lat
        bx, by = (b[0] - point[0]) * meters_lon, (b[1] - point[1]) * meters_lat
        dx, dy = bx - ax, by - ay
        squared = dx * dx + dy * dy
        t = 0.0 if squared == 0 else min(1.0, max(0.0, -(ax * dx + ay * dy) / squared))
        offset = math.hypot(ax + t * dx, ay + t * dy)
        segment = haversine_m(a, b)
        if offset < best.offset_m:
            best = Projection(position_m=travelled + t * segment, offset_m=offset)
        travelled += segment
    return best


@dataclass(frozen=True)
class Assignment:
    """Parada del rutero asignada a una parada de la capa."""

    sequence: int
    stop_code: str
    stop: Stop
    score: float
    reviewed: str | None
    """Registro que asignó la revisión manual, si la hubo."""

    @property
    def confirmed(self) -> bool:
        """La revisión manual o, sin ella, la dirección respaldan la asignación."""
        if self.reviewed is not None:
            return self.reviewed in {r.external_id for r in self.stop.records}
        return self.score >= MATCH_THRESHOLD


@dataclass(frozen=True)
class SequenceResult:
    """Secuencia de una variante y lo que quedó por revisar."""

    pattern_stops: list[PatternStop]
    assignments: list[Assignment]
    unassigned: list[Stop]
    """Paradas de la capa que sirven a la variante pero no están en el rutero."""


def is_circuit(shape: Shape) -> bool:
    """Indica si el trazado termina donde empieza."""
    return haversine_m(shape.coordinates[0], shape.coordinates[-1]) <= CLOSED_SHAPE_M


def _monotonic(distances: list[float]) -> bool:
    return all(a <= b for a, b in itertools.pairwise(distances))


def _pattern_stops(
    pattern_id: str,
    ordered: list[tuple[Stop, float]],
    qualities: list[Quality],
) -> list[PatternStop]:
    distances = [round(position, 2) for _, position in ordered]
    # GTFS exige `shape_dist_traveled` creciente; un recorrido que empieza a
    # mitad de un circuito no la cumple y la deja vacía.
    keep = _monotonic(distances)
    return [
        PatternStop(
            pattern_id=pattern_id,
            stop_id=stop.stop_id,
            stop_sequence=number,
            shape_dist_traveled_m=distance if keep else None,
            sequence_quality=quality,
        )
        for number, ((stop, _), distance, quality) in enumerate(
            zip(ordered, distances, qualities, strict=True), start=1
        )
    ]


def by_projection(shape: Shape, stops: Sequence[Stop]) -> list[tuple[Stop, float]]:
    """Paradas ordenadas por su posición sobre el trazado (empates por id)."""
    positions = [(stop, project(stop.location, shape.coordinates)) for stop in stops]
    return [
        (stop, projection.position_m)
        for stop, projection in sorted(
            positions, key=lambda item: (item[1].position_m, item[0].stop_id)
        )
    ]


def sequence_without_rutero(
    pattern_id: str, shape: Shape, stops: Sequence[Stop]
) -> SequenceResult:
    """Secuencia `probable` por posición sobre el trazado."""
    ordered = by_projection(shape, stops)
    return SequenceResult(
        pattern_stops=_pattern_stops(
            pattern_id, ordered, [Quality.PROBABLE] * len(ordered)
        ),
        assignments=[],
        unassigned=[],
    )


def sequence_with_rutero(
    pattern_id: str, shape: Shape, stops: Sequence[Stop], rutero: Rutero
) -> SequenceResult:
    """Secuencia del rutero, con cada parada asignada a una parada de la capa.

    Lanza `ValueError` si la capa tiene menos paradas que el rutero.
    """
    ordered = by_projection(shape, stops)
    scores = [
        [address_score(stop.address, record.address) for record, _ in ordered]
        for stop in rutero.stops
    ]

    def alignment(start: int) -> tuple[float, int, list[int]]:
        columns, total = align_in_order([row[start:] + row[:start] for row in scores])
        # En empate gana el inicio más cercano al del trazado.
        return total, -start, columns

    starts = range(len(ordered)) if is_circuit(shape) else range(1)
    _, negative_start, columns = max(
        (alignment(start) for start in starts), key=lambda item: item[:2]
    )
    start = -negative_start
    rotated = ordered[start:] + ordered[:start]

    assignments = []
    chosen = []
    for official, column in zip(rutero.stops, columns, strict=True):
        stop, position = rotated[column]
        score = address_score(official.address, stop.address)
        assignments.append(
            Assignment(
                official.sequence,
                official.stop_code,
                stop,
                round(score, 3),
                official.layer_external_id,
            )
        )
        chosen.append((stop, position))
    used = set(columns)
    return SequenceResult(
        pattern_stops=_pattern_stops(
            pattern_id,
            chosen,
            [
                Quality.OFFICIAL if a.confirmed else Quality.PROBABLE
                for a in assignments
            ],
        ),
        assignments=assignments,
        unassigned=[
            stop for index, (stop, _) in enumerate(rotated) if index not in used
        ],
    )
