"""Contrato de los collectors y registro por tipo de fuente."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from rutagt.core.errors import ConfigurationError

Source = dict[str, Any]
"""Entrada del catálogo `config/sources.json`."""

CollectionResult = dict[str, Any]
"""Metadatos de procedencia de una descarga, agregados al manifiesto."""

Collector = Callable[[Source, Path], CollectionResult]
"""Descarga una fuente a `destination` y escribe su archivo de procedencia."""

_REGISTRY: dict[str, Collector] = {}


def register_collector(source_type: str) -> Callable[[Collector], Collector]:
    """Registra un collector para un valor del campo `type` del catálogo."""

    def decorator(collector: Collector) -> Collector:
        if source_type in _REGISTRY:
            raise ValueError(f"Ya existe un collector para el tipo {source_type!r}")
        _REGISTRY[source_type] = collector
        return collector

    return decorator


def registered_types() -> list[str]:
    """Tipos de fuente con collector registrado, en orden alfabético."""
    return sorted(_REGISTRY)


def get_collector(source_type: str) -> Collector:
    """Devuelve el collector registrado para un tipo de fuente."""
    try:
        return _REGISTRY[source_type]
    except KeyError:
        raise ConfigurationError(
            f"Tipo de fuente no soportado: {source_type}"
        ) from None


def collect_source(source: Source, output_root: Path) -> CollectionResult:
    """Ejecuta el collector correspondiente al tipo de la fuente."""
    collector = get_collector(source["type"])
    return collector(source, output_root / source["output"])
