"""Interfaz de línea de comandos de la normalización (`rutagt-normalize`).

Ejecuta los adaptadores sobre un snapshot crudo (por defecto, `LATEST`) y
escribe la capa staging (ADR-0033). Códigos de salida: 0 éxito, 1 alguna fuente
falló o produjo problemas de severidad `error`, 2 error de configuración.
"""

import argparse
import logging
from pathlib import Path

from rutagt.core.errors import ConfigurationError
from rutagt.core.logging import configure_logging
from rutagt.core.settings import Settings
from rutagt.core.snapshots import resolve_snapshot
from rutagt.pipeline import normalizers
from rutagt.pipeline.normalizers.runner import (
    normalize_snapshot,
    select_adapted_sources,
)
from rutagt.pipeline.sources import load_sources

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_CONFIGURATION_ERROR = 2


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rutagt-normalize",
        description="Traduce un snapshot crudo a la capa staging",
    )
    parser.add_argument("--config", type=Path, default=settings.sources_config)
    parser.add_argument(
        "--raw", type=Path, default=settings.data_dir, help="Raíz de los snapshots"
    )
    parser.add_argument(
        "--snapshot", help="Snapshot a normalizar (por defecto, LATEST)"
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Fuente a normalizar (por defecto, todas las que tienen adaptador)",
    )
    parser.add_argument(
        "--staging",
        type=Path,
        help="Raíz de la capa staging (por defecto, data/staging)",
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
    try:
        snapshot = resolve_snapshot(args.raw, args.snapshot)
        sources = select_adapted_sources(load_sources(args.config), args.source)
        if not sources:
            raise ConfigurationError(
                "Ninguna fuente tiene adaptador registrado "
                f"(registrados: {normalizers.registered_sources() or 'ninguno'})"
            )
        staging_root = args.staging or args.raw.parent / "staging"
        summary = normalize_snapshot(sources, snapshot, staging_root)
    except ConfigurationError as exc:
        logger.error("%s", exc)
        return EXIT_CONFIGURATION_ERROR
    logger.info(
        "Fin de normalización: %d exitosas, %d fallidas. Staging: %s",
        len(summary.successful),
        len(summary.failed),
        (staging_root / snapshot.name).resolve(),
    )
    return EXIT_OK if summary.ok else EXIT_FAILURES


if __name__ == "__main__":
    raise SystemExit(main())
