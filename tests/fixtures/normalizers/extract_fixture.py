"""Regenera el snapshot de prueba de los normalizers a partir de un snapshot real.

Copia sin modificar los registros elegidos de las cuatro capas municipales y
escribe la procedencia mínima que exige el runner (SHA-256). Uso, desde la raíz
del repositorio y con el recolector ya ejecutado:

    uv run python tests/fixtures/normalizers/extract_fixture.py [snapshot_id]

Si se cambia la selección, regenerar también los resultados esperados con
`RUTAGT_UPDATE_GOLDEN=1 uv run pytest tests/pipeline/normalizers/test_golden.py`.
"""

import sys
from pathlib import Path
from typing import Any

from rutagt.core.io import read_json, sha256_bytes, write_json
from rutagt.core.settings import PROJECT_ROOT
from rutagt.core.snapshots import resolve_snapshot

FIXTURE_SNAPSHOT = "20261126T181403Z"
"""Identificador del snapshot de prueba (el del snapshot de origen en 2026-11)."""

HERE = Path(__file__).parent

SELECTION: dict[str, tuple[str, list[int], str]] = {
    "muniguate_transmetro_stops_2025": (
        "muniguate/transmetro_stops_2025.geojson",
        [19, 20, 22, 24, 25, 26, 44, 54, 82, 85, 86, 91, 141, 142, 144, 145],
        "Líneas 18 y 13 con trazado; sentido en el nombre (44, 54, 144, 145); "
        "sentido repetido (Granai 144/145, E6); zona discrepante (44, 54); "
        "espacio no separable (19); espacio inicial en la dirección (82); "
        "sufijo de líneas (19); andenes de líneas sin trazado en el extracto",
    ),
    "muniguate_tubus_stops_2025": (
        "muniguate/tubus_stops_2025.geojson",
        [101, 102, 143, 163, 205, 214, 226, 258],
        "Número repetido a 519 m (101/102) y registro duplicado (143/258, B7); "
        "sentido en la dirección (163); zona discrepante (205); "
        "espacio no separable (214); rutas con y sin trazado en el extracto",
    ),
    "muniguate_transmetro_routes_2025": (
        "muniguate/transmetro_routes_2025.geojson",
        [6, 7, 9, 12],
        "Línea 18 como MultiLineString en circuito (7); corrección ortográfica "
        "(6, 9, 12); variantes con trazado compartido (9/12)",
    ),
    "muniguate_tubus_routes_2025": (
        "muniguate/tubus_routes_2025.geojson",
        [5, 7],
        "Código como texto; rutas 305 y 402",
    ),
}


def extract(snapshot: Path, destination: Path) -> None:
    """Escribe en `destination` los registros elegidos de `snapshot`."""
    for source_id, (relative, fids, reason) in SELECTION.items():
        collection: dict[str, Any] = read_json(snapshot / relative)
        wanted = set(fids)
        features = [
            f for f in collection["features"] if f["properties"]["FID"] in wanted
        ]
        found = sorted(f["properties"]["FID"] for f in features)
        if found != sorted(wanted):
            raise SystemExit(f"{source_id}: faltan FID {sorted(wanted - set(found))}")
        path = destination / relative
        body = write_json(path, {**collection, "features": features})
        write_json(
            path.with_name(path.name + ".provenance.json"),
            {
                "source_id": source_id,
                "extracted_from_snapshot": snapshot.name,
                "fids": sorted(wanted),
                "reason": reason,
                "sha256": sha256_bytes(body),
            },
        )


def main(argv: list[str]) -> None:
    raw_root = PROJECT_ROOT / "data" / "raw"
    snapshot = resolve_snapshot(raw_root, argv[0] if argv else None)
    extract(snapshot, HERE / "raw" / FIXTURE_SNAPSHOT)
    print(f"Fixture extraído de {snapshot.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
