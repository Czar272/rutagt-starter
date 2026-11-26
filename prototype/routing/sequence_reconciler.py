"""Reconciliación ordenada del rutero oficial con la capa GeoJSON (RGT-128).

Reemplaza la asignación parada por parada de `analyze_route.py`, que daba el
mayor peso al número en el nombre del registro y, con la numeración corrida de
la capa municipal, asignaba a varias paradas el registro de la parada
siguiente. Este reconciliador:

1. ordena los registros por su posición a lo largo del trazado oficial;
2. compara direcciones con una similitud que distingue números de calle;
3. asigna cada parada a un registro distinto conservando el orden de la
   secuencia (alineación monótona), dejando sin asignar los registros que no
   corresponden a ninguna parada.

Uso, desde la raíz del repositorio:

    uv run python prototype/routing/sequence_reconciler.py
"""

import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from analyze_route import (
    GEOJSON_FILE,
    OFFICIAL_FILE,
    PROJECT_ROOT,
    ROUTE_CODE,
    extract_stop_code,
    get_route_stops,
    load_json,
    normalize_text,
)
from linear_reference import Polyline

ROUTES_FILE = PROJECT_ROOT / "data" / "raw" / "muniguate" / "tubus_routes_2025.geojson"
REVIEWED_FILE = (
    Path(__file__).resolve().parent
    / "data"
    / f"route_{ROUTE_CODE}_reviewed_mapping.json"
)
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

TEXT_WEIGHT = 0.6
NUMBER_WEIGHT = 0.4
NEUTRAL_NUMBER_SCORE = 0.5
MATCH_THRESHOLD = 0.75

STREET_TYPES = {
    "calle": "calle",
    "av": "av",
    "diag": "diagonal",
    "diagonal": "diagonal",
}
_STREET = r"(calle|av|diag|diagonal)"
_NUMBER_BEFORE = re.compile(rf"\b(\d+)\s*(?:a|va|ta|o|ra|da)?\s+{_STREET}\b")
_NUMBER_AFTER = re.compile(rf"\b{_STREET}\s+(\d+)\b")


def street_numbers(address: str | None) -> set[tuple[str, str]]:
    """Pares (número, tipo de vía) mencionados en una dirección.

    «Calz. San Juan y 8a avenida» → {("8", "av")}. Los números de zona se ignoran.
    """
    text = normalize_text(address)
    numbers = {
        (str(int(number)), STREET_TYPES[kind])
        for number, kind in _NUMBER_BEFORE.findall(text)
    }
    numbers |= {
        (str(int(number)), STREET_TYPES[kind])
        for kind, number in _NUMBER_AFTER.findall(text)
    }
    return numbers


def number_agreement(left: str | None, right: str | None) -> float:
    """Coincidencia de números de vía (Jaccard); neutral si alguno no tiene."""
    a, b = street_numbers(left), street_numbers(right)
    if not a or not b:
        return NEUTRAL_NUMBER_SCORE
    return len(a & b) / len(a | b)


def address_score(official: str | None, record: str | None) -> float:
    """Similitud combinada de texto normalizado y números de vía."""
    text = SequenceMatcher(None, normalize_text(official), normalize_text(record))
    return TEXT_WEIGHT * text.ratio() + NUMBER_WEIGHT * number_agreement(
        official, record
    )


def align_in_order(scores: Sequence[Sequence[float]]) -> list[int]:
    """Asigna cada fila a una columna distinta, en orden creciente.

    Maximiza la suma de puntajes con programación dinámica: best[i][j] es el
    mejor total asignando las primeras i filas usando las primeras j columnas.
    Las columnas que no convienen quedan sin asignar.
    """
    rows = len(scores)
    columns = len(scores[0]) if rows else 0
    if columns < rows:
        raise ValueError("Hay menos registros que paradas para alinear")
    minus_inf = float("-inf")
    best = [[minus_inf] * (columns + 1) for _ in range(rows + 1)]
    best[0] = [0.0] * (columns + 1)
    for i in range(1, rows + 1):
        for j in range(i, columns + 1):
            best[i][j] = max(best[i][j - 1], best[i - 1][j - 1] + scores[i - 1][j - 1])
    assignment = [0] * rows
    i, j = rows, columns
    while i > 0:
        if j > i and best[i][j] == best[i][j - 1]:
            j -= 1
        else:
            assignment[i - 1] = j - 1
            i -= 1
            j -= 1
    return assignment


@dataclass(frozen=True)
class Assignment:
    stop_code: str
    sequence: int
    fid: Any
    record_name: str | None
    position_m: float
    score: float
    status: str
    name_code_mismatch: bool


