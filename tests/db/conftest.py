"""Bases temporales y Alembic para las pruebas de integración.

Cada base se crea en el servidor configurado con `RUTAGT_DB_*` y se elimina al
terminar:

    uv run --env-file .env pytest -m integration
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine

from rutagt.core.settings import PROJECT_ROOT
from rutagt.db.settings import DatabaseSettings


@contextmanager
def _temporary_database() -> Iterator[Engine]:
    """Crea una base vacía, la entrega y la elimina al terminar."""
    settings = DatabaseSettings.from_env()
    name = f"rutagt_test_{uuid4().hex[:12]}"
    admin = create_engine(settings.url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = create_engine(settings.url(name))
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("RUTAGT_DB_NAME", name)
            yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


def _alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["configure_logger"] = False
    return config


def _alembic(revision: str, *, downgrade: bool = False) -> None:
    """Ejecuta Alembic con la configuración del repositorio."""
    config = _alembic_config()
    if downgrade:
        command.downgrade(config, revision)
    else:
        command.upgrade(config, revision)


@pytest.fixture
def temporary_database() -> Callable[[], AbstractContextManager[Engine]]:
    return _temporary_database


@pytest.fixture
def alembic() -> Callable[..., None]:
    return _alembic


@pytest.fixture
def head_revision() -> str | None:
    return ScriptDirectory.from_config(_alembic_config()).get_current_head()


@pytest.fixture(scope="module")
def migrated() -> Iterator[Engine]:
    """Base con todas las migraciones, compartida por las pruebas de un módulo."""
    with _temporary_database() as engine:
        _alembic("head")
        yield engine
