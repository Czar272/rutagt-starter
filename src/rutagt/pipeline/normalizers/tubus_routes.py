"""Adaptador de las rutas de TuBus (`muniguate_tubus_routes_2025`).

Cada registro es una ruta con su trazado; solo trae `FID`, `Codigoruta` y
`Shape__Length` (perfil T3). Por registro, el adaptador produce:

- un `StagedRoute` con `route_code` = `short_name` = `Codigoruta` como texto
  (T1, X1), el mismo valor que llevan las paradas en `route_codes`. No hay
  variantes, nombre largo ni sentido: provienen de los ruteros oficiales;
- un `StagedShape` con la longitud geodésica calculada, porque
  `Shape__Length` está medido en Web Mercator (T2).

Una ruta repetida en la capa es `error`: no hay forma de saber cuál trazado
es el vigente.
"""

import re
from collections import defaultdict
from typing import Any

from rutagt.pipeline.normalizers.base import RawInput, register_adapter
from rutagt.pipeline.normalizers.common import (
    external_id_of,
    features_of,
    issue,
    line_length_m,
    read_line,
)
from rutagt.pipeline.normalizers.models import (
    Issue,
    Severity,
    SourceRef,
    StagedRecord,
    StagedRoute,
    StagedShape,
    StagingBatch,
)

SOURCE_ID = "muniguate_tubus_routes_2025"

_ROUTE_CODE = re.compile(r"^\d+$")


def route_code_of(value: Any) -> str | None:
    """`Codigoruta` como texto sin espacios ni ceros a la izquierda, o `None`."""
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not _ROUTE_CODE.match(value.strip()):
        return None
    return str(int(value.strip()))


def _adapt_feature(
    feature: dict[str, Any], issues: list[Issue]
) -> tuple[StagedRoute, StagedShape] | None:
    props = feature.get("properties") or {}
    external_id = external_id_of(props, issues)
    if external_id is None:
        return None

    code = route_code_of(props.get("Codigoruta"))
    if code is None:
        issues.append(
            issue(
                Severity.ERROR,
                "codigo_invalido",
                "Codigoruta ausente o no es un número de ruta",
                external_id,
                Codigoruta=props.get("Codigoruta"),
            )
        )
        return None

    line = read_line(feature.get("geometry"), external_id, issues)
    if line is None:
        return None

    source = SourceRef(source_id=SOURCE_ID, external_id=external_id, raw=props)
    route = StagedRoute(source=source, route_code=code, short_name=code)
    shape = StagedShape(
        source=source,
        route_code=code,
        coordinates=tuple(line),
        length_m=round(line_length_m(line), 1),
    )
    return route, shape


@register_adapter(SOURCE_ID)
def adapt(raw: RawInput) -> StagingBatch:
    """Traduce la capa de rutas de TuBus a `StagedRoute` y `StagedShape`."""
    issues: list[Issue] = []
    adapted: dict[str, list[tuple[StagedRoute, StagedShape]]] = defaultdict(list)
    for feature in features_of(raw.content, issues):
        result = _adapt_feature(feature, issues)
        if result is not None:
            adapted[result[0].route_code].append(result)

    records: list[StagedRecord] = []
    for code, group in adapted.items():
        if len(group) > 1:
            ids = [route.source.external_id for route, _ in group]
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="ruta_repetida",
                    message=f"La ruta {code} aparece en {len(group)} registros",
                    external_id=ids[0],
                    evidence={"external_ids": ids, "route_code": code},
                )
            )
            continue
        records.extend(group[0])

    return StagingBatch(
        source_id=raw.source_id,
        snapshot_id=raw.snapshot_id,
        records=tuple(records),
        issues=tuple(issues),
    )
