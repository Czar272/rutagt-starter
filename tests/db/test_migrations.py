"""Pruebas de integración de las migraciones contra PostgreSQL + PostGIS.

Cada prueba trabaja sobre una base temporal creada en el servidor configurado
con `RUTAGT_DB_*` y eliminada al terminar:

    uv run --env-file .env pytest -m integration
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine

from rutagt.core.settings import PROJECT_ROOT
from rutagt.db.settings import DatabaseSettings

pytestmark = pytest.mark.integration

SCHEMAS = ["provenance", "transit", "realtime", "community"]
APPEND_ONLY_TABLES = {
    "provenance.source_record",
    "transit.feed_version",
    "realtime.vehicle_position",
    "realtime.stop_event",
    "realtime.traffic_observation",
    "realtime.eta_prediction",
}

VALID_NETWORK = """
INSERT INTO provenance.data_source (source_id, name, source_kind)
VALUES ('muniguate_tubus_stops_2025', 'Paradas TuBus', 'official_open_data');
INSERT INTO transit.agency (agency_id, agency_name, source_id)
VALUES ('tubus', 'TuBus', 'muniguate_tubus_stops_2025');
INSERT INTO transit.route (route_id, agency_id, route_short_name, route_color)
VALUES ('tubus:route:801', 'tubus', '801', '00A3E0');
INSERT INTO transit.shape (shape_id, geom)
VALUES ('tubus:shape:801-0',
        ST_GeomFromText('LINESTRING(-90.51 14.60, -90.50 14.61)', 4326));
INSERT INTO transit.route_pattern (pattern_id, route_id, shape_id, direction_id)
VALUES ('tubus:pattern:801-0', 'tubus:route:801', 'tubus:shape:801-0', 0);
INSERT INTO transit.stop (stop_id, stop_name, location) VALUES
  ('tubus:stop:801-094', 'Parada 094', ST_SetSRID(ST_MakePoint(-90.51, 14.60), 4326)),
  ('tubus:stop:801-095', 'Parada 095', ST_SetSRID(ST_MakePoint(-90.50, 14.61), 4326));
INSERT INTO transit.pattern_stop (pattern_id, stop_id, stop_sequence, sequence_quality)
VALUES ('tubus:pattern:801-0', 'tubus:stop:801-094', 1, 'official'),
       ('tubus:pattern:801-0', 'tubus:stop:801-095', 2, 'official');
INSERT INTO transit.service_calendar (service_id, monday, tuesday, wednesday,
  thursday, friday, saturday, sunday, start_date, end_date)
VALUES ('tubus:service:laboral', true, true, true, true, true, false, false,
        '2026-01-01', '2026-12-31');
INSERT INTO transit.trip (trip_id, route_id, pattern_id, service_id)
VALUES ('tubus:trip:801-0-0600', 'tubus:route:801', 'tubus:pattern:801-0',
        'tubus:service:laboral');
INSERT INTO transit.stop_time (trip_id, stop_id, stop_sequence, arrival_seconds,
  departure_seconds)
