"""Pruebas de la configuración del registro."""

import logging

import pytest

from rutagt.core.logging import configure_logging


def test_configure_logging_writes_to_stderr_with_prefix(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("WARNING")

    logging.getLogger("rutagt.prueba").info("oculto")
    logging.getLogger("rutagt.prueba").warning("visible")

    err = capsys.readouterr().err
    assert "oculto" not in err
    assert "[RutaGT] WARNING visible" in err


def test_configure_logging_replaces_previous_handlers() -> None:
    configure_logging("INFO")
    configure_logging("INFO")

    assert len(logging.getLogger("rutagt").handlers) == 1