def reconcile_sequence(
    official_stops: list[dict[str, Any]],
    features: list[dict[str, Any]],
    polyline: Polyline,
) -> tuple[list[Assignment], list[dict[str, Any]]]:
    """Asigna cada parada oficial a un registro distinto, conservando el orden.

    Devuelve las asignaciones y los registros que quedaron sin parada.
    """
    records = sorted(
        (
            (
                polyline.project(feature["geometry"]["coordinates"][:2]).position_m,
                feature,
            )
            for feature in features
        ),
        key=lambda item: item[0],
    )
    scores = [
        [
            address_score(stop["address"], feature["properties"].get("Direccion"))
            for _, feature in records
        ]
        for stop in official_stops
    ]
    assignment = align_in_order(scores)

    results = []
    for stop, column, row_scores in zip(
        official_stops, assignment, scores, strict=True
    ):
        position, feature = records[column]
        properties = feature["properties"]
        name_code = extract_stop_code(properties.get("Nombre_lug"))
        score = row_scores[column]
        results.append(
            Assignment(
                stop_code=stop["stop_code"],
                sequence=stop["sequence"],
                fid=properties.get("FID"),
                record_name=properties.get("Nombre_lug"),
                position_m=round(position),
                score=round(score, 3),
                status="MATCH" if score >= MATCH_THRESHOLD else "REVIEW",
                name_code_mismatch=name_code is not None
                and name_code != stop["stop_code"],
            )
        )
    used = set(assignment)
    unassigned = [
        {
            "fid": feature["properties"].get("FID"),
            "name": feature["properties"].get("Nombre_lug"),
            "address": feature["properties"].get("Direccion"),
            "position_m": round(position),
        }
        for index, (position, feature) in enumerate(records)
        if index not in used
    ]
    return results, unassigned


def compare_with_review(
    assignments: list[Assignment], reviewed: dict[str, Any]
) -> list[tuple[str, Any, Any]]:
    """Paradas cuyo FID difiere de la revisión: (código, obtenido, esperado)."""
    expected = {stop["stop_code"]: stop["fid"] for stop in reviewed["stops"]}
    return [
        (item.stop_code, item.fid, expected.get(item.stop_code))
        for item in assignments
        if item.fid != expected.get(item.stop_code)
    ]


def render_markdown(
    assignments: list[Assignment],
    unassigned: list[dict[str, Any]],
    differences: list[tuple[str, Any, Any]],
) -> str:
    fids = [item.fid for item in assignments]
    lines = [
        f"# Reconciliación ordenada — ruta {ROUTE_CODE}",
        "",
        f"- Paradas asignadas: {len(assignments)}",
        f"- FIDs reutilizados: {len(fids) - len(set(fids))}",
        f"- Asignaciones `MATCH`: {sum(a.status == 'MATCH' for a in assignments)}",
        f"- Asignaciones `REVIEW`: {sum(a.status == 'REVIEW' for a in assignments)}",
        f"- Registros sin parada: {len(unassigned)}",
        f"- Diferencias con la correspondencia revisada (RGT-127): {len(differences)}",
        "",
        "| Parada | FID | Nombre en la capa | km | Puntaje | Estado | Nombre ≠ ruta |",
        "| - | - | - | - | - | - | - |",
    ]
    for item in assignments:
        lines.append(
            f"| #{item.stop_code} | {item.fid} | {item.record_name} | "
            f"{item.position_m / 1000:.2f} | {item.score} | {item.status} | "
            f"{'sí' if item.name_code_mismatch else ''} |"
        )
    lines += ["", "## Registros sin parada", ""]
    lines += [
        f"- FID {record['fid']} ({record['position_m'] / 1000:.2f} km): "
        f"{record['name']} — {record['address']}"
        for record in unassigned
    ]
    if differences:
        lines += ["", "## Diferencias con la revisión", ""]
        lines += [
            f"- #{code}: FID {got} (revisión: FID {expected})"
            for code, got, expected in differences
        ]
    return "\n".join(lines) + "\n"


def route_polyline() -> Polyline:
    for feature in load_json(ROUTES_FILE)["features"]:
        if str(feature["properties"].get("Codigoruta")) == ROUTE_CODE:
            return Polyline(feature["geometry"]["coordinates"])
    raise SystemExit(f"No se encontró el trazado de la ruta {ROUTE_CODE}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    features = get_route_stops(load_json(GEOJSON_FILE))
    official_stops = load_json(OFFICIAL_FILE)["stops"]
    assignments, unassigned = reconcile_sequence(
        official_stops, features, route_polyline()
    )
    differences = compare_with_review(assignments, load_json(REVIEWED_FILE))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / f"route_{ROUTE_CODE}_sequence_reconciliation.md"
    report_path.write_text(
        render_markdown(assignments, unassigned, differences),
        encoding="utf-8",
        newline="\n",
    )
    fids = [item.fid for item in assignments]
    print(
        json.dumps(
            {
                "assigned": len(assignments),
                "reused_fids": len(fids) - len(set(fids)),
                "unassigned": [record["fid"] for record in unassigned],
                "differences_with_review": len(differences),
            }
        )
    )
    print(f"Reporte: {report_path}")
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
