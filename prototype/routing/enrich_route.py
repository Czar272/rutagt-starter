"""GeoJSON enriquecido de la ruta 801 con procedencia y calidad (RGT-129).

Combina el rutero oficial (secuencia, código y dirección de cada parada), la
capa de paradas de TuBus (ubicación) y el trazado de la ruta, usando el
reconciliador ordenado (RGT-128). Cada parada conserva la evidencia de su
asignación, sus discrepancias y un nivel de calidad por atributo, con los
niveles de `observation_quality` del esquema canónico:

- `official`: proviene directamente de una fuente oficial;
- `probable`: dos fuentes oficiales concuerdan, sin verificación en campo;
- `unverified`: las fuentes discrepan o no hay evidencia suficiente.

Uso, desde la raíz del repositorio:

    uv run python prototype/routing/enrich_route.py
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from analyze_route import (
    GEOJSON_FILE,
    OFFICIAL_FILE,
    ROUTE_CODE,
    get_route_stops,
    load_json,
    normalize_text,
)
from linear_reference import Polyline
from sequence_reconciler import (
    ROUTES_FILE,
    Assignment,
    reconcile_sequence,
    street_numbers,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_FILE = OUTPUT_DIR / f"route_{ROUTE_CODE}_enriched.geojson"
GENERATOR = "prototype/routing/enrich_route.py"
TICKET = "RGT-129"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def location_quality(assignment: Assignment) -> str:
    return "probable" if assignment.status == "MATCH" else "unverified"


def discrepancies(
    assignment: Assignment, official: dict[str, Any], layer: dict[str, Any]
) -> list[str]:
    """Diferencias entre el rutero oficial y el registro de la capa."""
    found = []
    if assignment.name_code_mismatch:
        found.append(
            f"El nombre del registro («{layer.get('Nombre_lug')}») no coincide con "
            f"el número oficial #{official['stop_code']}"
        )
    official_numbers = street_numbers(official["address"])
    layer_numbers = street_numbers(layer.get("Direccion"))
    if official_numbers and layer_numbers and official_numbers != layer_numbers:
        found.append(
            "Los números de vía difieren: rutero "
            f"{sorted(official_numbers)}, capa {sorted(layer_numbers)}"
        )
    if layer.get("Zona") not in (None, official["zone"]):
        found.append(
            f"Zona distinta: rutero {official['zone']}, capa {layer.get('Zona')}"
        )
    if normalize_text(layer.get("Direccion")) and assignment.status == "REVIEW":
        found.append("Dirección de la capa poco similar a la del rutero")
    return found


def build_enriched(
    official: dict[str, Any],
    features: list[dict[str, Any]],
    route_feature: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Construye la colección GeoJSON enriquecida de la ruta."""
    polyline = Polyline(route_feature["geometry"]["coordinates"])
    assignments, unassigned = reconcile_sequence(official["stops"], features, polyline)
    by_fid = {feature["properties"].get("FID"): feature for feature in features}

    stop_features = []
    for index, (stop, assignment) in enumerate(
        zip(official["stops"], assignments, strict=True)
    ):
        layer_feature = by_fid[assignment.fid]
        layer = layer_feature["properties"]
        coordinates = layer_feature["geometry"]["coordinates"][:2]
        projection = polyline.project(coordinates)
        next_position = (
            assignments[index + 1].position_m if index + 1 < len(assignments) else None
        )
        stop_features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": coordinates},
                "properties": {
                    "feature_type": "stop",
                    "route_code": ROUTE_CODE,
                    "sequence": stop["sequence"],
                    "stop_code": stop["stop_code"],
                    "stop_name": f"Parada #{stop['stop_code']}",
                    "official_address": stop["address"],
                    "zone": stop["zone"],
                    "layer_fid": assignment.fid,
                    "layer_name": layer.get("Nombre_lug"),
                    "layer_address": layer.get("Direccion"),
                    "position_m": assignment.position_m,
                    "offset_from_shape_m": round(projection.offset_m, 1),
                    "distance_to_next_m": (
                        round(next_position - assignment.position_m)
                        if next_position is not None
                        else None
                    ),
                    "match_score": assignment.score,
                    "match_status": assignment.status,
                    "quality": {
                        "sequence": "official",
                        "stop_code": "official",
                        "address": "official",
                        "location": location_quality(assignment),
                    },
                    "discrepancies": discrepancies(assignment, stop, layer),
                    "sources": {
                        "sequence": "muniguate_tubus_route_801_rutero_v4",
                        "location": "muniguate_tubus_stops_2025",
                    },
                },
            }
        )

    excluded_features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": by_fid[record["fid"]]["geometry"]["coordinates"][:2],
            },
            "properties": {
                "feature_type": "excluded_stop",
                "route_code": ROUTE_CODE,
                "layer_fid": record["fid"],
                "layer_name": record["name"],
                "layer_address": record["address"],
                "position_m": record["position_m"],
                "reason": "El registro no corresponde a ninguna parada del rutero "
                "oficial vigente; confirmar con la Municipalidad si sigue en uso.",
                "quality": {"location": "unverified"},
            },
        }
        for record in unassigned
    ]
    shape_feature = {
        "type": "Feature",
        "geometry": route_feature["geometry"],
        "properties": {
            "feature_type": "shape",
            "route_code": ROUTE_CODE,
            "route_name": official["route_name"],
            "length_m": round(polyline.length_m),
            "quality": {"geometry": "official"},
            "sources": {"geometry": "muniguate_tubus_routes_2025"},
        },
    }
    summary = {
        "stops": len(stop_features),
        "location_probable": sum(
            f["properties"]["quality"]["location"] == "probable" for f in stop_features
        ),
        "location_unverified": sum(
            f["properties"]["quality"]["location"] == "unverified"
            for f in stop_features
        ),
        "with_discrepancies": sum(
            bool(f["properties"]["discrepancies"]) for f in stop_features
        ),
        "excluded_records": len(excluded_features),
        "shape_length_m": round(polyline.length_m),
    }
    return {
        "type": "FeatureCollection",
        "name": f"route_{ROUTE_CODE}_enriched",
        "metadata": {
            "route_code": ROUTE_CODE,
            "route_name": official["route_name"],
            "service_hours": official.get("service_hours"),
            "summary": summary,
            "sources": sources,
            "generator": GENERATOR,
            "ticket": TICKET,
            "experimental": True,
        },
        "features": [shape_feature, *stop_features, *excluded_features],
    }


