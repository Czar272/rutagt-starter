"""Pruebas de los snapshots inmutables de la capa cruda (ADR-0032)."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from rutagt.core.errors import ConfigurationError
from rutagt.core.snapshots import (
    LATEST_FILE,
    create_snapshot,
    read_latest,
    resolve_snapshot,
    snapshot_id_for,
    validate_snapshot_id,
    write_latest,
)

SNAPSHOT = "20261126T174500Z"


def test_snapshot_id_uses_utc_basic_iso_format() -> None:
    guatemala = timezone(timedelta(hours=-6))
    moment = datetime(2026, 11, 26, 11, 45, 0, tzinfo=guatemala)

    assert snapshot_id_for(moment) == SNAPSHOT
    assert snapshot_id_for(moment.astimezone(UTC)) == SNAPSHOT


def test_snapshot_id_requires_timezone() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        snapshot_id_for(datetime(2026, 11, 26, 17, 45))


@pytest.mark.parametrize(
    "value", ["", "latest", "2026-11-26T17:45:00Z", "20261126T1745Z", "../x"]
)
def test_invalid_snapshot_ids_are_rejected(value: str) -> None:
    with pytest.raises(ConfigurationError, match="inválido"):
        validate_snapshot_id(value)


def test_create_snapshot_makes_a_new_directory(tmp_path: Path) -> None:
    root = tmp_path / "raw"

    path = create_snapshot(root, SNAPSHOT)

    assert path == root / SNAPSHOT
    assert path.is_dir()


def test_existing_snapshot_is_never_reused(tmp_path: Path) -> None:
    path = create_snapshot(tmp_path, SNAPSHOT)
    (path / "data.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="no se sobrescriben"):
        create_snapshot(tmp_path, SNAPSHOT)

    assert (path / "data.json").read_text(encoding="utf-8") == "{}"


def test_latest_round_trip(tmp_path: Path) -> None:
    create_snapshot(tmp_path, SNAPSHOT)

    write_latest(tmp_path, SNAPSHOT)

    assert (tmp_path / LATEST_FILE).read_text(encoding="utf-8") == SNAPSHOT + "\n"
    assert read_latest(tmp_path) == SNAPSHOT
    assert not list(tmp_path.glob(".*.tmp"))


def test_latest_replaces_previous_value(tmp_path: Path) -> None:
    newer = "20261127T080000Z"
    for snapshot in (SNAPSHOT, newer):
        create_snapshot(tmp_path, snapshot)
        write_latest(tmp_path, snapshot)

    assert read_latest(tmp_path) == newer


def test_latest_must_point_to_an_existing_snapshot(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="No existe"):
        write_latest(tmp_path, SNAPSHOT)


def test_read_latest_without_snapshots_returns_none(tmp_path: Path) -> None:
    assert read_latest(tmp_path) is None


def test_resolve_snapshot_defaults_to_latest(tmp_path: Path) -> None:
    create_snapshot(tmp_path, SNAPSHOT)
    write_latest(tmp_path, SNAPSHOT)

    assert resolve_snapshot(tmp_path) == tmp_path / SNAPSHOT


def test_resolve_explicit_snapshot(tmp_path: Path) -> None:
    older = "20260822T201216Z"
    create_snapshot(tmp_path, older)
    create_snapshot(tmp_path, SNAPSHOT)
    write_latest(tmp_path, SNAPSHOT)

    assert resolve_snapshot(tmp_path, older) == tmp_path / older


def test_resolve_without_latest_explains_how_to_fetch(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="rutagt-collect fetch"):
        resolve_snapshot(tmp_path)


def test_resolve_missing_snapshot_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="No existe"):
        resolve_snapshot(tmp_path, SNAPSHOT)
