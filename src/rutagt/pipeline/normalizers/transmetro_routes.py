"""Adaptador de las rutas de Transmetro (`muniguate_transmetro_routes_2025`).

Cada registro es una línea o una variante con su trazado (`FID`, `Nombre`,
`Codigoruta`, `Shape__Length`). Por registro, el adaptador produce:

- un `StagedRoute`, el patrón preliminar: `route_code` es la línea y
  `variant_code` el `Codigoruta` completo, el mismo código que llevan las
  estaciones en `route_codes`. El código sigue la regla línea × 1000 +
  variante (perfil P1), que falta confirmar con la Municipalidad;
- un `StagedShape` con la longitud geodésica calculada, porque
  `Shape__Length` está medido en Web Mercator (P4).

Además:

- une los tramos de un `MultiLineString` en una sola línea continua (P3) y
  deja en el problema el orden usado, para poder auditarlo;
- corrige errores ortográficos del nombre (P5) y conserva el original en
  `source.raw`;
- marca las variantes que comparten trazado con otras (P2). Reutilizar un
  único `shape` para varios patrones es tarea del constructor canónico.
"""

import re
from collections import defaultdict
from typing import Any

from rutagt.pipeline.normalizers.base import RawInput, register_adapter
from rutagt.pipeline.normalizers.common import (
    chain_segments,
    clean_optional,
    issue,
    line_length_m,
    line_positions,
)
from rutagt.pipeline.normalizers.models import (
    Issue,
    Position,
    Severity,
    SourceRef,
    StagedRecord,
    StagedRoute,
    StagedShape,
    StagingBatch,
)

SOURCE_ID = "muniguate_transmetro_routes_2025"

VARIANT_BASE = 1000
"""`Codigoruta` = línea × 1000 + variante (perfil P1)."""

SPELLING = {
    re.compile(r"\bExtención\b"): "Extensión",
    re.compile(r"\bExpres\b"): "Exprés",
}
"""Correcciones ortográficas del nombre (perfil P5), versionadas con el código."""

_LINE_IN_NAME = re.compile(r"^L[ií]nea\s+(?P<line>\d+)\b", re.IGNORECASE)


def correct_spelling(name: str) -> str:
    """Nombre con las correcciones ortográficas conocidas aplicadas."""
    for pattern, replacement in SPELLING.items():
        name = pattern.sub(replacement, name)
    return name


def _geometry(
    geometry: Any, external_id: str, issues: list[Issue]
) -> list[Position] | None:
    kind = geometry.get("type") if isinstance(geometry, dict) else None
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if kind == "LineString":
        line = line_positions(coordinates)
    elif kind == "MultiLineString" and isinstance(coordinates, list):
        segments = [line_positions(segment) for segment in coordinates]
        valid = [segment for segment in segments if segment is not None]
        if not valid or len(valid) != len(segments):
            line = None
        elif (chained := chain_segments(valid)) is None:
            issues.append(
                issue(
                    Severity.ERROR,
                    "tramos_discontinuos",
                    "Los tramos del MultiLineString no forman una línea continua",
                    external_id,
                    tramos=len(segments),
                )
            )
            return None
        else:
            line, order = chained
            issues.append(
                issue(
                    Severity.INFO,
                    "tramos_unidos",
                    f"{len(segments)} tramos unidos en una sola línea",
                    external_id,
                    orden=[{"tramo": i, "invertido": r} for i, r in order],
                )
            )
    else:
        line = None
    if line is None:
        issues.append(
            issue(
                Severity.ERROR,
                "geometria_invalida",
                "La geometría no es una línea con coordenadas válidas",
                external_id,
                tipo=kind,
            )
        )
    return line


