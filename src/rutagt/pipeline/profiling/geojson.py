"""Perfil de campos y geometrías de una colección GeoJSON.

Funciones puras: reciben la colección ya cargada y devuelven un diccionario
serializable con conteos, tipos, nulos, duplicados y anomalías. No modifican
los datos (ADR-0004).
"""

import json
from collections import Counter
from collections.abc import Iterator
from typing import Any

from rutagt.core.geo import GUATEMALA_BOUNDS, Bounds

# Secuencias típicas de UTF-8 leído como Latin-1 y el carácter de reemplazo.
ENCODING_MARKERS = ("Ã", "Â", "\ufffd")
# Un campo con hasta este número de valores distintos se considera un código.
CODE_MAX_DISTINCT = 15
TOP_VALUES = 5


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return type(value).__name__


def _sorted_counts(counter: Counter[str]) -> list[list[Any]]:
    """Pares `[valor, conteo]` del más al menos frecuente, con desempate estable."""
    return [
        [value, count]
        for value, count in sorted(counter.items(), key=lambda i: (-i[1], i[0]))
    ]


def profile_field(values: list[Any]) -> dict[str, Any]:
    """Perfil de un atributo a partir de sus valores (incluidos los ausentes)."""
    types = Counter(_type_name(v) for v in values)
    present = [v for v in values if v is not None and v != ""]
    keys = Counter(str(v) for v in present)
    repeated = Counter({k: c for k, c in keys.items() if c > 1})
    profile: dict[str, Any] = {
        "types": dict(sorted(types.items())),
        "null": types.get("null", 0),
        "empty": sum(1 for v in values if v == ""),
        "distinct": len(keys),
        "unique": len(keys) == len(present) and len(present) == len(values),
        "repeated_values": len(repeated),
        "top_repeated": _sorted_counts(repeated)[:TOP_VALUES],
    }
    if 0 < len(keys) <= CODE_MAX_DISTINCT:
        profile["values"] = _sorted_counts(keys)
    numbers = [
        v for v in present if isinstance(v, int | float) and not isinstance(v, bool)
    ]
    if numbers:
        profile["min"] = min(numbers)
        profile["max"] = max(numbers)
    strings = [v for v in present if isinstance(v, str)]
    if strings:
        lengths = [len(v) for v in strings]
        profile["length"] = [min(lengths), max(lengths)]
        profile["whitespace_issues"] = sum(
            1 for v in strings if v != v.strip() or "  " in v or "\u00a0" in v
        )
        profile["encoding_issues"] = sum(
            1 for v in strings if any(marker in v for marker in ENCODING_MARKERS)
        )
    return profile


def _positions(coordinates: Any) -> Iterator[tuple[float, float]]:
    """Recorre los pares (lon, lat) de cualquier geometría GeoJSON."""
    if (
        isinstance(coordinates, list)
        and len(coordinates) >= 2
        and all(isinstance(c, int | float) for c in coordinates[:2])
    ):
        yield float(coordinates[0]), float(coordinates[1])
    elif isinstance(coordinates, list):
        for item in coordinates:
            yield from _positions(item)


def profile_geometries(
    features: list[dict[str, Any]], bounds: Bounds = GUATEMALA_BOUNDS
) -> dict[str, Any]:
    """Tipos, faltantes, extensión, puntos fuera de límites y geometrías repetidas."""
    types: Counter[str] = Counter()
    missing = empty = outside = 0
    xs: list[float] = []
    ys: list[float] = []
    signatures: Counter[str] = Counter()
    min_x, min_y, max_x, max_y = bounds
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            missing += 1
            continue
        types[str(geometry.get("type"))] += 1
        positions = list(_positions(geometry.get("coordinates")))
        if not positions:
            empty += 1
            continue
        signatures[json.dumps(geometry.get("coordinates"))] += 1
        for x, y in positions:
            xs.append(x)
            ys.append(y)
        if any(not (min_x <= x <= max_x and min_y <= y <= max_y) for x, y in positions):
            outside += 1
    duplicated = [count for count in signatures.values() if count > 1]
    return {
        "types": dict(sorted(types.items())),
        "missing": missing,
        "empty": empty,
        "bbox": [min(xs), min(ys), max(xs), max(ys)] if xs else None,
        "outside_bounds": outside,
        "duplicate_groups": len(duplicated),
        "duplicate_records": sum(duplicated),
    }


def find_anomalies(profile: dict[str, Any]) -> list[str]:
    """Hallazgos legibles a partir de un perfil ya calculado."""
    anomalies: list[str] = []
    geometry = profile["geometry"]
    total = profile["records"]
    if total == 0:
        anomalies.append("La colección no tiene registros")
    if len(geometry["types"]) > 1:
        anomalies.append(f"Geometrías de varios tipos: {geometry['types']}")
    if geometry["missing"] or geometry["empty"]:
        anomalies.append(
            f"{geometry['missing']} registros sin geometría y "
            f"{geometry['empty']} con geometría vacía"
        )
    if geometry["outside_bounds"]:
        anomalies.append(
            f"{geometry['outside_bounds']} geometrías fuera de los límites de Guatemala"
        )
    if geometry["duplicate_groups"]:
        anomalies.append(
            f"{geometry['duplicate_records']} registros comparten geometría idéntica "
            f"en {geometry['duplicate_groups']} grupos"
        )
    for name, field in profile["fields"].items():
        if field["missing_key"]:
            anomalies.append(f"`{name}`: ausente en {field['missing_key']} registros")
        value_types = set(field["types"]) - {"null"}
        if len(value_types) > 1:
            anomalies.append(f"`{name}`: tipos mezclados {sorted(value_types)}")
        if field["null"] or field["empty"]:
            anomalies.append(
                f"`{name}`: {field['null']} nulos y {field['empty']} vacíos"
            )
        if field.get("whitespace_issues"):
            anomalies.append(
                f"`{name}`: {field['whitespace_issues']} valores con espacios "
                "al inicio, al final, dobles o no separables"
            )
        if field.get("encoding_issues"):
            anomalies.append(
                f"`{name}`: {field['encoding_issues']} valores con codificación dañada"
            )
    return anomalies


def profile_collection(
    collection: dict[str, Any], bounds: Bounds = GUATEMALA_BOUNDS
) -> dict[str, Any]:
    """Perfil completo de una colección: registros, geometrías, campos y anomalías."""
    features: list[dict[str, Any]] = collection.get("features") or []
    properties = [feature.get("properties") or {} for feature in features]
    names = list(dict.fromkeys(key for props in properties for key in props))
    fields: dict[str, Any] = {}
    for name in names:
        values = [props.get(name) for props in properties]
        fields[name] = {
            "missing_key": sum(1 for props in properties if name not in props),
            **profile_field(values),
        }
    profile: dict[str, Any] = {
        "records": len(features),
        "geometry": profile_geometries(features, bounds),
        "fields": fields,
    }
    profile["anomalies"] = find_anomalies(profile)
    return profile
