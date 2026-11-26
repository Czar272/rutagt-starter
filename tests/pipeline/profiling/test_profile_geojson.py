"""Pruebas del perfil de colecciones GeoJSON."""

from typing import Any

from rutagt.pipeline.profiling.geojson import (
    profile_collection,
    profile_field,
    profile_geometries,
)


def point(lon: float, lat: float, **properties: Any) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }


def test_field_counts_types_nulls_and_repeated_values() -> None:
    profile = profile_field([1, 2, 2, None, ""])

    assert profile["types"] == {"int": 3, "null": 1, "str": 1}
    assert (profile["null"], profile["empty"]) == (1, 1)
    assert profile["distinct"] == 2
    assert profile["unique"] is False
    assert profile["repeated_values"] == 1
    assert profile["top_repeated"] == [["2", 2]]
    assert profile["values"] == [["2", 2], ["1", 1]]
    assert (profile["min"], profile["max"]) == (1, 2)


def test_unique_field_without_gaps() -> None:
    profile = profile_field(list(range(20)))

    assert profile["unique"] is True
    assert profile["repeated_values"] == 0
    assert "values" not in profile


def test_string_field_detects_whitespace_and_encoding() -> None:
    profile = profile_field(
        ["Zona 1", " Zona 2", "6  avenida", "A\u00a0B", "EstaciÃ³n", "ok\ufffd"]
    )

    assert profile["length"] == [3, 10]
    assert profile["whitespace_issues"] == 3
    assert profile["encoding_issues"] == 2


def test_booleans_are_not_numbers() -> None:
    profile = profile_field([True, False])

    assert profile["types"] == {"bool": 2}
    assert "min" not in profile


def test_geometries_bbox_bounds_and_duplicates() -> None:
    features = [
        point(-90.5, 14.6),
        point(-90.5, 14.6),
        point(-90.4, 14.7),
        point(0.0, 0.0),
        {"type": "Feature", "geometry": None, "properties": {}},
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": []},
            "properties": {},
        },
    ]

    profile = profile_geometries(features)

    assert profile["types"] == {"LineString": 1, "Point": 4}
    assert (profile["missing"], profile["empty"]) == (1, 1)
    assert profile["bbox"] == [-90.5, 0.0, 0.0, 14.7]
    assert profile["outside_bounds"] == 1
    assert (profile["duplicate_groups"], profile["duplicate_records"]) == (1, 2)


def test_nested_geometries_are_traversed() -> None:
    multiline = {
        "type": "Feature",
        "geometry": {
            "type": "MultiLineString",
            "coordinates": [
                [[-90.5, 14.6], [-90.4, 14.6]],
                [[-90.4, 14.6], [-90.3, 14.7]],
            ],
        },
        "properties": {},
    }

    assert profile_geometries([multiline])["bbox"] == [-90.5, 14.6, -90.3, 14.7]


def test_empty_collection() -> None:
    profile = profile_collection({"type": "FeatureCollection", "features": []})

    assert profile["records"] == 0
    assert profile["geometry"]["bbox"] is None
    assert profile["anomalies"] == ["La colección no tiene registros"]


def test_collection_profile_reports_anomalies() -> None:
    collection = {
        "type": "FeatureCollection",
        "features": [
            point(-90.5, 14.6, FID=1, Codigo=801, Nombre="Parada  1"),
            point(-90.5, 14.6, FID=2, Codigo="801", Nombre=None),
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-90.5, 14.6], [0, 0]],
                },
                "properties": {"FID": 3, "Codigo": 802},
            },
        ],
    }

    profile = profile_collection(collection)

    assert list(profile["fields"]) == ["FID", "Codigo", "Nombre"]
    assert profile["fields"]["FID"]["unique"] is True
    assert profile["fields"]["Nombre"]["missing_key"] == 1
    assert profile["anomalies"] == [
        "Geometrías de varios tipos: {'LineString': 1, 'Point': 2}",
        "1 geometrías fuera de los límites de Guatemala",
        "2 registros comparten geometría idéntica en 1 grupos",
        "`Codigo`: tipos mezclados ['int', 'str']",
        "`Nombre`: ausente en 1 registros",
        "`Nombre`: 2 nulos y 0 vacíos",
        "`Nombre`: 1 valores con espacios al inicio, al final, dobles o no separables",
    ]


def test_clean_collection_has_no_anomalies() -> None:
    collection = {"features": [point(-90.5, 14.6, FID=1), point(-90.4, 14.6, FID=2)]}

    assert profile_collection(collection)["anomalies"] == []


def test_field_type_names_cover_json_values() -> None:
    profile = profile_field([1.5, "a", [1], {"k": 1}])

    assert profile["types"] == {"dict": 1, "float": 1, "list": 1, "str": 1}
    assert (profile["min"], profile["max"]) == (1.5, 1.5)


def test_missing_geometries_and_bad_encoding_are_anomalies() -> None:
    collection = {
        "features": [
            {"geometry": None, "properties": {"Nombre": "EstaciÃ³n"}},
            {
                "geometry": {"type": "Point", "coordinates": []},
                "properties": {"Nombre": "B"},
            },
        ]
    }

    anomalies = profile_collection(collection)["anomalies"]

    assert "1 registros sin geometría y 1 con geometría vacía" in anomalies
    assert "`Nombre`: 1 valores con codificación dañada" in anomalies
