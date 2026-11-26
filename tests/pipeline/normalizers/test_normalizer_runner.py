"""Pruebas del runner y de la interfaz `rutagt-normalize`."""

import json
from pathlib import Path
from typing import Any

import pytest

from rutagt.core.io import sha256_bytes, write_json
from rutagt.core.snapshots import create_snapshot, write_latest
from rutagt.pipeline.normalizers import base, cli, runner
from rutagt.pipeline.normalizers.models import (
    Issue,
    Severity,
    SourceRef,
    StagedShape,
    StagedStop,
    StagingBatch,
)
from rutagt.pipeline.normalizers.runner import (
    normalize_snapshot,
    select_adapted_sources,
)

SNAPSHOT = "20261126T181403Z"
SOURCES = [
    {
        "id": "muni_paradas",
        "type": "arcgis_feature_service",
        "output": "muni/paradas.geojson",
    },
    {
        "id": "muni_rutas",
        "type": "arcgis_feature_service",
        "output": "muni/rutas.geojson",
    },
    {"id": "sin_adaptador", "type": "html_links", "output": "otra.json"},
]
COLLECTION = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-90.5, 14.6]},
            "properties": {"FID": 1, "Nombre": "Parada 1"},
        },
        {
            "type": "Feature",
            "geometry": None,
            "properties": {"FID": 2, "Nombre": "Sin punto"},
        },
    ],
}


def stops_adapter(raw: base.RawInput) -> StagingBatch:
    """Adaptador mínimo: un `StagedStop` por punto y un error por geometría faltante."""
    records = []
    issues = []
    for feature in raw.content["features"]:
        props = feature["properties"]
        ref = SourceRef(
            source_id=raw.source_id, external_id=str(props["FID"]), raw=props
        )
        if feature["geometry"] is None:
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code="sin_geometria",
                    message="Registro sin geometría",
                    external_id=ref.external_id,
                )
            )
            continue
        lon, lat = feature["geometry"]["coordinates"]
        records.append(
            StagedStop(source=ref, name=props["Nombre"], position=(lon, lat))
        )
    return StagingBatch(
        source_id=raw.source_id,
        snapshot_id=raw.snapshot_id,
        records=tuple(records),
        issues=tuple(issues),
    )


@pytest.fixture(autouse=True)
def registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, base.Adapter]:
    adapters: dict[str, base.Adapter] = {
        "muni_paradas": stops_adapter,
        "muni_rutas": stops_adapter,
    }
    monkeypatch.setattr(base, "_REGISTRY", adapters)
    return adapters


def write_raw(snapshot: Path, relative: str, value: Any) -> None:
    path = snapshot / relative
    body = write_json(path, value)
    write_json(
        path.with_name(path.name + ".provenance.json"), {"sha256": sha256_bytes(body)}
    )


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    snapshot = create_snapshot(root, SNAPSHOT)
    write_raw(snapshot, "muni/paradas.geojson", COLLECTION)
    write_raw(snapshot, "muni/rutas.geojson", COLLECTION)
    write_latest(root, SNAPSHOT)
    return root


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": SOURCES}), encoding="utf-8")
    return path


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_select_adapted_sources() -> None:
    assert [s["id"] for s in select_adapted_sources(SOURCES)] == [
        "muni_paradas",
        "muni_rutas",
    ]
    assert [s["id"] for s in select_adapted_sources(SOURCES, ["muni_rutas"])] == [
        "muni_rutas"
    ]


@pytest.mark.parametrize(
    ("requested", "message"),
    [
        (["zzz"], "desconocidas: zzz"),
        (["sin_adaptador"], "sin adaptador: sin_adaptador"),
    ],
)
def test_select_rejects_unknown_or_unadapted(
    requested: list[str], message: str
) -> None:
    with pytest.raises(Exception, match=message):
        select_adapted_sources(SOURCES, requested)


