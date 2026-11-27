"""Carga y selección del catálogo de fuentes (`config/sources.json`).

Una fuente con `disabled_reason` queda deshabilitada: `--all` la omite y solo se
descarga si se pide explícitamente con `--source`. Una capa de paradas puede
declarar con `shapes_source` la fuente de trazados de sus rutas, que se usa
para validar la distancia de cada parada a su ruta (ADR-0034).

Las fuentes que llegan a la capa canónica declaran su `agency` (de
`config/agencies.json`) y su `source_kind`; una capa de andenes declara
`group_stations` para agruparlos en estaciones (ADR-0035).
"""

import re
from collections.abc import Iterable
from pathlib import Path

from rutagt.core.errors import ConfigurationError
from rutagt.core.io import read_json
from rutagt.pipeline.collectors.base import Source

AGENCY_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


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
    known = set(ids)
    for source in sources:
        shapes_source = source.get("shapes_source")
        if shapes_source is not None and shapes_source not in known:
            raise ConfigurationError(
                f"La fuente {source.get('id')} usa 'shapes_source' desconocida: "
                f"{shapes_source}"
            )
        agency = source.get("agency")
        if agency is not None and not (
            isinstance(agency, str) and AGENCY_ID.fullmatch(agency)
        ):
            raise ConfigurationError(
                f"La fuente {source.get('id')} tiene una 'agency' inválida: {agency!r}"
            )
        if not isinstance(source.get("group_stations", False), bool):
            raise ConfigurationError(
                f"La fuente {source.get('id')} tiene un 'group_stations' no booleano"
            )
        reason = source.get("disabled_reason")
        if reason is not None and not (isinstance(reason, str) and reason.strip()):
            raise ConfigurationError(
                f"La fuente {source.get('id')} tiene un 'disabled_reason' vacío"
            )
    return sources


def is_enabled(source: Source) -> bool:
    """Indica si la fuente participa en `--all`."""
    return source.get("disabled_reason") is None


def select_sources(
    sources: list[Source], requested: Iterable[str], fetch_all: bool
) -> list[Source]:
    """Selecciona las fuentes habilitadas o las solicitadas por identificador."""
    if fetch_all:
        return [source for source in sources if is_enabled(source)]
    requested_set = set(requested)
    selected = [source for source in sources if source["id"] in requested_set]
    missing = requested_set - {source["id"] for source in selected}
    if missing:
        raise ConfigurationError(f"Fuentes desconocidas: {', '.join(sorted(missing))}")
    if not selected:
        raise ConfigurationError("Indique --all o al menos un --source")
    return selected
