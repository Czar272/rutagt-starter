"""Normalizers: traducen `data/raw/` a la capa staging y luego a la canónica.

Importar este paquete registra los adaptadores incluidos en RutaGT (ADR-0033).
"""

from rutagt.pipeline.normalizers import transmetro_stops
from rutagt.pipeline.normalizers.base import (
    RawInput,
    get_adapter,
    register_adapter,
    registered_sources,
)

__all__ = [
    "RawInput",
    "get_adapter",
    "register_adapter",
    "registered_sources",
    "transmetro_stops",
]
