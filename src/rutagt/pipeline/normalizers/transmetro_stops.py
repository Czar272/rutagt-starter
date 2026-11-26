"""Adaptador de las estaciones de Transmetro (`muniguate_transmetro_stops_2025`).

La capa municipal tiene un registro por estación **y línea** (perfil E1). El
adaptador produce un `StagedStop` por registro, que representa el andén de esa
línea, con la lectura común de `muniguate_stops` (espacios, zona, código de
ruta) y estas reglas propias:

- separa el sentido escrito en el nombre (E2): «Estación Mariscal Dirección
  Plaza Barrios» queda como nombre «Estación Mariscal» y sentido «Plaza
  Barrios»; también «Granai - Dir. La Merced»;
- quita el sufijo de líneas («Colón - Líneas 6 y 18»), que repite lo que dice
  `Codigoruta`;
- reporta andenes con el mismo nombre, sentido y línea en posiciones
  distintas (E6).

Agrupar los andenes en estaciones (`location_type = 1`) y asignar
identificadores canónicos es tarea del constructor canónico (ADR-0033).
"""

import re
from collections import defaultdict

from rutagt.pipeline.normalizers.base import RawInput, register_adapter
from rutagt.pipeline.normalizers.models import (
    Issue,
    Position,
    Severity,
    StagedStop,
    StagingBatch,
)
from rutagt.pipeline.normalizers.muniguate_stops import adapt_stop_layer

SOURCE_ID = "muniguate_transmetro_stops_2025"

_DIRECTION = re.compile(
    r"^(?P<name>.+?)\s+(?:-\s+Dir\.|Direcci[oó]n)\s+(?P<direction>.+)$",
    re.IGNORECASE,
)
_LINES_SUFFIX = re.compile(r"\s+-\s+L[ií]neas?\s+[\d\s,y]+$", re.IGNORECASE)


def split_name(name: str) -> tuple[str, str | None]:
    """Separa el nombre de la estación, el sufijo de líneas y el sentido."""
    name = _LINES_SUFFIX.sub("", name)
    match = _DIRECTION.match(name)
    if match is None:
        return name, None
    return match.group("name"), match.group("direction")


def _duplicate_directions(stops: list[StagedStop]) -> list[Issue]:
    """Andenes con el mismo nombre, sentido y línea en posiciones distintas."""
    groups: dict[tuple[str, str, str], list[StagedStop]] = defaultdict(list)
    for stop in stops:
        if stop.direction_hint is not None:
            for route_code in stop.route_codes:
                key = (stop.name, stop.direction_hint, route_code)
                groups[key].append(stop)
    issues = []
    for (name, direction, route_code), group in sorted(groups.items()):
        positions: set[Position] = {stop.position for stop in group}
        if len(positions) > 1:
            ids = [stop.source.external_id for stop in group]
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code="sentido_duplicado",
                    message=(
                        f"{name} dirección {direction} aparece en {len(positions)} "
                        f"posiciones de la ruta {route_code}"
                    ),
                    external_id=ids[0],
                    evidence={"external_ids": ids, "route_code": route_code},
                )
            )
    return issues


@register_adapter(SOURCE_ID)
def adapt(raw: RawInput) -> StagingBatch:
    """Traduce la capa de estaciones de Transmetro a `StagedStop`."""
    stops, issues = adapt_stop_layer(raw, split_name)
    issues.extend(_duplicate_directions(stops))
    return StagingBatch(
        source_id=raw.source_id,
        snapshot_id=raw.snapshot_id,
        records=tuple(stops),
        issues=tuple(issues),
    )
