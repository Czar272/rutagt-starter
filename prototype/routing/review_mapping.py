"""Correspondencia revisada entre el rutero oficial y la capa GeoJSON (RGT-127).

Método:

1. Proyecta cada registro GeoJSON de la ruta sobre el trazado oficial y los
   ordena por su posición a lo largo del recorrido.
2. Alinea la secuencia del rutero con los registros ordenados maximizando la
   similitud de direcciones, con la restricción de que el orden se conserva y
   de que pueden quedar registros sin asignar (alineación monótona).
3. Compara el resultado con la asignación del reconciliador original y agrega
   las notas de la revisión manual.

Uso, desde la raíz del repositorio:

    uv run python prototype/routing/review_mapping.py
"""

import json
import sys
from pathlib import Path
from typing import Any

from analyze_route import (
    OFFICIAL_FILE,
    ROUTE_CODE,
    ROUTES_LAYER,
    STOPS_LAYER,
    address_similarity,
    extract_stop_code,
    get_route_stops,
    load_json,
    raw_file,
    reconcile,
)
from linear_reference import Polyline

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
REVIEWED_AT = "2026-11-25"

# Notas de la revisión manual contra el PDF oficial y el trazado.
STOP_NOTES: dict[str, str] = {
    "073": "La capa indica «16 calle y 15 calle»; el rutero, «Diagonal 24 y 16 calle». "
    "Posición y orden confirman la parada.",
    "074": "Dirección de la capa desplazada una cuadra respecto del rutero.",
    "075": "Dirección de la capa desplazada una cuadra respecto del rutero.",
    "076": "Registro con nombre descriptivo («Monumento a la Madre»); la capa indica "
    "13 avenida y el rutero 14 avenida.",
    "077": "La capa indica 11 avenida y el rutero 12 avenida.",
    "080": "La capa indica 12 avenida y el rutero 11 avenida.",
    "094": "El registro se llama «Parada 947», probable error de digitación de 094.",
    "095": "Tres registros consecutivos sobre Calzada San Juan (FID 91, 208 y 92) y "
    "una sola parada en el rutero. Asignación manual a FID 208 («8 avenida»): la "
    "similitud de texto prefiere FID 91 («7a avenida») porque no distingue números.",
    "098": "La capa indica «9a calle y 13 avenida» y el rutero «9a calle y Calle de La "
    "Verbena», ambas en Colonia Castillo Lara. Posición y orden confirman la parada; "
    "confianza media.",
}
# Asignaciones decididas en la revisión manual cuando la similitud de texto no
# basta para elegir entre registros consecutivos (parada -> FID).
MANUAL_ASSIGNMENTS: dict[str, int] = {"095": 208}
EXCLUDED_NOTES: dict[int, str] = {
    91: "Calzada San Juan y 7a avenida («Funerales Reforma»): no figura en el "
    "rutero vigente (versión 4); posible parada anterior o de otra ruta.",
    92: "Calzada San Juan y 9a avenida «B» («C.C. Promo Centro»): no figura en el "
    "rutero vigente (versión 4); posible parada anterior o de otra ruta.",
}


def route_polyline() -> Polyline:
    routes = load_json(raw_file(ROUTES_LAYER))
    for feature in routes["features"]:
        if str(feature["properties"].get("Codigoruta")) == ROUTE_CODE:
            return Polyline(feature["geometry"]["coordinates"])
    raise SystemExit(f"No se encontró el trazado de la ruta {ROUTE_CODE}")


def ordered_records(
    features: list[dict[str, Any]], polyline: Polyline
) -> list[dict[str, Any]]:
    records = []
    for feature in features:
        projection = polyline.project(feature["geometry"]["coordinates"][:2])
        properties = feature["properties"]
        records.append(
            {
                "fid": properties.get("FID"),
                "name": properties.get("Nombre_lug"),
                "address": properties.get("Direccion"),
                "position_m": round(projection.position_m),
                "offset_m": round(projection.offset_m, 1),
            }
        )
    records.sort(key=lambda record: record["position_m"])
    for order, record in enumerate(records, start=1):
        record["order"] = order
    return records


def align(
    official_stops: list[dict[str, Any]], records: list[dict[str, Any]]
) -> list[int]:
    """Índice del registro asignado a cada parada, conservando el orden.

    Programación dinámica: best[i][j] es el mejor puntaje asignando las primeras
    i paradas usando los primeros j registros.
    """
    stops, slots = len(official_stops), len(records)
    if slots < stops:
        raise SystemExit("Hay menos registros que paradas oficiales")
    similarity = [
        [address_similarity(stop["address"], record["address"]) for record in records]
        for stop in official_stops
    ]
    minus_inf = float("-inf")
    for i, stop in enumerate(official_stops):
        forced_fid = MANUAL_ASSIGNMENTS.get(stop["stop_code"])
        if forced_fid is not None:
            similarity[i] = [
                1.0 if record["fid"] == forced_fid else minus_inf for record in records
            ]
    best = [[minus_inf] * (slots + 1) for _ in range(stops + 1)]
    best[0] = [0.0] * (slots + 1)
    for i in range(1, stops + 1):
        for j in range(i, slots + 1):
            skip = best[i][j - 1]
            take = best[i - 1][j - 1] + similarity[i - 1][j - 1]
            best[i][j] = max(skip, take)
    assignment = [0] * stops
    i, j = stops, slots
    while i > 0:
        if best[i][j] == best[i][j - 1] and j > i:
            j -= 1
        else:
            assignment[i - 1] = j - 1
            i -= 1
            j -= 1
    return assignment


