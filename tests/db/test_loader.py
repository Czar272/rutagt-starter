"""Carga idempotente del dataset canónico en PostGIS (ADR-0035).

Usa el dataset construido desde el fixture real de los normalizers sobre una
base temporal con todas las migraciones:

    uv run --env-file .env pytest -m integration tests/db/test_loader.py
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text

from rutagt.core.settings import PROJECT_ROOT
from rutagt.db import cli
from rutagt.db.loader import LoadSummary, load_dataset
from rutagt.pipeline.canonical.models import CanonicalDataset
from rutagt.pipeline.canonical.runner import (
    build_snapshot,
    canonical_sources,
    load_agencies,
)
from rutagt.pipeline.normalizers.runner import (
    normalize_snapshot,
    select_adapted_sources,
)
from rutagt.pipeline.sources import load_sources

pytestmark = pytest.mark.integration

RAW = PROJECT_ROOT / "tests" / "fixtures" / "normalizers" / "raw"
SNAPSHOT = "20261126T181403Z"
CONFIG = PROJECT_ROOT / "config" / "sources.json"


@pytest.fixture(scope="module")
def normalized(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Raíz normalizada con el dataset del fixture."""
    root = tmp_path_factory.mktemp("capas")
    sources = load_sources(CONFIG)
    normalize_snapshot(
        select_adapted_sources(sources), RAW / SNAPSHOT, root / "staging"
    )
    build_snapshot(
        canonical_sources(sources),
        load_agencies(PROJECT_ROOT / "config" / "agencies.json"),
        RAW / SNAPSHOT,
        root / "staging",
        root / "normalized",
    )
    return root / "normalized"


@pytest.fixture
def dataset(normalized: Path) -> CanonicalDataset:
    return CanonicalDataset.model_validate_json(
        (normalized / SNAPSHOT / "canonical.json").read_bytes()
    )


@pytest.fixture
def database(
    temporary_database: Callable[[], AbstractContextManager[Engine]],
    alembic: Callable[..., None],
) -> Iterator[Engine]:
    with temporary_database() as engine:
        alembic("head")
        yield engine


def load(engine: Engine, dataset: CanonicalDataset, run_id: str) -> LoadSummary:
    with engine.begin() as conn:
        return load_dataset(conn, dataset, run_id)


def query(engine: Engine, sql: str, **params: Any) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(text(sql), params)]


def scalar(engine: Engine, sql: str, **params: Any) -> Any:
    [(value,)] = query(engine, sql, **params)
    return value


AUDIT = """
    SELECT stop_id, updated_at, loaded_by_run FROM transit.stop
    UNION ALL SELECT route_id, updated_at, loaded_by_run FROM transit.route
    UNION ALL SELECT shape_id, updated_at, loaded_by_run FROM transit.shape
    UNION ALL SELECT data_issue_id::text, updated_at, loaded_by_run
      FROM provenance.data_issue
    ORDER BY 1
"""


def test_first_load_writes_the_network_with_provenance(
    database: Engine, dataset: CanonicalDataset
) -> None:
    summary = load(database, dataset, "run-1")

    assert summary.tables["transit.stop"].inserted == len(dataset.stops) == 34
    assert summary.tables["provenance.source_record"].inserted == 30
    assert summary.tables["provenance.data_issue"].inserted == len(dataset.issues)
    assert (
        scalar(
            database,
            "SELECT count(*) FROM transit.stop WHERE location_type = 1 "
            "AND location_quality = 'probable'",
        )
        == 12
    )
    # Cada andén y cada parada tienen al menos un registro de origen.
    assert (
        scalar(
            database,
            "SELECT count(*) FROM transit.stop s WHERE location_type = 0 "
            "AND NOT EXISTS "
            "(SELECT 1 FROM provenance.entity_source_record e "
            "WHERE e.entity_type = 'stop' AND e.entity_id = s.stop_id)",
        )
        == 0
    )
    assert query(
        database,
        "SELECT r.external_id FROM provenance.entity_source_record e "
        "JOIN provenance.source_record r USING (source_record_id) "
        "WHERE e.entity_id = 'transmetro:shape:18001' ORDER BY 1",
    ) == [("12",), ("9",)]
    assert query(
        database,
        "SELECT parent_station_id, platform_code, ST_AsText(location) "
        "FROM transit.stop WHERE stop_id = 'transmetro:stop:paraiso-i.1'",
    )[0][:2] == ("transmetro:stop:paraiso-i", "1")
    # La longitud esférica del dataset difiere menos de 0,5 % del elipsoide.
    [(stored, ellipsoidal)] = query(
        database,
        "SELECT distance_m, ST_Length(geom::geography) FROM transit.shape "
        "WHERE shape_id = 'transmetro:shape:18000'",
    )
    assert float(stored) == pytest.approx(ellipsoidal, rel=0.005)


