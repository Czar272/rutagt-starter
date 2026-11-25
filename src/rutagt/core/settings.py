"""Configuración de RutaGT a partir de variables de entorno `RUTAGT_*`."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# src/rutagt/core/settings.py -> raíz del repositorio
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    """Valores de configuración del pipeline."""

    data_dir: Path
    sources_config: Path
    log_level: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Construye la configuración desde el entorno, con valores por defecto.

        Las rutas por defecto apuntan a la raíz del repositorio para que los
        comandos funcionen desde cualquier carpeta.
        """
        env = os.environ if environ is None else environ
        data_dir = env.get("RUTAGT_DATA_DIR") or str(PROJECT_ROOT / "data" / "raw")
        return cls(
            data_dir=Path(data_dir),
            sources_config=PROJECT_ROOT / "config" / "sources.json",
            log_level=(env.get("RUTAGT_LOG_LEVEL") or "INFO").upper(),
        )
