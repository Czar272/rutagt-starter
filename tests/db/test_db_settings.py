"""Pruebas de los parámetros de conexión a la base de datos."""

import pytest

from rutagt.core.errors import ConfigurationError
from rutagt.db.settings import DatabaseSettings

BASE = {"RUTAGT_DB_NAME": "rutagt", "RUTAGT_DB_USER": "rutagt"}


def test_defaults_for_host_port_and_password() -> None:
    settings = DatabaseSettings.from_env(BASE)

    assert settings.host == "localhost"
    assert settings.port == 5432
    assert settings.password is None


def test_environment_values_are_used() -> None:
    settings = DatabaseSettings.from_env(
        {
            **BASE,
            "RUTAGT_DB_HOST": "db",
            "RUTAGT_DB_PORT": "6543",
            "RUTAGT_DB_PASSWORD": "secreto",
        }
    )

    assert (settings.host, settings.port, settings.password) == ("db", 6543, "secreto")


@pytest.mark.parametrize("missing", ["RUTAGT_DB_NAME", "RUTAGT_DB_USER"])
def test_missing_required_variable_is_reported(missing: str) -> None:
    env = {k: v for k, v in BASE.items() if k != missing}

    with pytest.raises(ConfigurationError, match=missing):
        DatabaseSettings.from_env(env)


@pytest.mark.parametrize("port", ["abc", "0", "70000"])
def test_invalid_port_is_rejected(port: str) -> None:
    with pytest.raises(ConfigurationError, match="RUTAGT_DB_PORT"):
        DatabaseSettings.from_env({**BASE, "RUTAGT_DB_PORT": port})


def test_url_escapes_password_and_can_target_another_database() -> None:
    special = "p@ss:/w"
    settings = DatabaseSettings.from_env({**BASE, "RUTAGT_DB_PASSWORD": special})

    url = settings.url("otra")

    assert url.drivername == "postgresql+psycopg"
    assert url.database == "otra"
    assert url.password == special
    assert "p%40ss%3A%2Fw" in url.render_as_string(hide_password=False)
    assert settings.url().database == "rutagt"


def test_reads_process_environment_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUTAGT_DB_NAME", "desde_entorno")
    monkeypatch.setenv("RUTAGT_DB_USER", "rutagt")

    assert DatabaseSettings.from_env().name == "desde_entorno"