VALUES ('tubus:trip:801-0-0600', 'tubus:stop:801-094', 1, 21600, 21620);
"""

INVALID_STATEMENTS = {
    "identificador sin formato": (
        "INSERT INTO transit.stop (stop_id, stop_name, location) VALUES "
        "('801-094', 'x', ST_SetSRID(ST_MakePoint(-90.51, 14.60), 4326))"
    ),
    "tipo equivocado en el identificador": (
        "INSERT INTO transit.stop (stop_id, stop_name, location) VALUES "
        "('tubus:route:801-094', 'x', ST_SetSRID(ST_MakePoint(-90.51, 14.60), 4326))"
    ),
    "color de ruta inválido": (
        "INSERT INTO transit.route (route_id, agency_id, route_color) "
        "VALUES ('tubus:route:802', 'tubus', 'zzzzzz')"
    ),
    "tipo de ruta fuera de GTFS": (
        "INSERT INTO transit.route (route_id, agency_id, route_type) "
        "VALUES ('tubus:route:802', 'tubus', 99)"
    ),
    "parada sin ubicación": (
        "INSERT INTO transit.stop (stop_id, stop_name) VALUES ('tubus:stop:x', 'x')"
    ),
    "estación con estación padre": (
        "INSERT INTO transit.stop (stop_id, stop_name, location, location_type, "
        "parent_station_id) VALUES ('tubus:stop:e1', 'x', "
        "ST_SetSRID(ST_MakePoint(-90.51, 14.60), 4326), 1, 'tubus:stop:801-094')"
    ),
    "entrada sin estación padre": (
        "INSERT INTO transit.stop (stop_id, stop_name, location, location_type) "
        "VALUES ('tubus:stop:e2', 'x', "
        "ST_SetSRID(ST_MakePoint(-90.51, 14.60), 4326), 2)"
    ),
    "trazado MultiLineString": (
        "INSERT INTO transit.shape (shape_id, geom) VALUES ('tubus:shape:m', "
        "ST_GeomFromText('MULTILINESTRING((-90.51 14.60, -90.50 14.61))', 4326))"
    ),
    "salida antes de la llegada": (
        "INSERT INTO transit.stop_time (trip_id, stop_id, stop_sequence, "
        "arrival_seconds, departure_seconds) VALUES ('tubus:trip:801-0-0600', "
        "'tubus:stop:801-095', 2, 22000, 21900)"
    ),
    "calendario sin días": (
        "INSERT INTO transit.service_calendar VALUES ('tubus:service:nunca', "
        "false, false, false, false, false, false, false, '2026-01-01', '2026-12-31')"
    ),
    "vigencia invertida": (
        "INSERT INTO provenance.data_source (source_id, name, source_kind, "
        "valid_from, valid_to) VALUES ('fuente_x', 'x', 'field_survey', "
        "'2026-12-01', '2026-01-01')"
    ),
    "identificador de fuente sin snake_case": (
        "INSERT INTO provenance.data_source (source_id, name, source_kind) "
        "VALUES ('Fuente-X', 'x', 'field_survey')"
    ),
    "tipo de transbordo fuera de GTFS": (
        "INSERT INTO transit.transfer (from_stop_id, to_stop_id, transfer_type) "
        "VALUES ('tubus:stop:801-094', 'tubus:stop:801-095', 9)"
    ),
    "distancias de tarifa invertidas": (
        "INSERT INTO transit.fare_product (fare_product_id, name, amount) "
        "VALUES ('tubus:fare:general', 'General', 1);"
        "INSERT INTO transit.fare_rule (fare_product_id, min_distance_m, "
        "max_distance_m) VALUES ('tubus:fare:general', 500, 100)"
    ),
    "borrar una parada usada en un patrón": (
        "DELETE FROM transit.stop WHERE stop_id = 'tubus:stop:801-095'"
    ),
}


@contextmanager
def temporary_database() -> Iterator[Engine]:
    """Crea una base vacía, la entrega y la elimina al terminar."""
    settings = DatabaseSettings.from_env()
    name = f"rutagt_test_{uuid4().hex[:12]}"
    admin = create_engine(settings.url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = create_engine(settings.url(name))
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("RUTAGT_DB_NAME", name)
            yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


def alembic(revision: str, *, downgrade: bool = False) -> None:
    """Ejecuta Alembic con la configuración del repositorio."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["configure_logger"] = False
    if downgrade:
        command.downgrade(config, revision)
    else:
        command.upgrade(config, revision)


def rows(
    conn: Connection, sql: str, params: dict[str, Any] | None = None
) -> list[tuple[Any, ...]]:
    """Ejecuta SQL en el controlador; sin parámetros admite varias sentencias."""
    driver = cast(
        "psycopg.Connection[tuple[Any, ...]]", conn.connection.driver_connection
    )
    cursor = driver.execute(sql.encode(), params)
    return cursor.fetchall() if cursor.description else []


def names(conn: Connection, sql: str) -> set[str]:
    """Primera columna de una consulta filtrada por los esquemas del proyecto."""
    return {str(r[0]) for r in rows(conn, sql, {"schemas": SCHEMAS})}


@pytest.fixture(scope="module")
def migrated() -> Iterator[Engine]:
    with temporary_database() as engine:
        alembic("head")
        yield engine


def test_creates_the_four_schemas(migrated: Engine) -> None:
    with migrated.connect() as conn:
        found = names(
            conn, "SELECT nspname FROM pg_namespace WHERE nspname = ANY(%(schemas)s)"
        )

    assert found == set(SCHEMAS)


def test_every_foreign_key_is_covered_by_an_index(migrated: Engine) -> None:
    foreign_keys = """
        SELECT c.conrelid::regclass::text || '.' || c.conname
        FROM pg_constraint c
        WHERE c.contype = 'f'
          AND c.connamespace::regnamespace::text = ANY(%(schemas)s)
    """
    uncovered = """
          AND NOT EXISTS (
            SELECT 1 FROM pg_index i
            WHERE i.indrelid = c.conrelid
              AND (string_to_array(i.indkey::text, ' ')::int2[])
                  [1:array_length(c.conkey, 1)] = c.conkey
          )
    """
    with migrated.connect() as conn:
        total = names(conn, foreign_keys)
        unindexed = names(conn, foreign_keys + uncovered)

    assert len(total) >= 50
    assert unindexed == set()


