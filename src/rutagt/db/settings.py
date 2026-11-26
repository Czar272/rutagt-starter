"""Parámetros de conexión a la base de datos desde variables `RUTAGT_DB_*`."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import URL

from rutagt.core.errors import ConfigurationError

DRIVER = "postgresql+psycopg"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5432


@dataclass(frozen=True)
class DatabaseSettings:
    """Parámetros de conexión a PostgreSQL."""

    host: str
    port: int
    name: str
    user: str
    password: str | None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "DatabaseSettings":
        """Lee la conexión del entorno.

        `RUTAGT_DB_NAME` y `RUTAGT_DB_USER` son obligatorias; el servidor usa
        `localhost:5432` por defecto y la contraseña es opcional.
        """
        env = os.environ if environ is None else environ
        missing = [k for k in ("RUTAGT_DB_NAME", "RUTAGT_DB_USER") if not env.get(k)]
        if missing:
            raise ConfigurationError(
                "Faltan variables de conexión a la base de datos: "
                + ", ".join(missing)
                + " (usa `uv run --env-file .env ...`)"
            )
        port_text = env.get("RUTAGT_DB_PORT") or str(DEFAULT_PORT)
        try:
            port = int(port_text)
        except ValueError:
            raise ConfigurationError(
                f"RUTAGT_DB_PORT debe ser un número, no {port_text!r}"
            ) from None
        if not 0 < port < 65536:
            raise ConfigurationError(f"RUTAGT_DB_PORT fuera de rango: {port}")
        return cls(
            host=env.get("RUTAGT_DB_HOST") or DEFAULT_HOST,
            port=port,
            name=env["RUTAGT_DB_NAME"],
            user=env["RUTAGT_DB_USER"],
            password=env.get("RUTAGT_DB_PASSWORD") or None,
        )

    def url(self, database: str | None = None) -> URL:
        """URL de SQLAlchemy; `database` permite apuntar a otra base del servidor."""
        return URL.create(
            DRIVER,
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database or self.name,
        )
