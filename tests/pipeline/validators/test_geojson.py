"""Pruebas de las validaciones de calidad de GeoJSON."""

from rutagt.pipeline.validators.geojson import validate_geojson


def test_reports_missing_fields_and_bad_encoding() -> None:
    collection = {
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [-90.5, 14.6]},
                "properties": {"Nombre_lug": "Estaci�n", "Codigoruta": None},
            }
        ]
    }
    source = {
        "expected_geometry": ["Point"],
        "required_fields": ["Nombre_lug", "Codigoruta"],
    }

    warnings = validate_geojson(collection, source)

    assert "1 registros sin el campo requerido Codigoruta" in warnings
    assert any("Unicode" in warning for warning in warnings)


def test_rejects_unexpected_geometry() -> None:
    collection = {
        "features": [
            {"geometry": {"type": "LineString", "coordinates": []}, "properties": {}}
        ]
    }

    warnings = validate_geojson(
        collection, {"expected_geometry": ["Point"], "required_fields": []}
    )

    assert warnings == ["Geometrías no esperadas: ['LineString']"]


def test_accepts_valid_collection() -> None:
    collection = {
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [-90.5, 14.6]},
                "properties": {"Nombre_lug": "Estación"},
            }
        ]
    }

    assert validate_geojson(collection, {"required_fields": ["Nombre_lug"]}) == []


def test_warns_on_empty_source() -> None:
    assert validate_geojson({"features": []}, {}) == ["La fuente no devolvió registros"]
