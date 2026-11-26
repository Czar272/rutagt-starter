"""Adaptador de las estaciones de Transmetro (`muniguate_transmetro_stops_2025`).

La capa municipal tiene un registro por estación **y línea** (perfil E1), con
`FID`, `Nombre_lug`, `Direccion`, `Zona` y `Codigoruta`. El adaptador produce
un `StagedStop` por registro, que representa el andén de esa línea:

- limpia espacios del nombre y la dirección (E5) y conserva el texto original
  en `source.raw`;
- separa el sentido escrito en el nombre (E2): «Estación Mariscal Dirección
  Plaza Barrios» queda como nombre «Estación Mariscal» y sentido «Plaza
  Barrios»; también «Granai - Dir. La Merced»;
- quita el sufijo de líneas («Colón - Líneas 6 y 18»), que repite lo que dice
  `Codigoruta`;
- conserva `Zona` y reporta cuando contradice la zona de la dirección (E3).

Agrupar los andenes en estaciones (`location_type = 1`) y asignar
identificadores canónicos es tarea del constructor canónico (ADR-0033).
"""

import re
from collections import defaultdict
from typing import Any

from rutagt.pipeline.normalizers.base import RawInput, register_adapter
from rutagt.pipeline.normalizers.common import (
    address_zone,
    clean_optional,
    point_position,
)
from rutagt.pipeline.normalizers.models import (
    Issue,
    Position,
    Severity,
    SourceRef,
    StagedStop,
    StagingBatch,
)

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


def _issue(
    severity: Severity, code: str, message: str, external_id: str, **evidence: Any
) -> Issue:
    return Issue(
        severity=severity,
        code=code,
        message=message,
        external_id=external_id,
        evidence=evidence,
    )


def _adapt_feature(feature: dict[str, Any], issues: list[Issue]) -> StagedStop | None:
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

    position = point_position(feature.get("geometry"))
    if position is None:
        issues.append(
            _issue(
                Severity.ERROR,
                "geometria_invalida",
                "La geometría no es un punto con coordenadas válidas",
                external_id,
                geometry=feature.get("geometry"),
            )
        )
        return None

    original_name = props.get("Nombre_lug")
    cleaned_name = clean_optional(original_name)
    if cleaned_name is None:
        issues.append(
            _issue(Severity.ERROR, "sin_nombre", "Registro sin nombre", external_id)
        )
        return None
    name, direction = split_name(cleaned_name)

    original_address = props.get("Direccion")
    address = clean_optional(original_address)
    for field, original, cleaned in (
        ("Nombre_lug", original_name, cleaned_name),
        ("Direccion", original_address, address),
    ):
        if isinstance(original, str) and original != cleaned:
            issues.append(
                _issue(
                    Severity.INFO,
                    "espacios_anomalos",
                    f"{field} tenía espacios repetidos, no separables o en los bordes",
                    external_id,
                    field=field,
                    original=original,
                )
            )

    zone = _zone(props.get("Zona"), address, external_id, issues)

    route_code = props.get("Codigoruta")
    route_codes: tuple[str, ...] = ()
    if isinstance(route_code, int) and not isinstance(route_code, bool):
        route_codes = (str(route_code),)
    else:
        issues.append(
            _issue(
                Severity.WARNING,
                "sin_ruta",
                "Codigoruta ausente o no numérico",
                external_id,
                Codigoruta=route_code,
            )
        )

    return StagedStop(
        source=SourceRef(source_id=SOURCE_ID, external_id=external_id, raw=props),
        name=name,
        position=position,
        address=address,
        zone=zone,
        route_codes=route_codes,
        direction_hint=direction,
    )


def _zone(
    value: Any, address: str | None, external_id: str, issues: list[Issue]
) -> str | None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        issues.append(
            _issue(
                Severity.WARNING,
                "zona_invalida",
                "Zona ausente o no es un número positivo",
                external_id,
                Zona=value,
            )
        )
        return None
    zone = str(value)
    from_address = address_zone(address)
    if from_address is not None and from_address != zone:
        # Ninguno de los dos es confiable por sí solo (perfil E3): se conserva
        # el campo y se marca para resolverlo con los polígonos de zonas.
        issues.append(
            _issue(
                Severity.WARNING,
                "zona_discrepante",
                f"Zona {zone} contradice la dirección (zona {from_address})",
                external_id,
                zona=zone,
                zona_direccion=from_address,
            )
        )
    return zone


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

    stops = []
    for feature in features:
        stop = _adapt_feature(feature if isinstance(feature, dict) else {}, issues)
        if stop is not None:
            stops.append(stop)
    issues.extend(_duplicate_directions(stops))

    return StagingBatch(
        source_id=raw.source_id,
        snapshot_id=raw.snapshot_id,
        records=tuple(stops),
        issues=tuple(issues),
    )
