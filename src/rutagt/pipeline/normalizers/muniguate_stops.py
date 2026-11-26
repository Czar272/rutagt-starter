"""Lectura común de las capas de paradas de la Municipalidad de Guatemala.

Las capas de Transmetro y TuBus publican los mismos campos (`FID`,
`Nombre_lug`, `Direccion`, `Zona`, `Codigoruta`) con un punto por registro.
Este módulo traduce cada registro a un `StagedStop` y reporta los problemas
comunes (perfil E3, E5, B5, B6). Las reglas propias de cada dataset, como el
sentido escrito en el nombre de Transmetro, viven en su adaptador.
"""

from collections.abc import Callable
from typing import Any

from rutagt.pipeline.normalizers.base import RawInput
from rutagt.pipeline.normalizers.common import (
    address_zone,
    clean_optional,
    issue,
    point_position,
)
from rutagt.pipeline.normalizers.models import Issue, Severity, SourceRef, StagedStop

NameParser = Callable[[str], tuple[str, str | None]]
"""Separa un nombre limpio en nombre de parada y sentido (o `None`)."""


def keep_name(name: str) -> tuple[str, str | None]:
    """Parser por omisión: el nombre no lleva sentido."""
    return name, None


def _zone(
    value: Any, address: str | None, external_id: str, issues: list[Issue]
) -> str | None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        issues.append(
            issue(
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
            issue(
                Severity.WARNING,
                "zona_discrepante",
                f"Zona {zone} contradice la dirección (zona {from_address})",
                external_id,
                zona=zone,
                zona_direccion=from_address,
            )
        )
    return zone


def adapt_feature(
    feature: dict[str, Any],
    source_id: str,
    split_name: NameParser,
    issues: list[Issue],
) -> StagedStop | None:
    """Traduce un registro; devuelve `None` si no es utilizable (`error`)."""
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
            issue(
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
            issue(Severity.ERROR, "sin_nombre", "Registro sin nombre", external_id)
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
                issue(
                    Severity.INFO,
                    "espacios_anomalos",
                    f"{field} tenía espacios repetidos, no separables o en los bordes",
                    external_id,
                    field=field,
                    original=original,
                )
            )

    zone = _zone(props.get("Zona"), address, external_id, issues)

    # El código se une siempre como texto: TuBus lo publica como número en
    # paradas y como texto en rutas (perfil X1).
    route_code = props.get("Codigoruta")
    route_codes: tuple[str, ...] = ()
    if isinstance(route_code, int) and not isinstance(route_code, bool):
        route_codes = (str(route_code),)
    else:
        issues.append(
            issue(
                Severity.WARNING,
                "sin_ruta",
                "Codigoruta ausente o no numérico",
                external_id,
                Codigoruta=route_code,
            )
        )

    return StagedStop(
        source=SourceRef(source_id=source_id, external_id=external_id, raw=props),
        name=name,
        position=position,
        address=address,
        zone=zone,
        route_codes=route_codes,
        direction_hint=direction,
    )


def adapt_stop_layer(
    raw: RawInput, split_name: NameParser = keep_name
) -> tuple[list[StagedStop], list[Issue]]:
    """Traduce todos los registros de una capa de paradas municipal."""
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
        return [], issues

    stops = []
    for feature in features:
        stop = adapt_feature(
            feature if isinstance(feature, dict) else {},
            raw.source_id,
            split_name,
            issues,
        )
        if stop is not None:
            stops.append(stop)
    return stops, issues
