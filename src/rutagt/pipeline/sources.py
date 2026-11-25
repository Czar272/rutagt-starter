"""Carga y selección del catálogo de fuentes (`config/sources.json`)."""

from collections.abc import Iterable
from pathlib import Path

from rutagt.core.errors import ConfigurationError
from rutagt.core.io import read_json
from rutagt.pipeline.collectors.base import Source


def load_sources(config_path: Path) -> list[Source]:
    """Lee el catálogo y verifica su estructura e identificadores únicos."""
    try:
        config = read_json(config_path)
    except (OSError, ValueError) as exc:
        raise ConfigurationError(
            f"No se pudo leer el catálogo {config_path}: {exc}"
        ) from exc
    sources = config.get("sources") if isinstance(config, dict) else None
    if not isinstance(sources, list):
        raise ConfigurationError("La configuración debe contener una lista 'sources'")
    ids = [source.get("id") for source in sources]
    if len(ids) != len(set(ids)):
        raise ConfigurationError("Hay identificadores de fuente duplicados")
    return sources


def select_sources(
    sources: list[Source], requested: Iterable[str], fetch_all: bool
) -> list[Source]:
    """Selecciona todas las fuentes o las solicitadas por identificador."""
    if fetch_all:
        return sources
    requested_set = set(requested)
    selected = [source for source in sources if source["id"] in requested_set]
    missing = requested_set - {source["id"] for source in selected}
    if missing:
        raise ConfigurationError(f"Fuentes desconocidas: {', '.join(sorted(missing))}")
    if not selected:
        raise ConfigurationError("Indique --all o al menos un --source")
    return selected
