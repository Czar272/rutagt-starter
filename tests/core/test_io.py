"""Pruebas de las utilidades de entrada/salida."""

from datetime import datetime
from pathlib import Path

from rutagt.core import io


def test_write_json_is_utf8_deterministic_and_returns_bytes(tmp_path: Path) -> None:
    path = tmp_path / "anidado" / "dato.json"

    body = io.write_json(path, {"nombre": "Línea 13"})

    assert body == path.read_bytes()
    assert body == '{\n  "nombre": "Línea 13"\n}\n'.encode()
    assert io.read_json(path) == {"nombre": "Línea 13"}


def test_sha256_bytes() -> None:
    assert io.sha256_bytes(b"") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_utc_now_is_iso_8601_with_timezone() -> None:
    value = datetime.fromisoformat(io.utc_now())

    assert value.utcoffset() is not None
    assert value.microsecond == 0


def test_provenance_path() -> None:
    assert io.provenance_path(Path("a/paradas.geojson")) == Path(
        "a/paradas.geojson.provenance.json"
    )
