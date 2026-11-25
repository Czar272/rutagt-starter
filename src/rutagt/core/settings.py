"""Configuración de RutaGT a partir de variables de entorno `RUTAGT_*`."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from rutagt.core.errors import ConfigurationError
from rutagt.core.logging import LogFormat

# src/rutagt/core/settings.py -> raíz del repositorio
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_FORMATS = ("text", "json")


@dataclass(frozen=True)
class Settings:
    """Valores de configuración del pipeline."""

    data_dir: Path
    sources_config: Path
    log_level: str
    log_format: LogFormat

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Construye la configuración desde el entorno, con valores por defecto.

        Las rutas por defecto apuntan a la raíz del repositorio para que los
        comandos funcionen desde cualquier carpeta.
        """
        env = os.environ if environ is None else environ
        data_dir = env.get("RUTAGT_DATA_DIR") or str(PROJECT_ROOT / "data" / "raw")
        log_format = (env.get("RUTAGT_LOG_FORMAT") or "text").lower()
        if log_format not in LOG_FORMATS:
            raise ConfigurationError(
                f"RUTAGT_LOG_FORMAT debe ser 'text' o 'json', no {log_format!r}"
            )
        return cls(
            data_dir=Path(data_dir),
            sources_config=PROJECT_ROOT / "config" / "sources.json",
            log_level=(env.get("RUTAGT_LOG_LEVEL") or "INFO").upper(),
            log_format=cast(LogFormat, log_format),
        )
