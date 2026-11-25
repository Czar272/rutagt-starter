"""Pruebas de la configuración del registro."""

import json
import logging

import pytest

from rutagt.core.logging import configure_logging, log_context


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


def test_json_format_emits_one_object_per_line_with_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO", "json")

    with log_context(run_id="abc"), log_context(source_id="fuente"):
        logging.getLogger("rutagt.prueba").info("hola %s", "mundo")
    logging.getLogger("rutagt.prueba").info("sin contexto")

    first, second = (json.loads(line) for line in capsys.readouterr().err.splitlines())
    assert first["message"] == "hola mundo"
    assert first["level"] == "INFO"
    assert first["logger"] == "rutagt.prueba"
    assert first["run_id"] == "abc"
    assert first["source_id"] == "fuente"
    assert "run_id" not in second


def test_json_format_includes_exception_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO", "json")

    try:
        raise ValueError("falla")
    except ValueError:
        logging.getLogger("rutagt.prueba").exception("error")

    entry = json.loads(capsys.readouterr().err)
    assert "ValueError: falla" in entry["exception"]
