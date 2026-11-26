"""Niveles estimated y community en la escala de calidad (ADR-0031).

Revisión: 0002
Anterior: 0001
Fecha: 2026-11-26
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQL_DIR = Path(__file__).with_suffix("")


def _execute(name: str) -> None:
    # SQL sin parámetros directo al controlador: los `:` y `%` del SQL no se
    # interpretan como marcadores (ADR-0030). Usa la transacción de Alembic.
    driver = op.get_bind().connection.driver_connection
    if driver is None:
        raise RuntimeError("La conexión de Alembic no tiene conexión de controlador")
    driver.execute((SQL_DIR / name).read_text("utf-8"))


def upgrade() -> None:
    _execute("upgrade.sql")


def downgrade() -> None:
    _execute("downgrade.sql")
