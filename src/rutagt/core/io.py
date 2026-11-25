"""Utilidades de entrada/salida deterministas y verificables."""

import hashlib
import json
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
