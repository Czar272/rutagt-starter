"""Constructor canónico de extremo a extremo sobre el fixture real (ADR-0035)."""

import json
from pathlib import Path

import pytest

from rutagt.core.errors import ConfigurationError, SourceError
from rutagt.core.io import provenance_path, read_json, sha256_bytes, write_json
from rutagt.core.settings import PROJECT_ROOT
from rutagt.pipeline.canonical import cli, identifiers
from rutagt.pipeline.canonical.models import CanonicalDataset, Quality
from rutagt.pipeline.canonical.runner import (
    DATASET_FILE,
    build_snapshot,
    canonical_sources,
    load_agencies,
    load_ruteros,
    read_batch,
    read_dataset,
)
from rutagt.pipeline.normalizers.runner import (
    normalize_snapshot,
    select_adapted_sources,
)
from rutagt.pipeline.sources import load_sources

RAW = PROJECT_ROOT / "tests" / "fixtures" / "normalizers" / "raw"
SNAPSHOT = "20261126T181403Z"
CONFIG = PROJECT_ROOT / "config" / "sources.json"
AGENCIES = PROJECT_ROOT / "config" / "agencies.json"
RUTEROS = PROJECT_ROOT / "data" / "reference" / "ruteros"


@pytest.fixture(scope="module")
def layers(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Raíz con staging del fixture ya normalizado."""
    root = tmp_path_factory.mktemp("capas")
    summary = normalize_snapshot(
        select_adapted_sources(load_sources(CONFIG)), RAW / SNAPSHOT, root / "staging"
    )
    assert summary.ok
    return root


def build(layers: Path, normalized: Path) -> CanonicalDataset:
    return build_snapshot(
        canonical_sources(load_sources(CONFIG)),
        load_agencies(AGENCIES),
        RAW / SNAPSHOT,
        layers / "staging",
        normalized,
        load_ruteros(RUTEROS),
    )


def test_builds_the_fixture_network(layers: Path, tmp_path: Path) -> None:
    dataset = build(layers, tmp_path)
    stops = {stop.stop_id: stop for stop in dataset.stops}

    assert [a.agency_id for a in dataset.agencies] == ["transmetro", "tubus"]
    assert len(dataset.source_records) == 78
    assert [s.shape_id for s in dataset.shapes if len(s.records) > 1] == [
        "transmetro:shape:18001"
    ]
    # Paraíso I: el mismo andén publicado para las dos variantes exprés.
    paraiso = stops["transmetro:stop:paraiso-i.1"]
    assert [r.external_id for r in paraiso.records] == ["86", "142"]
    assert paraiso.parent_station_id == "transmetro:stop:paraiso-i"
    # Granai: dos andenes con el mismo sentido quedan separados, con incidencia.
    assert {"transmetro:stop:granai.1", "transmetro:stop:granai.2"} <= set(stops)
    assert ("sentido_duplicado", "transmetro:stop:granai.1") in {
        (i.issue_type, i.entity_id) for i in dataset.issues
    }
    # B7: el posible duplicado de TuBus no se fusiona.
    assert [
        stops[f"tubus:stop:parada-190.{n}"].records[0].external_id for n in (1, 2)
    ] == [
        "143",
        "258",
    ]
    assert stops["tubus:stop:parada-199"].direction_hint == "norte"


def test_route_801_follows_the_official_rutero(layers: Path, tmp_path: Path) -> None:
    dataset = build(layers, tmp_path)
    stops = {stop.stop_id: stop for stop in dataset.stops}
    rutero = load_ruteros(RUTEROS)[0]
    sequence = [p for p in dataset.pattern_stops if p.pattern_id == "tubus:pattern:801"]
    pattern = next(p for p in dataset.patterns if p.pattern_id == "tubus:pattern:801")

    # Reproduce la revisión manual de RGT-127: cada parada del rutero, en orden,
    # en el registro que eligió la revisión.
    assert [p.stop_sequence for p in sequence] == list(range(1, 48))
    assert [
        official.layer_external_id in {r.external_id for r in stops[p.stop_id].records}
        for official, p in zip(rutero.stops, sequence, strict=True)
    ] == [True] * 47
    assert {p.sequence_quality for p in sequence} == {Quality.OFFICIAL}
    distances = [p.shape_dist_traveled_m or 0.0 for p in sequence]
    assert None not in {p.shape_dist_traveled_m for p in sequence}
    assert distances == sorted(distances)
    # El código oficial corrige la numeración corrida del nombre.
    assert stops[sequence[35].stop_id].stop_name == "Parada 100"
    assert stops[sequence[35].stop_id].stop_code == "098"
    assert pattern.attributes == {
        "circuit": True,
        "sequence_source": "muniguate_rutero_tubus_801_v4",
        "terminal_stop_id": "tubus:stop:parada-087",
    }
    outside = {
        i.entity_id: i.evidence["motivo_revision"]
        for i in dataset.issues
        if i.issue_type == "parada_fuera_de_rutero"
    }
    assert set(outside) == {
        "tubus:stop:funerales-reforma",
        "tubus:stop:c-c-promo-centro",
    }
    assert all(
        "no figura en el rutero vigente" in reason for reason in outside.values()
    )
    assert "muniguate_rutero_tubus_801_v4" in dataset.source_ids


def test_patterns_without_rutero_follow_the_shape(layers: Path, tmp_path: Path) -> None:
    dataset = build(layers, tmp_path)
    without = {
        i.entity_id for i in dataset.issues if i.issue_type == "secuencia_sin_rutero"
    }
    sequenced = {p.pattern_id for p in dataset.pattern_stops}

    assert "tubus:pattern:801" not in without
    assert without == sequenced - {"tubus:pattern:801"}
    assert {
        p.sequence_quality
        for p in dataset.pattern_stops
        if p.pattern_id != "tubus:pattern:801"
    } == {Quality.PROBABLE}


def test_writes_a_verifiable_dataset_with_provenance(
    layers: Path, tmp_path: Path
) -> None:
    dataset = build(layers, tmp_path)
    provenance = read_json(provenance_path(tmp_path / SNAPSHOT / DATASET_FILE))

    assert read_dataset(tmp_path, SNAPSHOT) == dataset
    assert provenance["generator"] == "rutagt-canonical"
    assert [i["file"] for i in provenance["inputs"]] == [
        "muniguate_transmetro_stops_2025.json",
        "muniguate_tubus_stops_2025.json",
        "muniguate_transmetro_routes_2025.json",
        "muniguate_tubus_routes_2025.json",
    ]
    assert provenance["counts"]["stations"] == 12


def test_is_deterministic(layers: Path, tmp_path: Path) -> None:
    build(layers, tmp_path / "a")
    build(layers, tmp_path / "b")

    first = (tmp_path / "a" / SNAPSHOT / DATASET_FILE).read_bytes()
    assert first == (tmp_path / "b" / SNAPSHOT / DATASET_FILE).read_bytes()


def test_rejects_tampered_files(layers: Path, tmp_path: Path) -> None:
    build(layers, tmp_path)
    dataset = tmp_path / SNAPSHOT / DATASET_FILE
    dataset.write_text(dataset.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(SourceError, match="no coincide"):
        read_dataset(tmp_path, SNAPSHOT)


def test_rejects_staging_from_another_snapshot(layers: Path, tmp_path: Path) -> None:
    other = tmp_path / "staging" / "20250101T000000Z"
    other.mkdir(parents=True)
    for path in (layers / "staging" / SNAPSHOT).glob("muniguate_*"):
        (other / path.name).write_bytes(path.read_bytes())
    raw = tmp_path / "raw" / "20250101T000000Z"
    for path in (RAW / SNAPSHOT).rglob("*.provenance.json"):
        target = raw / path.relative_to(RAW / SNAPSHOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())

    with pytest.raises(SourceError, match="es del snapshot 20261126T181403Z"):
        build_snapshot(
            canonical_sources(load_sources(CONFIG)),
            load_agencies(AGENCIES),
            raw,
            tmp_path / "staging",
            tmp_path / "normalized",
        )


def test_rejects_missing_raw_provenance(layers: Path, tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="procedencia"):
        build_snapshot(
            canonical_sources(load_sources(CONFIG)),
            load_agencies(AGENCIES),
            tmp_path / "raw" / SNAPSHOT,
            layers / "staging",
            tmp_path / "normalized",
        )


@pytest.mark.parametrize("name", ["staging", "normalized"])
def test_rejects_valid_checksums_over_invalid_content(
    tmp_path: Path, name: str
) -> None:
    folder = tmp_path / SNAPSHOT
    file = "muniguate_tubus_stops_2025.json" if name == "staging" else DATASET_FILE
    body = write_json(folder / file, {"records": "no"})
    write_json(provenance_path(folder / file), {"sha256": sha256_bytes(body)})

    with pytest.raises(SourceError, match="no es válido"):
        if name == "staging":
            read_batch(tmp_path / SNAPSHOT, "muniguate_tubus_stops_2025")
        else:
            read_dataset(tmp_path, SNAPSHOT)


def test_cli_requires_sources_with_agency(tmp_path: Path) -> None:
    config = tmp_path / "sources.json"
    config.write_text(json.dumps({"sources": [{"id": "x"}]}), "utf-8")

    assert (
        cli.main(["--config", str(config), "--raw", str(RAW), "--snapshot", SNAPSHOT])
        == cli.EXIT_CONFIGURATION_ERROR
    )


def test_cli_reports_invalid_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUTAGT_LOG_FORMAT", "xml")

    assert cli.main([]) == cli.EXIT_CONFIGURATION_ERROR


def test_rejects_invalid_ruteros(tmp_path: Path) -> None:
    (tmp_path / "x.json").write_text('{"schema_version": 2}', "utf-8")

    with pytest.raises(ConfigurationError, match="Rutero inválido"):
        load_ruteros(tmp_path)


def test_rejects_invalid_agencies(tmp_path: Path) -> None:
    path = tmp_path / "agencies.json"
    path.write_text(json.dumps({"agencies": [{"agency_id": "X Y"}]}), "utf-8")
    with pytest.raises(ConfigurationError, match="No se pudo leer"):
        load_agencies(path)

    agency = {"agency_id": "metro", "agency_name": "Metro"}
    path.write_text(json.dumps({"agencies": [agency, agency]}), "utf-8")
    with pytest.raises(ConfigurationError, match="duplicadas"):
        load_agencies(path)


def test_cli_exit_codes(layers: Path, tmp_path: Path) -> None:
    common = ["--raw", str(RAW), "--snapshot", SNAPSHOT]
    ok = cli.main(
        [
            *common,
            "--staging",
            str(layers / "staging"),
            "--normalized",
            str(tmp_path),
        ]
    )
    missing = cli.main([*common, "--staging", str(tmp_path / "vacio")])
    bad_config = cli.main([*common, "--agencies", str(tmp_path / "no-existe.json")])

    assert (ok, missing, bad_config) == (
        cli.EXIT_OK,
        cli.EXIT_FAILURES,
        cli.EXIT_CONFIGURATION_ERROR,
    )
    assert (tmp_path / SNAPSHOT / DATASET_FILE).is_file()


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Estación Bolívar", "bolivar"),
        ("Estacion Santa Teresa", "santa-teresa"),
        ("Estación Usac / Periferico", "usac-periferico"),
        ("Estación Proyectos 4-4", "proyectos-4-4"),
        ("Parada 067", "parada-067"),
        ("Estación", "estacion"),
    ],
)
def test_place_keys(name: str, key: str) -> None:
    assert identifiers.place_key(name) == key


def test_code_order_is_natural() -> None:
    assert sorted(["12000", "7000", "B", "1000"], key=identifiers.code_order) == [
        "1000",
        "7000",
        "12000",
        "B",
    ]
