"""Contrato de los adaptadores de fuente y registro por `source_id` (ADR-0033).

Un adaptador recibe el contenido crudo de una fuente de un snapshot y devuelve
un `StagingBatch`. Es una función pura: no lee ni escribe archivos, no accede a
la red ni a la base de datos y no modifica la entrada. El runner se encarga de
leer el snapshot, registrar y escribir la salida con su procedencia.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rutagt.core.errors import ConfigurationError
from rutagt.pipeline.normalizers.models import StagingBatch


@dataclass(frozen=True)
class RawInput:
    """Una fuente cruda de un snapshot, ya leída por el runner."""

    source_id: str
    snapshot_id: str
    content: Any
    provenance: dict[str, Any]


Adapter = Callable[[RawInput], StagingBatch]
"""Traduce el contenido crudo de una fuente a registros de staging."""

_REGISTRY: dict[str, Adapter] = {}


def register_adapter(source_id: str) -> Callable[[Adapter], Adapter]:
    """Registra el adaptador de una fuente del catálogo (`config/sources.json`)."""

    def decorator(adapter: Adapter) -> Adapter:
        if source_id in _REGISTRY:
            raise ValueError(f"Ya existe un adaptador para la fuente {source_id!r}")
        _REGISTRY[source_id] = adapter
        return adapter

    return decorator


def registered_sources() -> list[str]:
    """Fuentes con adaptador registrado, en orden alfabético."""
    return sorted(_REGISTRY)


def get_adapter(source_id: str) -> Adapter:
    """Adaptador registrado para una fuente."""
    try:
        return _REGISTRY[source_id]
    except KeyError:
        raise ConfigurationError(
            f"No hay adaptador registrado para la fuente {source_id}"
        ) from None
