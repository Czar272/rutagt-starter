"""Configuración del registro (logging) de RutaGT.

Admite dos formatos:

- ``text``: legible para personas, pensado para desarrollo local.
- ``json``: un objeto JSON por línea, pensado para producción y para enviar a
  una plataforma de observabilidad.

El contexto de correlación (por ejemplo ``run_id`` del pipeline o ``request_id``
de la API) se declara con :func:`log_context` y se agrega a cada registro
emitido dentro de ese bloque.
"""

import json
import logging
import sys
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Literal

LogFormat = Literal["text", "json"]

TEXT_FORMAT = "[RutaGT] %(levelname)s %(message)s"
SERVICE_NAME = "rutagt"

_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "rutagt_log_context", default=None
)


@contextmanager
def log_context(**fields: Any) -> Generator[None]:
    """Agrega campos de correlación a todos los registros emitidos en el bloque."""
    token = _context.set({**current_context(), **fields})
    try:
        yield
    finally:
        _context.reset(token)


def current_context() -> dict[str, Any]:
    """Campos de correlación activos."""
    return dict(_context.get() or {})


class ContextFilter(logging.Filter):
    """Copia el contexto de correlación activo al registro."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.context = current_context()
        return True


class JsonFormatter(logging.Formatter):
    """Formatea cada registro como un objeto JSON en una sola línea."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": SERVICE_NAME,
        }
        entry.update(getattr(record, "context", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def use_utf8_output() -> None:
    """Fuerza UTF-8 en la salida estándar y de error.

    En Windows, cuando la salida se redirige, Python usa la codificación de la
    consola (por ejemplo cp1252) y corrompe los caracteres no ASCII.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (OSError, ValueError):
                continue


def configure_logging(level: str = "INFO", log_format: LogFormat = "text") -> None:
    """Configura el logger raíz de `rutagt` para escribir en la salida de error.

    Se llama una sola vez desde cada punto de entrada. Volver a llamarla
    reemplaza la configuración previa, lo que permite usarla en pruebas.
    """
    use_utf8_output()
    logger = logging.getLogger("rutagt")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(ContextFilter())
    handler.setFormatter(
        JsonFormatter() if log_format == "json" else logging.Formatter(TEXT_FORMAT)
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
