"""Pruebas de la interfaz de línea de comandos `rutagt-collect`."""

import json
from pathlib import Path
from typing import Any

import pytest

from rutagt.core.errors import SourceError
from rutagt.core.snapshots import read_latest
from rutagt.pipeline import cli

SOURCES = [
    {"id": "a", "type": "html_links", "name": "Fuente A", "output": "a.json"},
    {"id": "b", "type": "html_links", "name": "Fuente B", "output": "b.json"},
    {
        "id": "c",
        "type": "html_links",
        "name": "Fuente C",
        "output": "c.json",
        "disabled_reason": "El sitio responde HTTP 403 a clientes automatizados",
    },
]


def snapshots(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir())


def manifest_of(root: Path) -> dict[str, Any]:
    (snapshot,) = snapshots(root)
    data: dict[str, Any] = json.loads(
        (snapshot / "run_manifest.json").read_text(encoding="utf-8")
    )
    return data


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": SOURCES}), encoding="utf-8")
    return path


def test_list_command_prints_sources(
    config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--config", str(config), "list"]) == cli.EXIT_OK

    output = capsys.readouterr().out
    assert "Fuente A" in output
    assert "Fuente B" in output
    assert "Fuente C [deshabilitada]" in output


@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        (SourceError("fuente caída"), "fuente caída"),
        (KeyError("features"), "KeyError('features')"),
    ],
    ids=["controlada", "inesperada"],
)
def test_fetch_writes_manifest_and_continues_after_failures(
    monkeypatch: pytest.MonkeyPatch,
    config: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    failure: Exception,
    expected_error: str,
) -> None:
    def fake_collect_source(source: dict[str, Any], output: Path) -> dict[str, Any]:
        if source["id"] == "a":
            raise failure
        return {"source_id": source["id"], "record_count": 2, "quality_warnings": []}

    monkeypatch.setattr(cli, "collect_source", fake_collect_source)
    output = tmp_path / "raw"

    exit_code = cli.main(
        ["--config", str(config), "fetch", "--all", "--output", str(output)]
    )

    manifest = manifest_of(output)
    assert exit_code == cli.EXIT_SOURCE_FAILURES
    assert [r["source_id"] for r in manifest["successful"]] == ["b"]
    assert [(f["source_id"], f["error"]) for f in manifest["failed"]] == [
        ("a", expected_error)
    ]
    assert manifest["summary"] == {
        "requested": 2,
        "successful": 1,
        "failed": 1,
        "skipped": 1,
    }
    assert manifest["skipped"] == [
        {"source_id": "c", "reason": SOURCES[2]["disabled_reason"]}
    ]
    assert len(manifest["run_id"]) == 32
    assert all(
        entry["duration_seconds"] >= 0
        for entry in manifest["successful"] + manifest["failed"]
    )
    assert manifest["complete"] is False
    assert read_latest(output) is None
    logs = capsys.readouterr().err
    assert "OK b: 2 registros, 0 advertencias" in logs
    assert "incompleto" in logs


def test_fetch_returns_zero_when_every_source_succeeds(
    monkeypatch: pytest.MonkeyPatch, config: Path, tmp_path: Path
) -> None:
    destinations: list[Path] = []

    def fake_collect_source(source: dict[str, Any], output: Path) -> dict[str, Any]:
        destinations.append(output)
        return {}

    monkeypatch.setattr(cli, "collect_source", fake_collect_source)

    exit_code = cli.main(
        ["--config", str(config), "fetch", "--all", "--output", str(tmp_path)]
    )

    manifest = manifest_of(tmp_path)
    snapshot = tmp_path / manifest["snapshot_id"]
    assert exit_code == cli.EXIT_OK
    assert manifest["complete"] is True
    assert manifest["scope"] == "all"
    assert read_latest(tmp_path) == manifest["snapshot_id"]
    assert destinations == [snapshot, snapshot]


def test_selected_sources_never_become_latest(
    monkeypatch: pytest.MonkeyPatch,
    config: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "collect_source", lambda source, output: {})

    exit_code = cli.main(
        ["--config", str(config), "fetch", "--source", "c", "--output", str(tmp_path)]
    )

    manifest = manifest_of(tmp_path)
    assert exit_code == cli.EXIT_OK
    assert (manifest["scope"], manifest["complete"]) == ("selected", False)
    assert manifest["skipped"] == []
    assert read_latest(tmp_path) is None
    assert "parcial (--source)" in capsys.readouterr().err


def test_each_fetch_creates_a_new_snapshot_without_touching_previous(
    monkeypatch: pytest.MonkeyPatch, config: Path, tmp_path: Path
) -> None:
    ids = iter(["20261126T174500Z", "20261126T180000Z"])
    monkeypatch.setattr(cli, "snapshot_id_for", lambda moment: next(ids))
    monkeypatch.setattr(cli, "collect_source", lambda source, output: {})
    args = ["--config", str(config), "fetch", "--all", "--output", str(tmp_path)]

    assert cli.main(args) == cli.EXIT_OK
    first = snapshots(tmp_path)[0] / "run_manifest.json"
    before = first.read_bytes()
    assert cli.main(args) == cli.EXIT_OK

    assert [p.name for p in snapshots(tmp_path)] == [
        "20261126T174500Z",
        "20261126T180000Z",
    ]
    assert first.read_bytes() == before
    assert read_latest(tmp_path) == "20261126T180000Z"


def test_snapshot_collision_is_a_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
    config: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "snapshot_id_for", lambda moment: "20261126T174500Z")
    monkeypatch.setattr(cli, "collect_source", lambda source, output: {})
    args = ["--config", str(config), "fetch", "--all", "--output", str(tmp_path)]

    assert cli.main(args) == cli.EXIT_OK
    assert cli.main(args) == cli.EXIT_CONFIGURATION_ERROR
    assert "no se sobrescriben" in capsys.readouterr().err


def test_configuration_errors_return_exit_code_two(
    config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = cli.main(["--config", str(config), "fetch", "--source", "z"])

    assert exit_code == cli.EXIT_CONFIGURATION_ERROR
    assert "Fuentes desconocidas: z" in capsys.readouterr().err


def test_json_log_format_includes_run_and_source_context(
    monkeypatch: pytest.MonkeyPatch,
    config: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RUTAGT_LOG_FORMAT", "json")
    monkeypatch.setattr(cli, "collect_source", lambda source, output: {})

    cli.main(
        ["--config", str(config), "fetch", "--source", "a", "--output", str(tmp_path)]
    )

    manifest = manifest_of(tmp_path)
    entries = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert {entry["run_id"] for entry in entries} == {manifest["run_id"]}
    assert any(entry.get("source_id") == "a" for entry in entries)
    assert all(entry["service"] == "rutagt" for entry in entries)


def test_invalid_log_format_is_a_configuration_error(
    monkeypatch: pytest.MonkeyPatch, config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("RUTAGT_LOG_FORMAT", "xml")

    assert cli.main(["--config", str(config), "list"]) == cli.EXIT_CONFIGURATION_ERROR
    assert "RUTAGT_LOG_FORMAT" in capsys.readouterr().err
