"""Errores de `rutagt-load` que se detectan antes de conectarse a la base."""

from pathlib import Path

import pytest

from rutagt.db import cli


@pytest.fixture
def database_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUTAGT_DB_NAME", "rutagt")
    monkeypatch.setenv("RUTAGT_DB_USER", "rutagt")


def test_missing_database_settings_is_a_configuration_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("RUTAGT_DB_NAME", raising=False)

    assert (
        cli.main(["--snapshot", "20261126T181403Z", "--normalized", str(tmp_path)])
        == cli.EXIT_CONFIGURATION_ERROR
    )


@pytest.mark.usefixtures("database_env")
def test_without_latest_snapshot_is_a_configuration_error(tmp_path: Path) -> None:
    assert cli.main(["--raw", str(tmp_path)]) == cli.EXIT_CONFIGURATION_ERROR


@pytest.mark.usefixtures("database_env")
def test_invalid_snapshot_id_is_a_configuration_error(tmp_path: Path) -> None:
    assert cli.main(["--snapshot", "ayer"]) == cli.EXIT_CONFIGURATION_ERROR


@pytest.mark.usefixtures("database_env")
def test_missing_dataset_fails_without_touching_the_database(tmp_path: Path) -> None:
    assert (
        cli.main(["--snapshot", "20261126T181403Z", "--normalized", str(tmp_path)])
        == cli.EXIT_FAILURES
    )


def test_invalid_log_format_is_a_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUTAGT_LOG_FORMAT", "xml")

    assert cli.main([]) == cli.EXIT_CONFIGURATION_ERROR
