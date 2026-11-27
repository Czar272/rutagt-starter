"""Interfaz de línea de comandos de la carga a PostGIS (`rutagt-load`).

Carga `data/normalized/<snapshot>/canonical.json` (por defecto, el del
snapshot `LATEST`) en la base configurada con `RUTAGT_DB_*`, en una sola
transacción (ADR-0035):

    uv run --env-file .env rutagt-load

Códigos de salida: 0 éxito, 1 el dataset no es válido o la carga falló,
2 error de configuración.
"""

import argparse
import logging
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from rutagt.core.errors import ConfigurationError, SourceError
from rutagt.core.logging import configure_logging, log_context
from rutagt.core.settings import Settings
from rutagt.core.snapshots import read_latest, validate_snapshot_id
from rutagt.db.loader import load_dataset
from rutagt.db.settings import DatabaseSettings
from rutagt.pipeline.canonical.runner import read_dataset

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_CONFIGURATION_ERROR = 2


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rutagt-load",
        description="Carga la red canónica de un snapshot en PostGIS",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=settings.data_dir,
        help="Raíz de los snapshots crudos (para leer LATEST)",
    )
    parser.add_argument("--snapshot", help="Snapshot a cargar (por defecto, LATEST)")
    parser.add_argument(
        "--normalized",
        type=Path,
        help="Raíz de la capa normalizada (por defecto, data/normalized)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        configure_logging()
        logger.error("%s", exc)
        return EXIT_CONFIGURATION_ERROR
    configure_logging(settings.log_level, settings.log_format)
    args = build_parser(settings).parse_args(argv)
    run_id = uuid.uuid4().hex
    try:
        snapshot_id = args.snapshot or read_latest(args.raw)
        if snapshot_id is None:
            raise ConfigurationError(f"No hay snapshot vigente en {args.raw}")
        validate_snapshot_id(snapshot_id)
        database = DatabaseSettings.from_env()
        dataset = read_dataset(
            args.normalized or args.raw.parent / "normalized", snapshot_id
        )
        engine = create_engine(database.url())
        try:
            with log_context(run_id=run_id, snapshot_id=snapshot_id):
                with engine.begin() as conn:
                    summary = load_dataset(conn, dataset, run_id)
                logger.info("Carga de %s: %s", snapshot_id, summary.as_dict())
        finally:
            engine.dispose()
    except ConfigurationError as exc:
        logger.error("%s", exc)
        return EXIT_CONFIGURATION_ERROR
    except (SourceError, SQLAlchemyError) as exc:
        logger.error("La carga falló y no se aplicó ningún cambio: %s", exc)
        return EXIT_FAILURES
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