def test_reloading_changes_nothing(database: Engine, dataset: CanonicalDataset) -> None:
    load(database, dataset, "run-1")
    before = query(database, AUDIT)
    counts = query(
        database,
        "SELECT (SELECT count(*) FROM provenance.source_record), "
        "(SELECT count(*) FROM provenance.entity_source_record), "
        "(SELECT count(*) FROM provenance.data_issue)",
    )

    summary = load(database, dataset, "run-2")

    assert not summary.changed
    assert query(database, AUDIT) == before
    assert (
        query(
            database,
            "SELECT (SELECT count(*) FROM provenance.source_record), "
            "(SELECT count(*) FROM provenance.entity_source_record), "
            "(SELECT count(*) FROM provenance.data_issue)",
        )
        == counts
    )


def test_changes_update_retire_and_resolve(
    database: Engine, dataset: CanonicalDataset
) -> None:
    load(database, dataset, "run-1")
    renamed = dataset.stops[0].model_copy(update={"stop_name": "Atlántida (nueva)"})
    dropped = "tubus:stop:matamoros"
    changed = dataset.model_copy(
        update={
            "stops": (
                renamed,
                *(s for s in dataset.stops[1:] if s.stop_id != dropped),
            ),
            "issues": dataset.issues[1:],
        }
    )

    summary = load(database, changed, "run-2")

    assert summary.tables["transit.stop"].updated == 1
    assert summary.tables["transit.stop"].retired == 1
    assert summary.tables["provenance.data_issue"].retired == 1
    assert query(
        database,
        "SELECT stop_name, loaded_by_run FROM transit.stop WHERE stop_id = :id",
        id=renamed.stop_id,
    ) == [("Atlántida (nueva)", "run-2")]
    assert (
        scalar(
            database,
            "SELECT status::text FROM transit.stop WHERE stop_id = :id",
            id=dropped,
        )
        == "retired"
    )
    assert (
        scalar(
            database,
            "SELECT status::text FROM provenance.data_issue WHERE issue_key = :key",
            key=dataset.issues[0].issue_key,
        )
        == "resolved"
    )

    # Al volver a publicarse, la parada se reactiva y la incidencia se reabre.
    load(database, dataset, "run-3")
    assert (
        scalar(
            database,
            "SELECT status::text FROM transit.stop WHERE stop_id = :id",
            id=dropped,
        )
        == "active"
    )
    assert query(
        database,
        "SELECT status::text, resolved_at FROM provenance.data_issue "
        "WHERE issue_key = :key",
        key=dataset.issues[0].issue_key,
    ) == [("open", None)]


def test_curation_status_is_preserved(
    database: Engine, dataset: CanonicalDataset
) -> None:
    load(database, dataset, "run-1")
    key = dataset.issues[0].issue_key
    with database.begin() as conn:
        conn.execute(
            text(
                "UPDATE provenance.data_issue SET status = 'dismissed' "
                "WHERE issue_key = :key"
            ),
            {"key": key},
        )

    load(database, dataset, "run-2")
    load(database, dataset.model_copy(update={"issues": ()}), "run-3")

    assert (
        scalar(
            database,
            "SELECT status::text FROM provenance.data_issue WHERE issue_key = :key",
            key=key,
        )
        == "dismissed"
    )


def test_a_failed_load_changes_nothing(
    database: Engine, dataset: CanonicalDataset
) -> None:
    broken = dataset.model_copy(
        update={
            "stops": (
                *dataset.stops,
                dataset.stops[-1].model_copy(
                    update={
                        "stop_id": "tubus:stop:huerfana",
                        "parent_station_id": "tubus:stop:no-existe",
                    }
                ),
            )
        }
    )

    with pytest.raises(Exception, match=r"parent_station_id|foreign key"):
        load(database, broken, "run-1")

    assert scalar(database, "SELECT count(*) FROM transit.stop") == 0
    assert scalar(database, "SELECT count(*) FROM provenance.source_record") == 0


def test_cli_loads_the_snapshot(database: Engine, normalized: Path) -> None:
    arguments = ["--snapshot", SNAPSHOT, "--normalized", str(normalized)]

    assert cli.main(arguments) == cli.EXIT_OK
    assert cli.main(arguments) == cli.EXIT_OK
    assert scalar(database, "SELECT count(*) FROM transit.route") == 4
