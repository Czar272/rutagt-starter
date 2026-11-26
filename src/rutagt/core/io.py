"""Utilidades de entrada/salida deterministas y verificables."""

import hashlib
import json
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """Devuelve la fecha y hora actual en UTC con precisión de segundos (ISO 8601)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    """Calcula el checksum SHA-256 de un contenido binario."""
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> Any:
    """Lee un archivo JSON codificado en UTF-8."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> bytes:
    """Escribe JSON UTF-8 determinista y devuelve los bytes escritos.

    El formato (indentación fija, sin escapar caracteres no ASCII y con salto de
    línea final) garantiza que el checksum dependa solo del contenido.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(body)
    return body


def provenance_path(destination: Path) -> Path:
    """Ruta del archivo de procedencia asociado a un archivo de datos."""
    return destination.with_suffix(destination.suffix + ".provenance.json")


def git_revision(repository: Path) -> str | None:
    """Commit actual del repositorio, o `None` si Git no está disponible.

    Las capas derivadas lo registran como `code_version` (ADR-0032).
    """
    git = shutil.which("git")
    if git is None:
        return None
    result = subprocess.run(  # noqa: S603 - ejecutable resuelto y argumentos fijos
        [git, "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else None


def write_json_atomic(path: Path, value: Any) -> bytes:
    """Como `write_json`, pero escribe en un temporal y lo renombra al terminar.

    Quien lea el archivo ve la versión anterior completa o la nueva completa,
    nunca una escritura a medias.
    """
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        body = write_json(temporary, value)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return body