def _adapt_feature(
    feature: dict[str, Any], issues: list[Issue]
) -> tuple[StagedRoute, StagedShape] | None:
    props = feature.get("properties") or {}
    fid = props.get("FID")
    external_id = str(fid) if isinstance(fid, int | str) and fid != "" else ""
    if not external_id:
        issues.append(
            Issue(
                severity=Severity.ERROR,
                code="sin_identificador",
                message="Registro sin FID",
                evidence={"properties": props},
            )
        )
        return None

    code = props.get("Codigoruta")
    if not isinstance(code, int) or isinstance(code, bool) or code < VARIANT_BASE:
        issues.append(
            issue(
                Severity.ERROR,
                "codigo_invalido",
                f"Codigoruta no sigue la regla línea × {VARIANT_BASE} + variante",
                external_id,
                Codigoruta=code,
            )
        )
        return None
    line_code = str(code // VARIANT_BASE)

    line = _geometry(feature.get("geometry"), external_id, issues)
    if line is None:
        return None

    original_name = props.get("Nombre")
    cleaned = clean_optional(original_name)
    long_name = correct_spelling(cleaned) if cleaned else None
    if cleaned is not None and long_name != cleaned:
        issues.append(
            issue(
                Severity.INFO,
                "nombre_corregido",
                f"Nombre corregido: «{cleaned}» → «{long_name}»",
                external_id,
                original=original_name,
                corregido=long_name,
            )
        )
    match = _LINE_IN_NAME.match(cleaned or "")
    if match and str(int(match.group("line"))) != line_code:
        issues.append(
            issue(
                Severity.WARNING,
                "codigo_contradice_nombre",
                f"Codigoruta {code} no corresponde a «{cleaned}»",
                external_id,
                Codigoruta=code,
                linea_nombre=match.group("line"),
            )
        )

    source = SourceRef(source_id=SOURCE_ID, external_id=external_id, raw=props)
    route = StagedRoute(
        source=source,
        route_code=line_code,
        variant_code=str(code),
        short_name=line_code,
        long_name=long_name,
    )
    shape = StagedShape(
        source=source,
        route_code=line_code,
        variant_code=str(code),
        coordinates=tuple(line),
        length_m=round(line_length_m(line), 1),
    )
    return route, shape


def _shared_shapes(shapes: list[StagedShape]) -> list[Issue]:
    """Variantes con exactamente el mismo trazado que otras (perfil P2)."""
    groups: dict[tuple[Position, ...], list[StagedShape]] = defaultdict(list)
    for shape in shapes:
        groups[shape.coordinates].append(shape)
    issues = []
    for group in groups.values():
        if len(group) > 1:
            codes = [shape.variant_code for shape in group]
            issues.append(
                Issue(
                    severity=Severity.INFO,
                    code="trazado_compartido",
                    message=f"Las variantes {', '.join(map(str, codes))} "
                    "tienen el mismo trazado",
                    external_id=group[0].source.external_id,
                    evidence={
                        "external_ids": [s.source.external_id for s in group],
                        "variant_codes": codes,
                    },
                )
            )
    return issues


@register_adapter(SOURCE_ID)
def adapt(raw: RawInput) -> StagingBatch:
    """Traduce la capa de rutas de Transmetro a `StagedRoute` y `StagedShape`."""
    issues: list[Issue] = []
    features = raw.content.get("features") if isinstance(raw.content, dict) else None
    if not isinstance(features, list):
        issues.append(
            Issue(
                severity=Severity.ERROR,
                code="sin_features",
                message="El contenido no es un FeatureCollection con features",
            )
        )
        features = []

    records: list[StagedRecord] = []
    shapes: list[StagedShape] = []
    for feature in features:
        adapted = _adapt_feature(feature if isinstance(feature, dict) else {}, issues)
        if adapted is not None:
            route, shape = adapted
            records.extend((route, shape))
            shapes.append(shape)
    issues.extend(_shared_shapes(shapes))

    return StagingBatch(
        source_id=raw.source_id,
        snapshot_id=raw.snapshot_id,
        records=tuple(records),
        issues=tuple(issues),
    )
