"""Pruebas de la configuración por variables de entorno."""

from pathlib import Path

import pytest

from rutagt.core.errors import ConfigurationError
from rutagt.core.settings import PROJECT_ROOT, Settings


def test_defaults_point_to_repository_root() -> None:
    settings = Settings.from_env({})

    assert settings.data_dir == PROJECT_ROOT / "data" / "raw"
    assert settings.sources_config == PROJECT_ROOT / "config" / "sources.json"
    assert settings.sources_config.exists()
    assert settings.log_level == "INFO"
    assert settings.log_format == "text"


def test_environment_overrides_defaults() -> None:
    settings = Settings.from_env(
        {"RUTAGT_DATA_DIR": "/srv/rutagt/raw", "RUTAGT_LOG_LEVEL": "debug"}
    )

    assert settings.data_dir == Path("/srv/rutagt/raw")
    assert settings.log_level == "DEBUG"


def test_empty_values_fall_back_to_defaults() -> None:
    settings = Settings.from_env({"RUTAGT_DATA_DIR": "", "RUTAGT_LOG_LEVEL": ""})

    assert settings.data_dir == PROJECT_ROOT / "data" / "raw"
    assert settings.log_level == "INFO"


def test_log_format_is_validated() -> None:
    assert Settings.from_env({"RUTAGT_LOG_FORMAT": "JSON"}).log_format == "json"
    with pytest.raises(ConfigurationError, match="RUTAGT_LOG_FORMAT"):
        Settings.from_env({"RUTAGT_LOG_FORMAT": "xml"})
