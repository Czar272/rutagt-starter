"""Pruebas de las utilidades de entrada/salida."""

from datetime import datetime
from pathlib import Path

import pytest

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


def test_git_revision_of_the_project() -> None:
    revision = io.git_revision(Path(__file__).resolve().parents[2])

    assert revision is not None
    assert len(revision) == 40


def test_git_revision_outside_a_repository(tmp_path: Path) -> None:
    assert io.git_revision(tmp_path) is None


def test_git_revision_without_git(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("rutagt.core.io.shutil.which", lambda name: None)

    assert io.git_revision(tmp_path) is None


def test_write_json_atomic_replaces_whole_file(tmp_path: Path) -> None:
    path = tmp_path / "salida.json"
    path.write_text("viejo", encoding="utf-8")

    body = io.write_json_atomic(path, {"a": 1})

    assert path.read_bytes() == body
    assert not list(tmp_path.glob(".*.tmp"))


def test_write_json_atomic_keeps_previous_file_on_failure(tmp_path: Path) -> None:
    path = tmp_path / "salida.json"
    path.write_text("viejo", encoding="utf-8")

    with pytest.raises(TypeError):
        io.write_json_atomic(path, {"a": object()})

    assert path.read_text(encoding="utf-8") == "viejo"
    assert not list(tmp_path.glob(".*.tmp"))
