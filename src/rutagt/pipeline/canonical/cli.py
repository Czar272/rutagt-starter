"""Interfaz de línea de comandos del constructor canónico (`rutagt-canonical`).

Combina los lotes de staging de un snapshot (por defecto, `LATEST`) en
`data/normalized/<snapshot>/canonical.json` (ADR-0035). Códigos de salida:
0 éxito, 1 falta un lote, no es válido o tiene problemas `error`,
2 error de configuración.
"""

import argparse
import logging
from pathlib import Path

from rutagt.core.errors import ConfigurationError, SourceError
from rutagt.core.logging import configure_logging, log_context
from rutagt.core.settings import PROJECT_ROOT, Settings
from rutagt.core.snapshots import resolve_snapshot
from rutagt.pipeline.canonical.runner import (
    DATASET_FILE,
    build_snapshot,
    canonical_sources,
    counts,
    load_agencies,
    load_ruteros,
)
from rutagt.pipeline.sources import load_sources

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_CONFIGURATION_ERROR = 2

AGENCIES_CONFIG = PROJECT_ROOT / "config" / "agencies.json"
RUTEROS_DIR = PROJECT_ROOT / "data" / "reference" / "ruteros"


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rutagt-canonical",
        description="Combina la capa staging de un snapshot en la red canónica",
    )
    parser.add_argument("--config", type=Path, default=settings.sources_config)
    parser.add_argument("--agencies", type=Path, default=AGENCIES_CONFIG)
    parser.add_argument(
        "--ruteros",
        type=Path,
        default=RUTEROS_DIR,
        help="Directorio de ruteros oficiales transcritos (ADR-0036)",
    )
    parser.add_argument(
        "--raw", type=Path, default=settings.data_dir, help="Raíz de los snapshots"
    )
    parser.add_argument("--snapshot", help="Snapshot a combinar (por defecto, LATEST)")
    parser.add_argument(
        "--staging", type=Path, help="Raíz de staging (por defecto, data/staging)"
    )
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
    try:
        snapshot = resolve_snapshot(args.raw, args.snapshot)
        sources = canonical_sources(load_sources(args.config))
        if not sources:
            raise ConfigurationError("Ninguna fuente del catálogo declara 'agency'")
        agencies = load_agencies(args.agencies)
        ruteros = load_ruteros(args.ruteros)
        normalized_root = args.normalized or args.raw.parent / "normalized"
        with log_context(snapshot_id=snapshot.name):
            dataset = build_snapshot(
                sources,
                agencies,
                snapshot,
                args.staging or args.raw.parent / "staging",
                normalized_root,
                ruteros,
            )
    except ConfigurationError as exc:
        logger.error("%s", exc)
        return EXIT_CONFIGURATION_ERROR
    except SourceError as exc:
        logger.error("%s", exc)
        return EXIT_FAILURES
    logger.info(
        "Red canónica %s: %s. Archivo: %s",
        snapshot.name,
        counts(dataset),
        (normalized_root / snapshot.name / DATASET_FILE).resolve(),
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