def test_writes_batch_provenance_and_manifest(raw: Path, tmp_path: Path) -> None:
    summary = normalize_snapshot(SOURCES[:1], raw / SNAPSHOT, tmp_path / "staging")

    staging = tmp_path / "staging" / SNAPSHOT
    batch = StagingBatch.model_validate_json(
        (staging / "muni_paradas.json").read_text(encoding="utf-8")
    )
    provenance = read(staging / "muni_paradas.json.provenance.json")
    manifest = read(staging / "run_manifest.json")
    raw_bytes = (raw / SNAPSHOT / "muni" / "paradas.geojson").read_bytes()

    assert summary.ok
    assert [r.source.external_id for r in batch.records] == ["1"]
    assert [i.code for i in batch.issues] == ["sin_geometria"]
    assert provenance["inputs"] == [
        {"file": "muni/paradas.geojson", "sha256": sha256_bytes(raw_bytes)}
    ]
    assert provenance["snapshot_id"] == SNAPSHOT
    assert provenance["records"] == {"stop": 1}
    assert provenance["issues"] == {"warning": 1}
    assert provenance["sha256"] == sha256_bytes(
        (staging / "muni_paradas.json").read_bytes()
    )
    assert provenance["run_id"] == manifest["run_id"] == summary.run_id
    assert manifest["ok"] is True
    assert not list(staging.glob(".*.tmp"))


def test_error_issues_make_the_run_fail(
    raw: Path, tmp_path: Path, registry: dict[str, base.Adapter]
) -> None:
    def failing_issues(raw_input: base.RawInput) -> StagingBatch:
        batch = stops_adapter(raw_input)
        error = Issue(severity=Severity.ERROR, code="fuera_de_cobertura", message="x")
        return batch.model_copy(update={"issues": (error,)})

    registry["muni_paradas"] = failing_issues

    summary = normalize_snapshot(SOURCES[:1], raw / SNAPSHOT, tmp_path / "staging")

    assert summary.ok is False
    assert summary.successful[0]["has_errors"] is True


@pytest.mark.parametrize(
    ("adapter", "expected"),
    [
        (lambda raw: (_ for _ in ()).throw(KeyError("FID")), "KeyError('FID')"),
        (
            lambda raw: StagingBatch(
                source_id="otra", snapshot_id=SNAPSHOT, records=()
            ),
            "otra fuente o snapshot",
        ),
        (
            lambda raw: StagedStop(
                source=SourceRef(source_id="muni_paradas", external_id="1", raw={}),
                name="",
                position=(0.0, 0.0),
            ),
            "registros inválidos",
        ),
    ],
    ids=["inesperado", "otra-fuente", "invalido"],
)
def test_adapter_failures_do_not_stop_other_sources(
    raw: Path,
    tmp_path: Path,
    registry: dict[str, base.Adapter],
    adapter: base.Adapter,
    expected: str,
) -> None:
    registry["muni_paradas"] = adapter

    summary = normalize_snapshot(SOURCES[:2], raw / SNAPSHOT, tmp_path / "staging")

    assert [f["source_id"] for f in summary.failed] == ["muni_paradas"]
    assert expected in summary.failed[0]["error"]
    assert [s["source_id"] for s in summary.successful] == ["muni_rutas"]


def test_tampered_raw_file_is_rejected(raw: Path, tmp_path: Path) -> None:
    (raw / SNAPSHOT / "muni" / "paradas.geojson").write_text("{}", encoding="utf-8")

    summary = normalize_snapshot(SOURCES[:1], raw / SNAPSHOT, tmp_path / "staging")

    assert "SHA-256" in summary.failed[0]["error"]


def test_missing_raw_file_and_invalid_json(raw: Path, tmp_path: Path) -> None:
    (raw / SNAPSHOT / "muni" / "rutas.geojson").unlink()
    broken = raw / SNAPSHOT / "muni" / "paradas.geojson"
    broken.write_bytes(b"{no")
    write_json(
        broken.with_name(broken.name + ".provenance.json"),
        {"sha256": sha256_bytes(b"{no")},
    )

    summary = normalize_snapshot(SOURCES[:2], raw / SNAPSHOT, tmp_path / "staging")

    errors = {f["source_id"]: f["error"] for f in summary.failed}
    assert "no es JSON válido" in errors["muni_paradas"]
    assert "no contiene muni/rutas.geojson" in errors["muni_rutas"]


def test_cli_normalizes_latest_snapshot(raw: Path, config: Path) -> None:
    exit_code = cli.main(["--config", str(config), "--raw", str(raw)])

    staging = raw.parent / "staging" / SNAPSHOT
    assert exit_code == cli.EXIT_OK
    assert sorted(p.name for p in staging.iterdir()) == [
        "muni_paradas.json",
        "muni_paradas.json.provenance.json",
        "muni_rutas.json",
        "muni_rutas.json.provenance.json",
        "run_manifest.json",
    ]