def test_audit_columns_and_updated_at_triggers(migrated: Engine) -> None:
    columns = """
        SELECT table_schema || '.' || table_name FROM information_schema.columns
        WHERE table_schema = ANY(%(schemas)s) AND is_nullable = 'NO'
          AND column_name = """
    with migrated.connect() as conn:
        tables = names(
            conn,
            "SELECT table_schema || '.' || table_name FROM information_schema.tables "
            "WHERE table_schema = ANY(%(schemas)s) AND table_type = 'BASE TABLE'",
        )
        created = names(conn, columns + "'created_at'")
        updated = names(conn, columns + "'updated_at'")
        triggered = names(
            conn,
            """
            SELECT t.tgrelid::regclass::text
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE t.tgname = 'set_updated_at' AND NOT t.tgisinternal
              AND n.nspname = ANY(%(schemas)s)
            """,
        )

    # 23 tablas originales + data_issue (D22) + feed_version (D17).
    assert len(tables) == 25
    assert created == tables
    assert tables - updated == APPEND_ONLY_TABLES
    assert triggered == updated


def test_updated_at_changes_on_update(migrated: Engine) -> None:
    with migrated.begin() as conn:
        rows(
            conn,
            "INSERT INTO provenance.data_source (source_id, name, source_kind) "
            "VALUES ('fuente_auditoria', 'x', 'field_survey')",
        )
    with migrated.begin() as conn:
        rows(
            conn,
            "UPDATE provenance.data_source SET name = 'y' "
            "WHERE source_id = 'fuente_auditoria'",
        )
    with migrated.begin() as conn:
        [(created, updated)] = rows(
            conn,
            "DELETE FROM provenance.data_source WHERE source_id = 'fuente_auditoria' "
            "RETURNING created_at, updated_at",
        )

    assert updated > created


def test_geometries_use_wgs84(migrated: Engine) -> None:
    with migrated.connect() as conn:
        found = rows(
            conn,
            "SELECT f_table_schema || '.' || f_table_name || '.' || f_geometry_column,"
            " type, srid FROM geometry_columns WHERE f_table_schema = ANY(%(schemas)s)",
            {"schemas": SCHEMAS},
        )

    assert {r[2] for r in found} == {4326}
    assert ("transit.shape.geom", "LINESTRING", 4326) in found


def test_valid_network_is_accepted_and_distance_helper_works(
    migrated: Engine,
) -> None:
    with migrated.connect() as conn, conn.begin() as tx:
        rows(conn, VALID_NETWORK)
        [(distance,)] = rows(
            conn,
            "SELECT public.rutagt_distance_m(a.location, b.location) "
            "FROM transit.stop a, transit.stop b "
            "WHERE a.stop_id = 'tubus:stop:801-094' "
            "AND b.stop_id = 'tubus:stop:801-095'",
        )
        tx.rollback()

    assert 1400 < distance < 1700


def test_deleting_a_pattern_cascades_to_its_stops(migrated: Engine) -> None:
    with migrated.connect() as conn, conn.begin() as tx:
        rows(conn, VALID_NETWORK)
        rows(
            conn,
            "DELETE FROM transit.stop_time; DELETE FROM transit.trip; "
            "DELETE FROM transit.route_pattern",
        )
        [(remaining,)] = rows(conn, "SELECT count(*) FROM transit.pattern_stop")
        tx.rollback()

    assert remaining == 0


@pytest.mark.parametrize(
    "statement", INVALID_STATEMENTS.values(), ids=INVALID_STATEMENTS.keys()
)
def test_constraints_reject_invalid_data(migrated: Engine, statement: str) -> None:
    with migrated.connect() as conn, conn.begin() as tx:
        rows(conn, VALID_NETWORK)
        with pytest.raises((psycopg.errors.IntegrityError, psycopg.errors.DataError)):
            rows(conn, statement)
        tx.rollback()


def test_downgrade_removes_everything_and_upgrade_is_repeatable() -> None:
    with temporary_database() as engine:
        alembic("head")
        alembic("base", downgrade=True)
        with engine.connect() as conn:
            leftover = names(
                conn,
                "SELECT nspname FROM pg_namespace WHERE nspname = ANY(%(schemas)s) "
                "UNION ALL SELECT proname FROM pg_proc "
                "WHERE starts_with(proname, 'rutagt_')",
            )
        alembic("head")
        with engine.connect() as conn:
            version = rows(conn, "SELECT version_num FROM public.alembic_version")

    assert leftover == set()
    assert version == [("0001",)]
