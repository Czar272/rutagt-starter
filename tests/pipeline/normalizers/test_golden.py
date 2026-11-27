"""Normalización de extremo a extremo sobre extractos reales de las capas municipales.

El snapshot de `tests/fixtures/normalizers/raw/` reúne los casos críticos que
encontró el perfil (RGT-34) y los adaptadores (RGT-36 a RGT-40). La prueba
ejecuta el runner con el catálogo real y compara un resumen legible de cada
lote con `expected_summary.json`. Para regenerarlo tras un cambio intencional:

    RUTAGT_UPDATE_GOLDEN=1 uv run pytest tests/pipeline/normalizers/test_golden.py

y revisar el diff antes de confirmarlo.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from rutagt.core.settings import PROJECT_ROOT
from rutagt.pipeline.normalizers import cli
from rutagt.pipeline.normalizers.models import (
    StagedRoute,
    StagedShape,
    StagedStop,
    StagingBatch,
)
from rutagt.pipeline.normalizers.runner import (
    normalize_snapshot,
    select_adapted_sources,
)
from rutagt.pipeline.sources import load_sources

FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "normalizers"
RAW = FIXTURES / "raw"
SNAPSHOT = "20261126T181403Z"
EXPECTED = FIXTURES / "expected_summary.json"
CONFIG = PROJECT_ROOT / "config" / "sources.json"


def sources() -> list[dict[str, Any]]:
    return select_adapted_sources(load_sources(CONFIG))


def summarize_record(record: StagedStop | StagedRoute | StagedShape) -> dict[str, Any]:
    base = {"entity": record.entity_type, "external_id": record.source.external_id}
    if isinstance(record, StagedStop):
        return {
            **base,
            "name": record.name,
            "direction_hint": record.direction_hint,
            "zone": record.zone,
            "route_codes": list(record.route_codes),
            "address": record.address,
        }
    if isinstance(record, StagedRoute):
        return {
            **base,
            "route_code": record.route_code,
            "variant_code": record.variant_code,
            "short_name": record.short_name,
            "long_name": record.long_name,
        }
    return {
        **base,
        "route_code": record.route_code,
        "variant_code": record.variant_code,
        "points": len(record.coordinates),
        "length_m": record.length_m,
    }


def summarize(batch: StagingBatch) -> dict[str, Any]:
    return {
        "records": [summarize_record(record) for record in batch.records],
        "issues": [
            {
                "severity": str(issue.severity),
                "code": issue.code,
                "external_id": issue.external_id,
            }
            for issue in batch.issues
        ],
    }


def read_batches(staging: Path) -> dict[str, StagingBatch]:
    return {
        path.stem: StagingBatch.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(staging.glob("muniguate_*.json"))
        if not path.name.endswith(".provenance.json")
    }


@pytest.fixture(scope="module")
def staging(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("staging")
    summary = normalize_snapshot(sources(), RAW / SNAPSHOT, root)
    assert summary.failed == []
    return root / SNAPSHOT


def test_all_municipal_layers_have_an_adapter() -> None:
    assert sorted(source["id"] for source in sources()) == [
        "muniguate_transmetro_routes_2025",
        "muniguate_transmetro_stops_2025",
        "muniguate_tubus_routes_2025",
        "muniguate_tubus_stops_2025",
    ]


def test_matches_the_expected_summary(staging: Path) -> None:
    actual = {
        source_id: summarize(batch)
        for source_id, batch in read_batches(staging).items()
    }
    if os.environ.get("RUTAGT_UPDATE_GOLDEN") == "1":
        # `newline` evita CRLF en Windows; Prettier da el formato final.
        EXPECTED.write_text(
            json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    assert actual == expected


def test_every_fixture_record_is_processable(staging: Path) -> None:
    """Ningún registro real se pierde ni produce problemas `error`."""
    batches = read_batches(staging)
    for source_id, batch in batches.items():
        provenance = json.loads(
            next(
                (RAW / SNAPSHOT).rglob(
                    f"*{source_id.removeprefix('muniguate_')}*.provenance.json"
                )
            ).read_text(encoding="utf-8")
        )
        external_ids = {record.source.external_id for record in batch.records}
        assert external_ids == {str(fid) for fid in provenance["fids"]}, source_id
        assert not batch.has_errors, source_id


def test_runs_are_deterministic(staging: Path, tmp_path: Path) -> None:
    """Dos ejecuciones sobre el mismo snapshot producen lotes idénticos."""
    normalize_snapshot(sources(), RAW / SNAPSHOT, tmp_path)

    for path in sorted(staging.glob("muniguate_*.json")):
        again = tmp_path / SNAPSHOT / path.name
        if path.name.endswith(".provenance.json"):
            first = json.loads(path.read_text(encoding="utf-8"))
            second = json.loads(again.read_text(encoding="utf-8"))
            assert first["sha256"] == second["sha256"], path.name
        else:
            assert path.read_bytes() == again.read_bytes(), path.name


def test_cli_exits_ok_on_the_fixture(tmp_path: Path) -> None:
    exit_code = cli.main(
        [
            "--config",
            str(CONFIG),
            "--raw",
            str(RAW),
            "--snapshot",
            SNAPSHOT,
            "--staging",
            str(tmp_path),
        ]
    )

    assert exit_code == cli.EXIT_OK
