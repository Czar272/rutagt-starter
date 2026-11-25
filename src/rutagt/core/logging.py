"""Configuración del registro (logging) de RutaGT."""

import logging
import sys

LOG_FORMAT = "[RutaGT] %(levelname)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configura el logger raíz de `rutagt` para escribir en la salida de error.

    Se llama una sola vez desde cada punto de entrada. Volver a llamarla
    reemplaza la configuración previa, lo que permite usarla en pruebas.
    """
    logger = logging.getLogger("rutagt")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
