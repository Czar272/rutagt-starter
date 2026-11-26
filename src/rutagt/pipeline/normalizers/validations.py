"""Validaciones geoespaciales de la capa staging y su severidad (ADR-0034).

Se ejecutan en el runner después de cada adaptador, sobre los registros ya
tipados, y devuelven `Issue`. No modifican registros: un problema `error`
impide pasar el lote a la capa canónica y hace fallar `rutagt-normalize`.

Reglas y severidad:

- `fuera_de_guatemala` (error): parada o vértice fuera de Guatemala.
- `fuera_de_cobertura` (warning): dentro de Guatemala, fuera del Área
  Metropolitana.
- `salto_en_trazado` (warning): vértices seguidos a más de `MAX_SEGMENT_M`.
- `trazado_corto` (warning): trazado de menos de `MIN_SHAPE_M`.
- `parada_lejos_de_ruta`: warning a más de `STOP_WARNING_M` del trazado de su
  ruta; error a más de `STOP_ERROR_M`.
- `ruta_sin_trazado` (warning): la fuente de trazados no tiene esa ruta.
"""

import itertools
from collections.abc import Iterable

from rutagt.core.geo import GUATEMALA_BOUNDS, METRO_AREA_BOUNDS, contains
from rutagt.pipeline.normalizers.common import (
    haversine_m,
    point_to_line_m,
)
from rutagt.pipeline.normalizers.models import (
    Issue,
    Position,
    Severity,
    StagedShape,
    StagedStop,
    StagingBatch,
)

MAX_SEGMENT_M = 1_500.0
"""Salto máximo entre vértices; el mayor observado en 2025 es de 652 m."""

MIN_SHAPE_M = 500.0
"""Longitud mínima razonable de un trazado urbano; el menor de 2025 mide 3,5 km."""

STOP_WARNING_M = 50.0
"""Distancia a la ruta a partir de la cual se alerta; el p99 de 2025 es de 22 m."""

STOP_ERROR_M = 500.0
"""Distancia a la ruta a partir de la cual la parada no puede ser de esa ruta."""


def _coverage(
    positions: Iterable[Position], external_id: str, entity: str
) -> list[Issue]:
    outside_country = outside_area = 0
    for lon, lat in positions:
        if not contains(GUATEMALA_BOUNDS, lon, lat):
            outside_country += 1
        elif not contains(METRO_AREA_BOUNDS, lon, lat):
            outside_area += 1
    issues = []
    if outside_country:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                code="fuera_de_guatemala",
                message=f"{entity} con {outside_country} posiciones fuera de Guatemala",
                external_id=external_id,
                evidence={"posiciones": outside_country},
            )
        )
    if outside_area:
        issues.append(
            Issue(
                severity=Severity.WARNING,
                code="fuera_de_cobertura",
                message=(
                    f"{entity} con {outside_area} posiciones fuera del Área "
                    "Metropolitana"
                ),
                external_id=external_id,
                evidence={"posiciones": outside_area},
            )
        )
    return issues


def _shape_checks(shape: StagedShape) -> list[Issue]:
    external_id = shape.source.external_id
    issues = _coverage(shape.coordinates, external_id, "Trazado")
    jumps = [
        round(distance)
        for a, b in itertools.pairwise(shape.coordinates)
        if (distance := haversine_m(a, b)) > MAX_SEGMENT_M
    ]
    if jumps:
        issues.append(
            Issue(
                severity=Severity.WARNING,
                code="salto_en_trazado",
                message=(
                    f"Trazado con {len(jumps)} saltos de más de {MAX_SEGMENT_M:.0f} m"
                ),
                external_id=external_id,
                evidence={"saltos_m": jumps},
            )
        )
    if shape.length_m < MIN_SHAPE_M:
        issues.append(
            Issue(
                severity=Severity.WARNING,
                code="trazado_corto",
                message=f"Trazado de {shape.length_m:.0f} m",
                external_id=external_id,
                evidence={"length_m": shape.length_m},
            )
        )
    return issues


def validate_batch(batch: StagingBatch) -> list[Issue]:
    """Validaciones que solo necesitan los registros del propio lote."""
    issues: list[Issue] = []
    for record in batch.records:
        if isinstance(record, StagedStop):
            issues.extend(
                _coverage([record.position], record.source.external_id, "Parada")
            )
        elif isinstance(record, StagedShape):
            issues.extend(_shape_checks(record))
    return issues


def shape_key(shape: StagedShape) -> str:
    """Código con el que las paradas se refieren al trazado.

    Las estaciones de Transmetro usan el código de la variante (`12001`); las
    paradas de TuBus, el de la ruta (`801`), que no tiene variantes.
    """
    return shape.variant_code or shape.route_code


def validate_stops_against_shapes(
    stops: StagingBatch, shapes: StagingBatch
) -> list[Issue]:
    """Distancia de cada parada al trazado de cada ruta que la sirve."""
    by_code = {
        shape_key(record): list(record.coordinates)
        for record in shapes.records
        if isinstance(record, StagedShape)
    }
    issues: list[Issue] = []
    missing: dict[str, list[str]] = {}
    for record in stops.records:
        if not isinstance(record, StagedStop):
            continue
        for code in record.route_codes:
            line = by_code.get(code)
            if line is None:
                missing.setdefault(code, []).append(record.source.external_id)
                continue
            distance = point_to_line_m(record.position, line)
            if distance <= STOP_WARNING_M:
                continue
            severity = Severity.ERROR if distance > STOP_ERROR_M else Severity.WARNING
            issues.append(
                Issue(
                    severity=severity,
                    code="parada_lejos_de_ruta",
                    message=(
                        f"{record.name} está a {distance:.0f} m del trazado "
                        f"de la ruta {code}"
                    ),
                    external_id=record.source.external_id,
                    evidence={"route_code": code, "distancia_m": round(distance, 1)},
                )
            )
    for code, ids in sorted(missing.items()):
        issues.append(
            Issue(
                severity=Severity.WARNING,
                code="ruta_sin_trazado",
                message=(
                    f"La ruta {code} de {len(ids)} paradas no tiene trazado en "
                    f"{shapes.source_id}"
                ),
                external_id=ids[0],
                evidence={"route_code": code, "external_ids": ids},
            )
        )
    return issues
