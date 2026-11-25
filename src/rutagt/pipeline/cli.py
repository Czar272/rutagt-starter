"""Interfaz de línea de comandos del recolector (`rutagt-collect`).

Códigos de salida: 0 éxito, 1 alguna fuente falló, 2 error de configuración.
"""

import argparse
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from rutagt.core.errors import ConfigurationError, SourceError
from rutagt.core.io import utc_now, write_json
from rutagt.core.logging import configure_logging, log_context
from rutagt.core.settings import Settings
from rutagt.pipeline.collectors import collect_source
from rutagt.pipeline.collectors.http import USER_AGENT
from rutagt.pipeline.sources import load_sources, select_sources

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
        help="Directorio para datos crudos",
    )
    return parser


def _elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def run_fetch(sources: list[dict[str, Any]], config: Path, output: Path) -> int:
    """Recolecta las fuentes, continúa ante fallas y escribe el manifiesto.

    Cada ejecución recibe un `run_id` que se agrega a todos los registros y al
    manifiesto, para correlacionar logs, procedencia y resultados.
    """
    run_id = uuid.uuid4().hex
    started_at = utc_now()
    run_start = time.perf_counter()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with log_context(run_id=run_id):
        logger.info("Inicio de recolección de %d fuentes", len(sources))
        for source in sources:
            with log_context(source_id=source["id"]):
                logger.info("Recolectando %s...", source["id"])
                source_start = time.perf_counter()
                try:
                    result = collect_source(source, output)
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

        manifest_path = output / "run_manifest.json"
        write_json(
            manifest_path,
            {
                "project": "RutaGT",
                "run_id": run_id,
                "started_by": USER_AGENT,
                "started_at": started_at,
                "finished_at": utc_now(),
                "duration_seconds": _elapsed(run_start),
                "config": str(config.resolve()),
                "output": str(output.resolve()),
                "summary": {
                    "requested": len(sources),
                    "successful": len(results),
                    "failed": len(failures),
                },
                "successful": results,
                "failed": failures,
            },
        )
        logger.info(
            "Fin de recolección: %d exitosas, %d fallidas. Manifiesto: %s",
            len(results),
            len(failures),
            manifest_path.resolve(),
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
                print(
                    f"{source['id']:<42} {source['type']:<24} {source.get('name', '')}"
                )
            return EXIT_OK
        selected = select_sources(sources, args.source, args.all)
        return run_fetch(selected, args.config, args.output)
    except ConfigurationError as exc:
        logger.error("%s", exc)
        return EXIT_CONFIGURATION_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
