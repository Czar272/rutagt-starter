"""Auditoría de candidatos para las paradas conflictivas de la ruta 801 (RGT-126).

Para cada parada del rutero oficial que no se clasificó como EXACT, lista los
tres mejores registros GeoJSON con su puntaje, coordenadas y distancia a la
parada anterior de la secuencia. El reporte sirve de insumo para la revisión
manual (RGT-127).

Uso, desde la raíz del repositorio:

    uv run python prototype/routing/audit_candidates.py
"""

import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from analyze_route import (
    GEOJSON_FILE,
    OFFICIAL_FILE,
    ROUTE_CODE,
    address_similarity,
    candidate_score,
    extract_stop_code,
    get_route_stops,
    load_json,
    reconcile,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
TOP_CANDIDATES = 3
EARTH_RADIUS_M = 6_371_000
SUSPICIOUS_JUMP_M = 800


def haversine_m(a: list[float], b: list[float]) -> float:
    """Distancia en metros entre dos coordenadas [lon, lat]."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def coordinates(feature: dict[str, Any]) -> list[float]:
    return list(feature["geometry"]["coordinates"][:2])


def top_candidates(
    official: dict[str, Any], features: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Los mejores candidatos de una parada, ordenados por puntaje."""
    scored = []
    for feature in features:
        score, similarity, reasons = candidate_score(official, feature)
        properties = feature["properties"]
        scored.append(
            {
                "fid": properties.get("FID"),
                "name": properties.get("Nombre_lug"),
                "address": properties.get("Direccion"),
                "zone": properties.get("Zona"),
                "code_in_name": extract_stop_code(properties.get("Nombre_lug")),
                "coordinates": coordinates(feature),
                "score": round(score, 3),
                "address_similarity": round(similarity, 3),
                "reasons": reasons,
            }
        )
    scored.sort(key=lambda candidate: candidate["score"], reverse=True)
    return scored[:TOP_CANDIDATES]


def build_audit(
    official_stops: list[dict[str, Any]], features: list[dict[str, Any]]
) -> dict[str, Any]:
    results = reconcile(official_stops, features)
    by_fid = {feature["properties"].get("FID"): feature for feature in features}
    code_counts = Counter(
        extract_stop_code(feature["properties"].get("Nombre_lug"))
        for feature in features
    )

    used = {
        result["candidate"]["feature"]["properties"].get("FID") for result in results
    }
    unused_features = [feature for fid, feature in by_fid.items() if fid not in used]

    stops = []
    previous_coordinates: list[float] | None = None
    previous_fid: Any = None
    for result in results:
        official = result["official"]
        chosen = result["candidate"]["feature"]
        chosen_coordinates = coordinates(chosen)
        jump = (
            round(haversine_m(previous_coordinates, chosen_coordinates))
            if previous_coordinates
            else None
        )
        previous_coordinates = chosen_coordinates

        flags = []
        if jump is not None and jump > SUSPICIOUS_JUMP_M:
            flags.append(f"salto de {jump} m desde la parada anterior")
        if not result["candidate"]["code_matches"]:
            flags.append("el número del registro no coincide con el rutero")
        chosen_code = extract_stop_code(chosen["properties"].get("Nombre_lug"))
        if chosen_code and code_counts[chosen_code] > 1:
            flags.append(f"el número {chosen_code} aparece en varios registros")
        chosen_fid = chosen["properties"].get("FID")
        if (
            isinstance(previous_fid, int)
            and isinstance(chosen_fid, int)
            and chosen_fid < previous_fid
            and previous_fid - chosen_fid < 10
        ):
            flags.append(
                f"FID {chosen_fid} fuera de orden respecto del previo ({previous_fid})"
            )
        previous_fid = chosen_fid
        chosen_similarity = result["candidate"]["similarity"]
        for feature in unused_features:
            similarity = address_similarity(
                official["address"], feature["properties"].get("Direccion")
            )
            if similarity > chosen_similarity:
                flags.append(
                    f"el registro sin asignar FID {feature['properties'].get('FID')} "
                    f"({feature['properties'].get('Nombre_lug')}) tiene una dirección "
                    f"más parecida ({similarity:.3f} frente a {chosen_similarity:.3f})"
                )

        if result["classification"] == "EXACT" and not flags:
            continue
        stops.append(
            {
                "sequence": official["sequence"],
                "stop_code": official["stop_code"],
                "official_address": official["address"],
                "official_zone": official["zone"],
                "classification": result["classification"],
                "chosen_fid": chosen["properties"].get("FID"),
                "distance_from_previous_m": jump,
                "flags": flags,
                "candidates": top_candidates(official, features),
            }
        )

    unused = [
        {
            "fid": fid,
            "name": feature["properties"].get("Nombre_lug"),
            "address": feature["properties"].get("Direccion"),
            "coordinates": coordinates(feature),
        }
        for fid, feature in sorted(by_fid.items(), key=lambda item: str(item[0]))
        if fid not in used
    ]
    return {
        "route_code": ROUTE_CODE,
        "official_stops": len(official_stops),
        "geojson_records": len(features),
        "classification_counts": dict(
            Counter(result["classification"] for result in results)
        ),
        "stops_to_review": stops,
        "unused_records": unused,
    }


def render_markdown(audit: dict[str, Any]) -> str:
    lines = [
        f"# Auditoría de candidatos — ruta {audit['route_code']}",
        "",
        f"- Paradas del rutero oficial: {audit['official_stops']}",
        f"- Registros GeoJSON de la ruta: {audit['geojson_records']}",
        "- Clasificación: "
        + ", ".join(
            f"{name} {count}"
            for name, count in sorted(audit["classification_counts"].items())
        ),
        f"- Paradas a revisar: {len(audit['stops_to_review'])}",
        "",
        "Se listan las paradas que no son EXACT o que tienen alertas, con sus "
        f"{TOP_CANDIDATES} mejores candidatos. Un salto mayor a "
        f"{SUSPICIOUS_JUMP_M} m entre paradas consecutivas sugiere una "
        "correspondencia incorrecta.",
        "",
    ]
    for stop in audit["stops_to_review"]:
        lines += [
            f"## #{stop['stop_code']} (secuencia {stop['sequence']}) — "
            f"{stop['classification']}",
            "",
            f"Rutero: {stop['official_address']} (zona {stop['official_zone']})",
            "",
        ]
        if stop["flags"]:
            lines += [f"- ⚠️ {flag}" for flag in stop["flags"]] + [""]
        lines += [
            "| | FID | Nombre | Dirección | Zona | Puntaje | Similitud | Coordenadas |",
            "| - | - | - | - | - | - | - | - |",
        ]
        for candidate in stop["candidates"]:
            marker = "✔" if candidate["fid"] == stop["chosen_fid"] else ""
            lon, lat = candidate["coordinates"]
            lines.append(
                f"| {marker} | {candidate['fid']} | {candidate['name']} | "
                f"{candidate['address']} | {candidate['zone']} | "
                f"{candidate['score']} | {candidate['address_similarity']} | "
                f"{lat:.5f}, {lon:.5f} |"
            )
        lines.append("")
    lines += ["## Registros GeoJSON sin asignar", ""]
    lines += [
        f"- FID {record['fid']}: {record['name']} — {record['address']}"
        for record in audit["unused_records"]
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    features = get_route_stops(load_json(GEOJSON_FILE))
    official_stops = load_json(OFFICIAL_FILE)["stops"]
    audit = build_audit(official_stops, features)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / f"route_{ROUTE_CODE}_candidate_audit.json"
    markdown_path = OUTPUT_DIR / f"route_{ROUTE_CODE}_candidate_audit.md"
    json_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(audit), encoding="utf-8")
    print(f"Paradas a revisar: {len(audit['stops_to_review'])}")
    print(f"Reportes: {json_path} y {markdown_path}")


if __name__ == "__main__":
    main()
