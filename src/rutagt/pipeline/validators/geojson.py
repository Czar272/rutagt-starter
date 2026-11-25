"""Validaciones de calidad para colecciones GeoJSON."""

import json
from typing import Any

REPLACEMENT_CHARACTER = "�"


def validate_geojson(collection: dict[str, Any], source: dict[str, Any]) -> list[str]:
    """Devuelve advertencias de calidad de una colección GeoJSON.

    Verifica tipos de geometría esperados, campos requeridos vacíos, caracteres
    de reemplazo Unicode y colecciones vacías. No modifica los datos.
    """
    warnings: list[str] = []
    features = collection.get("features", [])
    allowed = set(source.get("expected_geometry", []))
    required = set(source.get("required_fields", []))
    geometry_types: set[str] = set()
    missing_counts = dict.fromkeys(required, 0)
    replacement_characters = 0

    for feature in features:
        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type")
        if geometry_type:
            geometry_types.add(geometry_type)
        properties = feature.get("properties") or {}
        for field in required:
            if properties.get(field) in (None, ""):
                missing_counts[field] += 1
        replacement_characters += json.dumps(properties, ensure_ascii=False).count(
            REPLACEMENT_CHARACTER
        )

    unexpected = geometry_types - allowed if allowed else set()
    if unexpected:
        warnings.append(f"Geometrías no esperadas: {sorted(unexpected)}")
    for field, count in sorted(missing_counts.items()):
        if count:
            warnings.append(f"{count} registros sin el campo requerido {field}")
    if replacement_characters:
        warnings.append(
            f"Se encontraron {replacement_characters} caracteres de reemplazo Unicode; "
            "conservar el dato original y corregirlo en una capa normalizada."
        )
    if not features:
        warnings.append("La fuente no devolvió registros")
    return warnings
