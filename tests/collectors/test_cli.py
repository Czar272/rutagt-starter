"""Pruebas de la interfaz de línea de comandos y de la selección de fuentes."""

import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SOURCES = [
    {"id": "a", "type": "html_links", "name": "Fuente A", "output": "a.json"},
    {"id": "b", "type": "html_links", "name": "Fuente B", "output": "b.json"},
]


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": SOURCES}), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ({"sources": {}}, "lista 'sources'"),
        ({"sources": [{"id": "x"}, {"id": "x"}]}, "duplicados"),
    ],
)
def test_load_sources_rejects_invalid_configuration(
    collect: ModuleType, tmp_path: Path, content: dict[str, Any], message: str
) -> None:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(collect.CollectorError, match=message):
        collect.load_sources(path)


def test_select_sources(collect: ModuleType) -> None:
    assert collect.select_sources(SOURCES, [], fetch_all=True) == SOURCES
    assert collect.select_sources(SOURCES, ["b"], fetch_all=False) == [SOURCES[1]]


@pytest.mark.parametrize(
    ("requested", "message"),
    [(["z"], "desconocidas: z"), ([], "Indique --all")],
)
def test_select_sources_rejects_invalid_requests(
    collect: ModuleType, requested: list[str], message: str
) -> None:
    with pytest.raises(collect.CollectorError, match=message):
        collect.select_sources(SOURCES, requested, fetch_all=False)


def test_list_command_prints_sources(
    collect: ModuleType, config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert collect.main(["--config", str(config), "list"]) == 0

    output = capsys.readouterr().out
    assert "Fuente A" in output
    assert "Fuente B" in output


def test_fetch_writes_manifest_and_continues_after_failures(
    collect: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    config: Path,
    tmp_path: Path,
) -> None:
    def fake_collect_source(source: dict[str, Any], output: Path) -> dict[str, Any]:
        if source["id"] == "a":
            raise collect.CollectorError("fuente caída")
        return {"source_id": source["id"], "record_count": 2, "quality_warnings": []}

    monkeypatch.setattr(collect, "collect_source", fake_collect_source)
    output = tmp_path / "raw"

    exit_code = collect.main(
        ["--config", str(config), "fetch", "--all", "--output", str(output)]
    )

    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert [r["source_id"] for r in manifest["successful"]] == ["b"]
    assert manifest["failed"] == [{"source_id": "a", "error": "fuente caída"}]


def test_fetch_returns_zero_when_every_source_succeeds(
    collect: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    config: Path,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        collect, "collect_source", lambda source, output: {"record_count": 1}
    )

    exit_code = collect.main(
        ["--config", str(config), "fetch", "--source", "a", "--output", str(tmp_path)]
    )

    assert exit_code == 0


def test_configuration_errors_return_exit_code_two(
    collect: ModuleType, config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = collect.main(["--config", str(config), "fetch", "--source", "z"])

    assert exit_code == 2
    assert "Fuentes desconocidas" in capsys.readouterr().err
