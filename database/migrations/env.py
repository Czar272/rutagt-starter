"""Entorno de Alembic para el esquema canónico de RutaGT (ADR-0030).

La conexión se construye desde las variables `RUTAGT_DB_*`. Las migraciones
se escriben en SQL explícito y se ejecutan en línea contra la base; el modo
`--sql` (sin conexión) no está soportado porque el SQL se envía directamente
al controlador.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from rutagt.core.errors import ConfigurationError
from rutagt.db.settings import DatabaseSettings

config = context.config
if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
    fileConfig(config.config_file_name)


def run_migrations_online() -> None:
    """Aplica las migraciones con una transacción por revisión."""
    engine = create_engine(DatabaseSettings.from_env().url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            transaction_per_migration=True,
            version_table_schema="public",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise ConfigurationError(
        "Las migraciones de RutaGT no admiten el modo --sql; ejecútalas contra una base"
    )
run_migrations_online()
