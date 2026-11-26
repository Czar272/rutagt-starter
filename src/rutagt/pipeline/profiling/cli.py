"""Interfaz de línea de comandos del perfilado (`rutagt-profile`).

Perfila los GeoJSON de un snapshot crudo (por defecto, el vigente) y escribe
`profiles.json`, `perfil.md` y su procedencia en
`data/staging/<snapshot_id>/profiles/` (ADR-0032). Códigos de salida: 0 éxito,
2 error de configuración.
"""

import argparse
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from rutagt.core.errors import ConfigurationError
from rutagt.core.io import git_revision, sha256_bytes, utc_now, write_json
from rutagt.core.logging import configure_logging
from rutagt.core.settings import PROJECT_ROOT, Settings
from rutagt.core.snapshots import resolve_snapshot
from rutagt.pipeline.profiling.geojson import profile_collection
from rutagt.pipeline.profiling.report import render_report

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_CONFIGURATION_ERROR = 2


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rutagt-profile",
        description="Perfila los datasets GeoJSON de un snapshot crudo",
    )
    parser.add_argument(
        "--raw", type=Path, default=settings.data_dir, help="Raíz de los snapshots"
    )
    parser.add_argument("--snapshot", help="Snapshot a perfilar (por defecto, LATEST)")
    parser.add_argument(
        "--output",
        type=Path,
        help="Directorio de salida (por defecto, data/staging/<snapshot>/profiles)",
    )
    return parser


def profile_snapshot(snapshot: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Perfiles por archivo relativo y lista de entradas con su SHA-256."""
    files = sorted(snapshot.rglob("*.geojson"))
    if not files:
        raise ConfigurationError(
            f"El snapshot {snapshot.name} no tiene archivos GeoJSON"
        )
    profiles: dict[str, Any] = {}
    inputs: list[dict[str, str]] = []
    for path in files:
        name = path.relative_to(snapshot).as_posix()
        content = path.read_bytes()
        try:
            collection = json.loads(content)
        except ValueError as exc:
            raise ConfigurationError(f"{name} no es JSON válido: {exc}") from exc
        profiles[name] = profile_collection(collection)
        inputs.append({"file": name, "sha256": sha256_bytes(content)})
        logger.info(
            "%s: %d registros, %d anomalías",
            name,
            profiles[name]["records"],
            len(profiles[name]["anomalies"]),
        )
    return profiles, inputs


def write_outputs(
    output: Path,
    snapshot_id: str,
    profiles: dict[str, Any],
    inputs: list[dict[str, str]],
) -> None:
    """Escribe en un directorio temporal y lo renombra (reconstrucción atómica)."""
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}")
    body = write_json(temporary / "profiles.json", profiles)
    report = render_report(snapshot_id, profiles).encode("utf-8")
    (temporary / "perfil.md").write_bytes(report)
    write_json(
        temporary / "profiles.json.provenance.json",
        {
            "generator": "rutagt-profile",
            "generated_at": utc_now(),
            "snapshot_id": snapshot_id,
            "inputs": inputs,
            "code_version": git_revision(PROJECT_ROOT),
            "outputs": {
                "profiles.json": sha256_bytes(body),
                "perfil.md": sha256_bytes(report),
            },
        },
    )
    if output.exists():
        shutil.rmtree(output)
    temporary.rename(output)


def main(argv: list[str] | None = None) -> int:
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        configure_logging()
        logger.error("%s", exc)
        return EXIT_CONFIGURATION_ERROR
    configure_logging(settings.log_level, settings.log_format)
    args = build_parser(settings).parse_args(argv)
    try:
        snapshot = resolve_snapshot(args.raw, args.snapshot)
        output = args.output or (
            args.raw.parent / "staging" / snapshot.name / "profiles"
        )
        profiles, inputs = profile_snapshot(snapshot)
        write_outputs(output, snapshot.name, profiles, inputs)
    except ConfigurationError as exc:
        logger.error("%s", exc)
        return EXIT_CONFIGURATION_ERROR
    logger.info("Perfil de %d datasets en %s", len(profiles), output.resolve())
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
