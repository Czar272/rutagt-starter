"""Pruebas del GeoJSON enriquecido con datos sintéticos."""

from typing import Any

from enrich_route import build_enriched


def layer(fid: int, lon: float, name: str, address: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, 14.6001]},
        "properties": {
            "FID": fid,
            "Nombre_lug": name,
            "Direccion": address,
            "Zona": 7,
        },
    }


OFFICIAL = {
    "route_name": "Ruta de prueba",
    "service_hours": {"monday_saturday": {"start": "05:30", "end": "19:00"}},
    "stops": [
        {
            "sequence": 1,
            "stop_code": "001",
            "address": "33 avenida y 26 calle",
            "zone": 7,
        },
        {
            "sequence": 2,
            "stop_code": "002",
            "address": "33 avenida y 30 calle",
            "zone": 7,
        },
    ],
}
ROUTE = {
    "type": "Feature",
    "geometry": {
        "type": "LineString",
        "coordinates": [[-90.52, 14.60], [-90.50, 14.60]],
    },
    "properties": {"Codigoruta": "801"},
}
FEATURES = [
    layer(10, -90.515, "Parada 001", "33 avenida y 26 calle"),
    layer(11, -90.510, "Sin parada", "Calzada San Juan y 7a avenida"),
    layer(12, -90.505, "Parada 003", "33 avenida y 30 calle"),
]


def build() -> dict[str, Any]:
    return build_enriched(OFFICIAL, FEATURES, ROUTE, sources=[{"source_id": "x"}])


def by_type(collection: dict[str, Any], feature_type: str) -> list[dict[str, Any]]:
    return [
        feature["properties"]
        for feature in collection["features"]
        if feature["properties"]["feature_type"] == feature_type
    ]


def test_contains_shape_stops_and_excluded_records() -> None:
    collection = build()

    assert len(by_type(collection, "shape")) == 1
    assert [stop["layer_fid"] for stop in by_type(collection, "stop")] == [10, 12]
    assert [record["layer_fid"] for record in by_type(collection, "excluded_stop")] == [
        11
    ]


def test_stops_keep_official_sequence_and_quality_levels() -> None:
    first, second = by_type(build(), "stop")

    assert (first["sequence"], first["stop_code"]) == (1, "001")
    assert first["quality"]["sequence"] == "official"
    assert first["quality"]["location"] in {"probable", "unverified"}
    assert first["distance_to_next_m"] == second["position_m"] - first["position_m"]
    assert second["distance_to_next_m"] is None


def test_records_name_mismatch_as_discrepancy() -> None:
    _, second = by_type(build(), "stop")

    assert any("Parada 003" in item for item in second["discrepancies"])


def test_metadata_summarizes_and_keeps_sources() -> None:
    metadata = build()["metadata"]

    assert metadata["summary"]["stops"] == 2
    assert metadata["summary"]["excluded_records"] == 1
    assert metadata["sources"] == [{"source_id": "x"}]
    assert metadata["experimental"] is True