def collect_sources(official: dict[str, Any]) -> list[dict[str, Any]]:
    """Procedencia de cada fuente usada, con su checksum."""
    sources = []
    for source_id, path in (
        ("muniguate_tubus_stops_2025", GEOJSON_FILE),
        ("muniguate_tubus_routes_2025", ROUTES_FILE),
    ):
        provenance = load_json(path.with_suffix(path.suffix + ".provenance.json"))
        sources.append(
            {
                "source_id": source_id,
                "authority": provenance.get("authority"),
                "fetched_at": provenance.get("fetched_at"),
                "sha256": provenance.get("sha256"),
                "license_note": provenance.get("license_note"),
            }
        )
    rutero = official["source"]
    sources.append(
        {
            "source_id": "muniguate_tubus_route_801_rutero_v4",
            "authority": rutero.get("authority"),
            "document": rutero.get("document"),
            "url": rutero.get("url"),
            "document_sha256": rutero.get("document_sha256"),
            "transcription_sha256": sha256_file(OFFICIAL_FILE),
            "valid_from": rutero.get("valid_from"),
        }
    )
    return sources


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    official = load_json(OFFICIAL_FILE)
    features = get_route_stops(load_json(GEOJSON_FILE))
    route_feature = next(
        feature
        for feature in load_json(ROUTES_FILE)["features"]
        if str(feature["properties"].get("Codigoruta")) == ROUTE_CODE
    )
    enriched = build_enriched(
        official, features, route_feature, collect_sources(official)
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    body = json.dumps(enriched, ensure_ascii=False, separators=(",", ":")) + "\n"
    OUTPUT_FILE.write_text(body, encoding="utf-8", newline="\n")
    provenance = {
        "file": OUTPUT_FILE.name,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "generator": GENERATOR,
        "ticket": TICKET,
        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "summary": enriched["metadata"]["summary"],
        "sources": enriched["metadata"]["sources"],
    }
    OUTPUT_FILE.with_suffix(".geojson.provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(enriched["metadata"]["summary"], ensure_ascii=False))
    print(f"GeoJSON: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
