"""Interfaz de línea de comandos del recolector (`rutagt-collect`).

Códigos de salida: 0 éxito, 1 alguna fuente falló, 2 error de configuración.
"""

import argparse
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rutagt.core.errors import ConfigurationError, SourceError
from rutagt.core.io import utc_now, write_json
from rutagt.core.logging import configure_logging, log_context
from rutagt.core.settings import Settings
from rutagt.core.snapshots import create_snapshot, snapshot_id_for, write_latest
from rutagt.pipeline.collectors import collect_source
from rutagt.pipeline.collectors.http import USER_AGENT
from rutagt.pipeline.sources import is_enabled, load_sources, select_sources

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_SOURCE_FAILURES = 1
EXIT_CONFIGURATION_ERROR = 2


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rutagt-collect", description="Recolector de fuentes públicas de RutaGT"
    )
    parser.add_argument("--config", type=Path, default=settings.sources_config)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="Lista las fuentes configuradas")
    fetch = subparsers.add_parser("fetch", help="Descarga una o varias fuentes")
    fetch.add_argument("--source", action="append", default=[], help="ID de la fuente")
    fetch.add_argument("--all", action="store_true", help="Descarga todas las fuentes")
    fetch.add_argument(
        "--output",
        type=Path,
        default=settings.data_dir,
        help="Raíz de los snapshots crudos (cada ejecución crea uno nuevo)",
    )
    return parser


def _elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def run_fetch(
    sources: list[dict[str, Any]],
    config: Path,
    output: Path,
    *,
    skipped: list[dict[str, Any]] | None = None,
    full_run: bool = False,
) -> int:
    """Recolecta las fuentes en un snapshot nuevo y escribe su manifiesto.

    Cada ejecución crea `output/<snapshot_id>/` (ADR-0032) y recibe un `run_id`
    que se agrega a todos los registros y al manifiesto, para correlacionar
    logs, procedencia y resultados. `output/LATEST` solo apunta al snapshot si
    es una ejecución completa (`full_run`: todas las fuentes habilitadas) y
    ninguna falló; `skipped` son las fuentes deshabilitadas que se omitieron.
    """
    skipped = skipped or []
    run_id = uuid.uuid4().hex
    started = datetime.now(UTC)
    started_at = started.isoformat(timespec="seconds")
    snapshot_id = snapshot_id_for(started)
    snapshot = create_snapshot(output, snapshot_id)
    run_start = time.perf_counter()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with log_context(run_id=run_id):
        logger.info(
            "Inicio de recolección de %d fuentes en el snapshot %s",
            len(sources),
            snapshot_id,
        )
        for source in sources:
            with log_context(source_id=source["id"]):
                logger.info("Recolectando %s...", source["id"])
                source_start = time.perf_counter()
                try:
                    result = collect_source(source, snapshot)
                except (SourceError, ConfigurationError, OSError) as exc:
                    failures.append(
                        {
                            "source_id": source["id"],
                            "error": str(exc),
                            "duration_seconds": _elapsed(source_start),
                        }
                    )
                    logger.error("Falló %s: %s", source["id"], exc)
                    continue
                except Exception as exc:
                    # Un error inesperado en una fuente no detiene las demás
                    # (ADR-0004); se registra con su traza para diagnosticarlo.
                    failures.append(
                        {
                            "source_id": source["id"],
                            "error": repr(exc),
                            "duration_seconds": _elapsed(source_start),
                        }
                    )
                    logger.exception("Error inesperado en %s", source["id"])
                    continue
                results.append({**result, "duration_seconds": _elapsed(source_start)})
                logger.info(
                    "OK %s: %s registros, %d advertencias",
                    source["id"],
                    result.get("record_count", 0),
                    len(result.get("quality_warnings", [])),
                )

        complete = full_run and not failures
        manifest_path = snapshot / "run_manifest.json"
        write_json(
            manifest_path,
            {
                "project": "RutaGT",
                "run_id": run_id,
                "snapshot_id": snapshot_id,
                "complete": complete,
                "scope": "all" if full_run else "selected",
                "started_by": USER_AGENT,
                "started_at": started_at,
                "finished_at": utc_now(),
                "duration_seconds": _elapsed(run_start),
                "config": str(config.resolve()),
                "output": str(snapshot.resolve()),
                "summary": {
                    "requested": len(sources),
                    "successful": len(results),
                    "failed": len(failures),
                    "skipped": len(skipped),
                },
                "successful": results,
                "failed": failures,
                "skipped": [
                    {"source_id": s["id"], "reason": s["disabled_reason"]}
                    for s in skipped
                ],
            },
        )
        if complete:
            write_latest(output, snapshot_id)
        logger.info(
            "Fin de recolección: %d exitosas, %d fallidas. Manifiesto: %s",
            len(results),
            len(failures),
            manifest_path.resolve(),
        )
        if not complete:
            logger.warning(
                "Snapshot %s %s: %s no cambia",
                snapshot_id,
                "incompleto" if failures else "parcial (--source)",
                output / "LATEST",
            )
    return EXIT_SOURCE_FAILURES if failures else EXIT_OK


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
        sources = load_sources(args.config)
        if args.command == "list":
            for source in sources:
                status = "" if is_enabled(source) else " [deshabilitada]"
                print(
                    f"{source['id']:<42} {source['type']:<24} "
                    f"{source.get('name', '')}{status}"
                )
            return EXIT_OK
        selected = select_sources(sources, args.source, args.all)
        skipped = [s for s in sources if not is_enabled(s)] if args.all else []
        return run_fetch(
            selected, args.config, args.output, skipped=skipped, full_run=args.all
        )
    except ConfigurationError as exc:
        logger.error("%s", exc)
        return EXIT_CONFIGURATION_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
