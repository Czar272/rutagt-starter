"""${message}

Revisión: ${up_revision}
Anterior: ${down_revision | comma,n}
Fecha: ${create_date}
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}

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