def build_review(
    official_stops: list[dict[str, Any]], features: list[dict[str, Any]]
) -> dict[str, Any]:
    records = ordered_records(features, route_polyline())
    assignment = align(official_stops, records)
    reconciled = {
        result["official"]["stop_code"]: result["candidate"]["feature"]["properties"][
            "FID"
        ]
        for result in reconcile(official_stops, features)
    }

    stops = []
    for stop, index in zip(official_stops, assignment, strict=True):
        record = records[index]
        previous_fid = reconciled[stop["stop_code"]]
        stops.append(
            {
                "sequence": stop["sequence"],
                "stop_code": stop["stop_code"],
                "official_address": stop["address"],
                "fid": record["fid"],
                "record_name": record["name"],
                "record_address": record["address"],
                "name_code": extract_stop_code(record["name"]),
                "route_order": record["order"],
                "position_m": record["position_m"],
                "offset_m": record["offset_m"],
                "address_similarity": round(
                    address_similarity(stop["address"], record["address"]), 3
                ),
                "reconciler_fid": previous_fid,
                "decision": "confirmado"
                if previous_fid == record["fid"]
                else "corregido",
                "manual_assignment": stop["stop_code"] in MANUAL_ASSIGNMENTS,
                "note": STOP_NOTES.get(stop["stop_code"]),
            }
        )

    assigned = {records[index]["fid"] for index in assignment}
    excluded = [
        {
            **record,
            "reason": EXCLUDED_NOTES.get(record["fid"], "Sin parada en el rutero"),
        }
        for record in records
        if record["fid"] not in assigned
    ]
    return {
        "route_code": ROUTE_CODE,
        "reviewed_at": REVIEWED_AT,
        "method": (
            "Proyección de los registros sobre el trazado oficial y alineación "
            "monótona de la secuencia del rutero por similitud de direcciones, "
            "con revisión manual contra el rutero oficial versión 4."
        ),
        "summary": {
            "official_stops": len(official_stops),
            "records": len(records),
            "confirmed": sum(stop["decision"] == "confirmado" for stop in stops),
            "corrected": sum(stop["decision"] == "corregido" for stop in stops),
            "excluded_records": len(excluded),
            "name_code_mismatches": sum(
                stop["name_code"] is not None and stop["name_code"] != stop["stop_code"]
                for stop in stops
            ),
        },
        "stops": stops,
        "excluded_records": excluded,
    }


def render_markdown(review: dict[str, Any]) -> str:
    summary = review["summary"]
    lines = [
        f"# Correspondencia revisada — ruta {review['route_code']}",
        "",
        f"Revisión: {review['reviewed_at']}. {review['method']}",
        "",
        f"- Paradas oficiales: {summary['official_stops']}",
        f"- Registros GeoJSON: {summary['records']}",
        f"- Confirmadas respecto del reconciliador: {summary['confirmed']}",
        f"- Corregidas respecto del reconciliador: {summary['corrected']}",
        f"- Registros sin parada en el rutero: {summary['excluded_records']}",
        "- Registros cuyo número en el nombre no coincide con el rutero: "
        f"{summary['name_code_mismatches']}",
        "",
        "| Parada | FID | Nombre en la capa | Orden | km | Similitud | "
        "Reconciliador | Decisión |",
        "| - | - | - | - | - | - | - | - |",
    ]
    for stop in review["stops"]:
        lines.append(
            f"| #{stop['stop_code']} | {stop['fid']} | {stop['record_name']} | "
            f"{stop['route_order']} | {stop['position_m'] / 1000:.2f} | "
            f"{stop['address_similarity']} | {stop['reconciler_fid']} | "
            f"{stop['decision']} |"
        )
    lines += ["", "## Notas de la revisión", ""]
    lines += [
        f"- **#{stop['stop_code']}:** {stop['note']}"
        for stop in review["stops"]
        if stop["note"]
    ]
    lines += ["", "## Registros sin parada en el rutero", ""]
    lines += [
        f"- **FID {record['fid']}** (orden {record['order']}, "
        f"{record['position_m'] / 1000:.2f} km): {record['reason']}"
        for record in review["excluded_records"]
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    features = get_route_stops(load_json(raw_file(STOPS_LAYER)))
    official_stops = load_json(OFFICIAL_FILE)["stops"]
    review = build_review(official_stops, features)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping_path = DATA_DIR / f"route_{ROUTE_CODE}_reviewed_mapping.json"
    report_path = OUTPUT_DIR / f"route_{ROUTE_CODE}_reviewed_mapping.md"
    mapping_path.write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path.write_text(render_markdown(review), encoding="utf-8", newline="\n")
    print(json.dumps(review["summary"], ensure_ascii=False))
    print(f"Correspondencia: {mapping_path}")
    print(f"Reporte: {report_path}")


if __name__ == "__main__":
    main()
