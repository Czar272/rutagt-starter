"""Pruebas del reporte y de la interfaz `rutagt-profile`."""

import json
from pathlib import Path
from typing import Any

import pytest

from rutagt.core.io import sha256_bytes
from rutagt.core.snapshots import create_snapshot, write_latest
from rutagt.pipeline.profiling import cli
from rutagt.pipeline.profiling.geojson import profile_collection
from rutagt.pipeline.profiling.report import render_report

SNAPSHOT = "20261126T181403Z"
COLLECTION: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-90.5, 14.6]},
            "properties": {"FID": i, "Ruta": "801" if i < 3 else 105, "Nombre": "A|B"},
        }
        for i in range(1, 5)
    ],
}


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    snapshot = create_snapshot(root, SNAPSHOT)
    (snapshot / "muni").mkdir()
    (snapshot / "muni" / "paradas.geojson").write_text(
        json.dumps(COLLECTION), encoding="utf-8"
    )
    (snapshot / "run_manifest.json").write_text("{}", encoding="utf-8")
    write_latest(root, SNAPSHOT)
    return root


def test_report_renders_fields_and_anomalies() -> None:
    report = render_report(
        SNAPSHOT, {"muni/paradas.geojson": profile_collection(COLLECTION)}
    )

    assert report.startswith("# Perfil de datasets\n\nSnapshot `20261126T181403Z`")
    assert "## `muni/paradas.geojson`" in report
    assert "| `FID` | int (4) | 0 | 4 | sí | 1 – 4 | — |" in report
    assert "A\\|B (4)" in report
    assert "- `Ruta`: tipos mezclados ['int', 'str']" in report


def test_report_without_anomalies_says_none() -> None:
    clean = {"features": [COLLECTION["features"][0]]}
    profile = profile_collection(clean)

    assert profile["anomalies"] == []
    assert "- Ninguna" in render_report(SNAPSHOT, {"x.geojson": profile})


def test_profiles_latest_snapshot_into_staging(raw: Path) -> None:
    assert cli.main(["--raw", str(raw)]) == cli.EXIT_OK

    output = raw.parent / "staging" / SNAPSHOT / "profiles"
    profiles = json.loads((output / "profiles.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (output / "profiles.json.provenance.json").read_text(encoding="utf-8")
    )
    source = raw / SNAPSHOT / "muni" / "paradas.geojson"
    assert list(profiles) == ["muni/paradas.geojson"]
    assert profiles["muni/paradas.geojson"]["records"] == 4
    assert (output / "perfil.md").read_text(encoding="utf-8").startswith("# Perfil")
    assert provenance["snapshot_id"] == SNAPSHOT
    assert provenance["inputs"] == [
        {"file": "muni/paradas.geojson", "sha256": sha256_bytes(source.read_bytes())}
    ]
    assert set(provenance["outputs"]) == {"profiles.json", "perfil.md"}


def test_rebuild_replaces_previous_output(raw: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "viejo.txt").write_text("x", encoding="utf-8")

    assert cli.main(["--raw", str(raw), "--output", str(output)]) == cli.EXIT_OK

    assert sorted(p.name for p in output.iterdir()) == [
        "perfil.md",
        "profiles.json",
        "profiles.json.provenance.json",
    ]
    assert not list(tmp_path.glob(".out.*"))


def test_explicit_snapshot_without_geojson_fails(
    raw: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    create_snapshot(raw, "20260101T000000Z")

    exit_code = cli.main(["--raw", str(raw), "--snapshot", "20260101T000000Z"])

    assert exit_code == cli.EXIT_CONFIGURATION_ERROR
    assert "no tiene archivos GeoJSON" in capsys.readouterr().err


def test_invalid_json_is_reported(
    raw: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (raw / SNAPSHOT / "roto.geojson").write_text("{no", encoding="utf-8")

    assert cli.main(["--raw", str(raw)]) == cli.EXIT_CONFIGURATION_ERROR
    assert "roto.geojson no es JSON válido" in capsys.readouterr().err


def test_missing_latest_is_a_configuration_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--raw", str(tmp_path)]) == cli.EXIT_CONFIGURATION_ERROR
    assert "No hay snapshot vigente" in capsys.readouterr().err


def test_invalid_log_format_is_a_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUTAGT_LOG_FORMAT", "xml")

    assert cli.main([]) == cli.EXIT_CONFIGURATION_ERROR


def test_report_lists_codes_repeated_values_and_ranges() -> None:
    features = [
        {"geometry": None, "properties": {"Zona": z, "Dir": d, "Vacio": None}}
        for z, d in [(1, "a"), (1, "b")] + [(i, f"x{i % 9}") for i in range(2, 20)]
    ]
    report = render_report(
        SNAPSHOT, {"x.geojson": profile_collection({"features": features})}
    )

    assert "| `Zona` | int (20) | 0 | 19 | no | 1 – 19 | 1 (2) |" in report
    assert "x2 (2)" in report
    assert "| `Vacio` | null (20) | 20 | 0 | no | — | — |" in report
    assert "- Extensión (lon/lat): —" in report