def test_cli_reports_failures(
    raw: Path, config: Path, tmp_path: Path, registry: dict[str, base.Adapter]
) -> None:
    registry["muni_rutas"] = lambda raw: (_ for _ in ()).throw(RuntimeError("x"))

    exit_code = cli.main(
        [
            "--config",
            str(config),
            "--raw",
            str(raw),
            "--source",
            "muni_rutas",
            "--staging",
            str(tmp_path / "otra"),
        ]
    )

    assert exit_code == cli.EXIT_FAILURES
    assert (tmp_path / "otra" / SNAPSHOT / "run_manifest.json").exists()


def test_cli_without_adapters_is_a_configuration_error(
    raw: Path,
    config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(base, "_REGISTRY", {})

    assert (
        cli.main(["--config", str(config), "--raw", str(raw)])
        == cli.EXIT_CONFIGURATION_ERROR
    )
    assert "Ninguna fuente tiene adaptador" in capsys.readouterr().err


def test_cli_invalid_log_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUTAGT_LOG_FORMAT", "xml")

    assert cli.main([]) == cli.EXIT_CONFIGURATION_ERROR


def shapes_adapter(raw: base.RawInput) -> StagingBatch:
    """Un trazado de la ruta 801 lejos de las paradas de `COLLECTION`."""
    ref = SourceRef(source_id=raw.source_id, external_id="1", raw={})
    shape = StagedShape(
        source=ref,
        route_code="801",
        coordinates=((-90.5, 14.61), (-90.4, 14.61)),
        length_m=10_760.0,
    )
    return StagingBatch(
        source_id=raw.source_id, snapshot_id=raw.snapshot_id, records=(shape,)
    )


def stops_of_801(raw: base.RawInput) -> StagingBatch:
    batch = stops_adapter(raw)
    records = tuple(
        r.model_copy(update={"route_codes": ("801",)}) for r in batch.records
    )
    return batch.model_copy(update={"records": records})


def test_validates_stops_against_their_shapes_source(
    raw: Path, tmp_path: Path, registry: dict[str, base.Adapter]
) -> None:
    registry["muni_paradas"] = stops_of_801
    registry["muni_rutas"] = shapes_adapter
    sources = [{**SOURCES[0], "shapes_source": "muni_rutas"}, SOURCES[1]]

    summary = normalize_snapshot(sources, raw / SNAPSHOT, tmp_path / "staging")

    batch = StagingBatch.model_validate_json(
        (tmp_path / "staging" / SNAPSHOT / "muni_paradas.json").read_text(
            encoding="utf-8"
        )
    )
    far = [i for i in batch.issues if i.code == "parada_lejos_de_ruta"]
    assert [i.severity for i in far] == [Severity.ERROR]
    assert summary.ok is False
    assert summary.successful[0]["issues"] == {"error": 1, "warning": 1}


def test_cross_validation_is_skipped_without_the_shapes_source(
    raw: Path, tmp_path: Path
) -> None:
    sources = [{**SOURCES[0], "shapes_source": "muni_rutas"}]

    summary = normalize_snapshot(sources, raw / SNAPSHOT, tmp_path / "staging")

    assert summary.ok
    assert summary.successful[0]["issues"] == {"info": 1, "warning": 1}


def test_batch_validations_run_after_the_adapter(
    raw: Path, tmp_path: Path, registry: dict[str, base.Adapter]
) -> None:
    def outside(raw_input: base.RawInput) -> StagingBatch:
        batch = stops_adapter(raw_input)
        moved = batch.records[0].model_copy(update={"position": (-90.5, -14.6)})
        return batch.model_copy(update={"records": (moved,)})

    registry["muni_paradas"] = outside

    summary = normalize_snapshot(SOURCES[:1], raw / SNAPSHOT, tmp_path / "staging")

    assert summary.successful[0]["issues"] == {"error": 1, "warning": 1}
    assert summary.ok is False


def test_write_failures_do_not_stop_other_sources(
    raw: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = runner.write_batch

    def failing(batch: StagingBatch, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if batch.source_id == "muni_paradas":
            raise OSError("disco lleno")
        return original(batch, *args, **kwargs)

    monkeypatch.setattr(runner, "write_batch", failing)

    summary = normalize_snapshot(SOURCES[:2], raw / SNAPSHOT, tmp_path / "staging")

    assert summary.failed == [{"source_id": "muni_paradas", "error": "disco lleno"}]
    assert [s["source_id"] for s in summary.successful] == ["muni_rutas"]
