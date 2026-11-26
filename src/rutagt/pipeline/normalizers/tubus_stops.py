"""Adaptador de las paradas de TuBus (`muniguate_tubus_stops_2025`).

Cada registro es una parada de una sola ruta (perfil B3). Además de la lectura
común de `muniguate_stops` (espacios, zona, código de ruta como texto), el
adaptador aplica estas reglas propias:

- los nombres genéricos «Parada NNN» (B1) se conservan, pero se marcan: el
  nombre visible se construirá con la dirección o una referencia cercana;
- el número del nombre no es un identificador (B2) ni define la secuencia (el
  spike de la ruta 801 encontró numeración corrida): se reporta cuando se
  repite dentro de una ruta y se usa solo como alerta;
- el sentido escrito en la dirección («... dirección norte») pasa a
  `direction_hint`.

La secuencia de paradas por ruta y sentido se reconcilia con los ruteros
oficiales en una etapa posterior, no en el adaptador.
"""

import re
from collections import defaultdict

from rutagt.pipeline.normalizers.base import RawInput, register_adapter
from rutagt.pipeline.normalizers.models import (
    Issue,
    Severity,
    StagedStop,
    StagingBatch,
)
from rutagt.pipeline.normalizers.muniguate_stops import adapt_stop_layer, issue

SOURCE_ID = "muniguate_tubus_stops_2025"

_GENERIC_NAME = re.compile(r"^Parada\s+(?P<number>\d+)$", re.IGNORECASE)
_ADDRESS_DIRECTION = re.compile(
    r"\bdirecci[oó]n\s+(?P<direction>norte|sur|este|oeste)\b", re.IGNORECASE
)


def generic_number(name: str) -> str | None:
    """Número de un nombre genérico «Parada NNN», sin ceros a la izquierda."""
    match = _GENERIC_NAME.match(name)
    return str(int(match.group("number"))) if match else None


def address_direction(address: str | None) -> str | None:
    """Sentido escrito en la dirección («dirección norte»), en minúsculas."""
    if address is None:
        return None
    match = _ADDRESS_DIRECTION.search(address)
    return match.group("direction").lower() if match else None


def _generic_names(stops: list[StagedStop]) -> list[Issue]:
    issues = []
    numbered: dict[tuple[str, str], list[str]] = defaultdict(list)
    for stop in stops:
        number = generic_number(stop.name)
        if number is None:
            continue
        issues.append(
            issue(
                Severity.INFO,
                "nombre_generico",
                f"Nombre genérico «{stop.name}»; el número solo sirve como pista",
                stop.source.external_id,
                numero=number,
            )
        )
        for route_code in stop.route_codes:
            numbered[(route_code, number)].append(stop.source.external_id)
    for (route_code, number), ids in sorted(numbered.items()):
        if len(ids) > 1:
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code="numero_repetido",
                    message=(
                        f"El número {number} aparece en {len(ids)} paradas "
                        f"de la ruta {route_code}"
                    ),
                    external_id=ids[0],
                    evidence={
                        "external_ids": ids,
                        "route_code": route_code,
                        "numero": number,
                    },
                )
            )
    return issues


@register_adapter(SOURCE_ID)
def adapt(raw: RawInput) -> StagingBatch:
    """Traduce la capa de paradas de TuBus a `StagedStop`."""
    stops, issues = adapt_stop_layer(raw)
    stops = [
        stop.model_copy(update={"direction_hint": direction})
        if (direction := address_direction(stop.address)) is not None
        else stop
        for stop in stops
    ]
    issues.extend(_generic_names(stops))
    return StagingBatch(
        source_id=raw.source_id,
        snapshot_id=raw.snapshot_id,
        records=tuple(stops),
        issues=tuple(issues),
    )
