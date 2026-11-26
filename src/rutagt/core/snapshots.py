"""Snapshots inmutables de la capa cruda (ADR-0032).

Cada ejecución del recolector escribe en `<raíz>/<snapshot_id>/`, un directorio
nuevo que nunca se reutiliza. `<raíz>/LATEST` contiene el identificador del
último snapshot completo, que es el que leen por defecto las etapas siguientes.
"""

import re
from datetime import UTC, datetime
from pathlib import Path

from rutagt.core.errors import ConfigurationError

SNAPSHOT_ID_FORMAT = "%Y%m%dT%H%M%SZ"
SNAPSHOT_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z$")
LATEST_FILE = "LATEST"


def snapshot_id_for(moment: datetime) -> str:
    """Identificador `AAAAMMDDTHHMMSSZ` del instante dado, convertido a UTC."""
    if moment.tzinfo is None:
        raise ValueError("El instante del snapshot debe tener zona horaria")
    return moment.astimezone(UTC).strftime(SNAPSHOT_ID_FORMAT)


def validate_snapshot_id(snapshot_id: str) -> str:
    """Devuelve el identificador si tiene el formato válido."""
    if not SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id):
        raise ConfigurationError(
            f"Identificador de snapshot inválido: {snapshot_id!r} "
            "(se espera AAAAMMDDTHHMMSSZ)"
        )
    return snapshot_id


def create_snapshot(root: Path, snapshot_id: str) -> Path:
    """Crea el directorio del snapshot; falla si ya existe para no sobrescribirlo."""
    path = root / validate_snapshot_id(snapshot_id)
    root.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError:
        raise ConfigurationError(
            f"El snapshot {snapshot_id} ya existe en {root}; "
            "los snapshots no se sobrescriben, vuelve a ejecutar"
        ) from None
    return path


def write_latest(root: Path, snapshot_id: str) -> None:
    """Marca el snapshot como vigente con un reemplazo atómico de `LATEST`."""
    if not (root / validate_snapshot_id(snapshot_id)).is_dir():
        raise ConfigurationError(f"No existe el snapshot {snapshot_id} en {root}")
    temporary = root / f".{LATEST_FILE}.tmp"
    temporary.write_text(snapshot_id + "\n", encoding="utf-8")
    temporary.replace(root / LATEST_FILE)


def read_latest(root: Path) -> str | None:
    """Identificador del snapshot vigente, o `None` si todavía no hay ninguno."""
    path = root / LATEST_FILE
    if not path.is_file():
        return None
    return validate_snapshot_id(path.read_text(encoding="utf-8").strip())


def resolve_snapshot(root: Path, snapshot_id: str | None = None) -> Path:
    """Directorio de un snapshot explícito o, si no se indica, del vigente."""
    chosen = snapshot_id or read_latest(root)
    if chosen is None:
        raise ConfigurationError(
            f"No hay snapshot vigente en {root}; ejecuta `rutagt-collect fetch --all`"
        )
    path = root / validate_snapshot_id(chosen)
    if not path.is_dir():
        raise ConfigurationError(f"No existe el snapshot {chosen} en {root}")
    return path
