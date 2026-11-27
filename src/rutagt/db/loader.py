"""Carga idempotente del dataset canónico en PostGIS (ADR-0035).

Todo ocurre en la transacción de la conexión recibida: o se carga el dataset
completo o no cambia nada. Reglas:

- **Entidades** (agencia, fuente, ruta, variante, trazado, parada): `INSERT …
  ON CONFLICT DO UPDATE` por su identificador canónico, solo si algún valor
  cambió. Una fila sin cambios conserva `updated_at` y `loaded_by_run`.
- **Registros originales**: `provenance.source_record` es append-only; un
  registro con el mismo `checksum` no se repite. `entity_source_record` enlaza
  cada entidad con todos sus registros.
- **Retiro**: las rutas, variantes y paradas de una fuente cargada que ya no
  están en el dataset pasan a `status = 'retired'`; nunca se borran.
- **Incidencias**: se identifican por `issue_key`. Una incidencia que ya
  existe conserva su estado de curación; una abierta que deja de detectarse
  pasa a `resolved`, y vuelve a `open` si reaparece.
"""

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Connection, text

from rutagt.pipeline.canonical.models import CanonicalDataset, RecordRef, Stop

RecordKey = tuple[str, str]
"""`(source_id, external_id)` de un registro original."""


@dataclass
class TableCounts:
    """Filas insertadas, actualizadas, sin cambios y retiradas de una tabla."""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    retired: int = 0


@dataclass
class LoadSummary:
    """Resultado de una carga, por tabla."""

    run_id: str
    tables: dict[str, TableCounts] = field(default_factory=dict)

    def table(self, name: str) -> TableCounts:
        return self.tables.setdefault(name, TableCounts())

    @property
    def changed(self) -> bool:
        """Indica si la carga modificó alguna fila."""
        return any(c.inserted or c.updated or c.retired for c in self.tables.values())

    def as_dict(self) -> dict[str, dict[str, int]]:
        return {name: vars(counts) for name, counts in sorted(self.tables.items())}


def _jsonb(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class _Table:
    """Tabla con clave canónica y las expresiones SQL de cada columna."""

    name: str
    key: str
    columns: Mapping[str, str]
    """Columna → expresión SQL del valor (con parámetros `:nombre`)."""
    on_change: Mapping[str, str] = field(default_factory=dict)
    """Columna → expresión que se actualiza solo cuando algo cambió."""

    def upsert_sql(self) -> str:
        names = list(self.columns)
        compared = [c for c in names if c != self.key]
        updates = [f"{c} = EXCLUDED.{c}" for c in compared]
        updates += [f"{c} = {expr}" for c, expr in self.on_change.items()]
        # Tablas y columnas son constantes de este módulo; los valores van como
        # parámetros.
        return (
            f"INSERT INTO {self.name} AS t ({', '.join(names)}, loaded_by_run) "  # noqa: S608
            f"VALUES ({', '.join(self.columns.values())}, :run_id) "
            f"ON CONFLICT ({self.key}) DO UPDATE SET {', '.join(updates)}, "
            "loaded_by_run = EXCLUDED.loaded_by_run "
            f"WHERE ({', '.join('t.' + c for c in compared)}) IS DISTINCT FROM "
            f"({', '.join('EXCLUDED.' + c for c in compared)}) "
            "RETURNING (xmax = 0) AS inserted"
        )


def _plain(*names: str) -> dict[str, str]:
    return {name: f":{name}" for name in names}


AGENCY = _Table(
    "transit.agency",
    "agency_id",
    {
        **_plain(
            "agency_id",
            "agency_name",
            "public_brand",
            "regulator_name",
            "agency_url",
            "agency_timezone",
            "agency_lang",
            "municipality",
        ),
        "status": "'active'",
    },
)

DATA_SOURCE = _Table(
    "provenance.data_source",
    "source_id",
    {
        **_plain("source_id", "name", "authority"),
        "source_kind": "CAST(:source_kind AS provenance.source_kind)",
        **_plain("source_url", "attribution", "attribution_url"),
        "fetched_at": "CAST(:fetched_at AS timestamptz)",
        "sha256": ":sha256",
        "metadata": "CAST(:metadata AS jsonb)",
    },
)

SHAPE = _Table(
    "transit.shape",
    "shape_id",
    {
        "shape_id": ":shape_id",
        "geom": "ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)",
        "distance_m": ":distance_m",
        "quality": "CAST(:quality AS transit.observation_quality)",
        **_plain("source_id", "source_record_id"),
    },
    on_change={
        "quality_assessed_at": (
            "CASE WHEN (t.geom, t.quality) IS DISTINCT FROM "
            "(EXCLUDED.geom, EXCLUDED.quality) THEN now() "
            "ELSE t.quality_assessed_at END"
        )
    },
)

ROUTE = _Table(
    "transit.route",
    "route_id",
    {
        **_plain(
            "route_id",
            "agency_id",
            "official_code",
            "route_short_name",
            "route_long_name",
            "route_type",
        ),
        "status": "'active'",
        **_plain("source_id", "source_record_id"),
    },
)

PATTERN = _Table(
    "transit.route_pattern",
    "pattern_id",
    {
        **_plain("pattern_id", "route_id", "shape_id", "variant_name"),
        "status": "'active'",
        "source_id": ":source_id",
    },
)

STOP = _Table(
    "transit.stop",
    "stop_id",
    {
        **_plain("stop_id", "stop_name", "location_type"),
        "location": "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)",
        **_plain(
            "address", "zone", "parent_station_id", "platform_code", "direction_hint"
        ),
        "status": "'active'",
        **_plain("source_id", "source_record_id"),
        "location_quality": "CAST(:location_quality AS transit.observation_quality)",
    },
    on_change={
        "location_assessed_at": (
            "CASE WHEN (t.location, t.location_quality) IS DISTINCT FROM "
            "(EXCLUDED.location, EXCLUDED.location_quality) THEN now() "
            "ELSE t.location_assessed_at END"
        )
    },
)

RETIRABLE = {
    "transit.route": "route_id",
    "transit.route_pattern": "pattern_id",
    "transit.stop": "stop_id",
}


def _upsert(
    conn: Connection,
    table: _Table,
    rows: Iterable[dict[str, Any]],
    summary: LoadSummary,
) -> None:
    sql = text(table.upsert_sql())
    counts = summary.table(table.name)
    for row in rows:
        result = conn.execute(sql, {**row, "run_id": summary.run_id}).one_or_none()
        if result is None:
            counts.unchanged += 1
        elif result.inserted:
            counts.inserted += 1
        else:
            counts.updated += 1


def _retire(
    conn: Connection,
    table: str,
    keep: Sequence[str],
    sources: Sequence[str],
    summary: LoadSummary,
) -> None:
    key = RETIRABLE[table]
    result = conn.execute(
        # Tabla y clave de RETIRABLE; los valores van como parámetros.
        text(
            f"UPDATE {table} SET status = 'retired', loaded_by_run = :run_id "  # noqa: S608
            f"WHERE source_id = ANY(:sources) AND NOT ({key} = ANY(:keep)) "
            "AND status <> 'retired'"
        ),
        {"run_id": summary.run_id, "sources": list(sources), "keep": list(keep)},
    )
    summary.table(table).retired += result.rowcount


def _source_records(
    conn: Connection, dataset: CanonicalDataset, summary: LoadSummary
) -> dict[RecordKey, int]:
    """Inserta los registros originales nuevos y devuelve el id de cada uno."""
    fetched_at = {s.source_id: s.fetched_at for s in dataset.data_sources}
    counts = summary.table("provenance.source_record")
    insert = text(
        "INSERT INTO provenance.source_record (source_id, external_id, entity_type, "
        "fetched_at, checksum, raw_payload, loaded_by_run) VALUES (:source_id, "
        ":external_id, :entity_type, CAST(:fetched_at AS timestamptz), :checksum, "
        "CAST(:raw_payload AS jsonb), :run_id) "
        "ON CONFLICT (source_id, external_id, checksum) DO NOTHING "
        "RETURNING source_record_id"
    )
    for record in dataset.source_records:
        inserted = conn.execute(
            insert,
            {
                **record.model_dump(exclude={"raw_payload"}),
                "raw_payload": _jsonb(record.raw_payload),
                "fetched_at": fetched_at[record.source_id],
                "run_id": summary.run_id,
            },
        ).one_or_none()
        if inserted is None:
            counts.unchanged += 1
        else:
            counts.inserted += 1
    wanted = {(r.source_id, r.external_id): r.checksum for r in dataset.source_records}
    found = conn.execute(
        text(
            "SELECT source_id, external_id, checksum, source_record_id "
            "FROM provenance.source_record WHERE source_id = ANY(:sources)"
        ),
        {"sources": dataset.source_ids},
    )
    return {
        (row.source_id, row.external_id): row.source_record_id
        for row in found
        if wanted.get((row.source_id, row.external_id)) == row.checksum
    }


def _link(
    conn: Connection,
    entity_type: str,
    entity_id: str,
    refs: Iterable[RecordRef],
    ids: Mapping[RecordKey, int],
    summary: LoadSummary,
) -> None:
    counts = summary.table("provenance.entity_source_record")
    sql = text(
        "INSERT INTO provenance.entity_source_record (entity_type, entity_id, "
        "source_record_id, loaded_by_run) VALUES (:entity_type, :entity_id, "
        ":source_record_id, :run_id) ON CONFLICT DO NOTHING RETURNING 1"
    )
    for ref in refs:
        inserted = conn.execute(
            sql,
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "source_record_id": ids[(ref.source_id, ref.external_id)],
                "run_id": summary.run_id,
            },
        ).one_or_none()
        if inserted is None:
            counts.unchanged += 1
        else:
            counts.inserted += 1


def _record_id(ref: RecordRef | None, ids: Mapping[RecordKey, int]) -> int | None:
    return None if ref is None else ids[(ref.source_id, ref.external_id)]


def _stop_row(stop: Stop, ids: Mapping[RecordKey, int]) -> dict[str, Any]:
    row = stop.model_dump(
        exclude={"location", "pattern_ids", "source_record", "records"}
    )
    lon, lat = stop.location
    return {
        **row,
        "lon": lon,
        "lat": lat,
        "source_record_id": _record_id(stop.source_record, ids),
    }


def _issues(conn: Connection, dataset: CanonicalDataset, summary: LoadSummary) -> None:
    counts = summary.table("provenance.data_issue")
    upsert = text(
        "INSERT INTO provenance.data_issue AS t (entity_type, entity_id, issue_type, "
        "description, source_id, evidence, issue_key, loaded_by_run) VALUES "
        "(:entity_type, :entity_id, :issue_type, :description, :source_id, "
        "CAST(:evidence AS jsonb), :issue_key, :run_id) "
        "ON CONFLICT (source_id, issue_key) WHERE issue_key IS NOT NULL DO UPDATE SET "
        "description = EXCLUDED.description, "
        "status = CASE WHEN t.status = 'resolved' THEN 'open' ELSE t.status END, "
        "resolved_at = CASE WHEN t.status = 'resolved' THEN NULL "
        "ELSE t.resolved_at END, "
        "loaded_by_run = EXCLUDED.loaded_by_run "
        "WHERE t.status = 'resolved' OR t.description <> EXCLUDED.description "
        "RETURNING (xmax = 0) AS inserted"
    )
    for issue in dataset.issues:
        result = conn.execute(
            upsert,
            {
                **issue.model_dump(exclude={"evidence"}),
                "evidence": _jsonb(issue.evidence),
                "run_id": summary.run_id,
            },
        ).one_or_none()
        if result is None:
            counts.unchanged += 1
        elif result.inserted:
            counts.inserted += 1
        else:
            counts.updated += 1
    resolved = conn.execute(
        text(
            "UPDATE provenance.data_issue SET status = 'resolved', "
            "resolved_at = greatest(now(), detected_at), loaded_by_run = :run_id "
            "WHERE source_id = ANY(:sources) AND issue_key IS NOT NULL "
            "AND status = 'open' AND NOT (issue_key = ANY(:keys))"
        ),
        {
            "run_id": summary.run_id,
            "sources": dataset.source_ids,
            "keys": [issue.issue_key for issue in dataset.issues],
        },
    )
    counts.retired += resolved.rowcount


def load_dataset(
    conn: Connection, dataset: CanonicalDataset, run_id: str
) -> LoadSummary:
    """Carga el dataset en la transacción de `conn` y devuelve el resumen."""
    summary = LoadSummary(run_id=run_id)
    sources = dataset.source_ids
    _upsert(conn, AGENCY, (a.model_dump() for a in dataset.agencies), summary)
    _upsert(
        conn,
        DATA_SOURCE,
        (
            {**s.model_dump(exclude={"metadata"}), "metadata": _jsonb(s.metadata)}
            for s in dataset.data_sources
        ),
        summary,
    )
    ids = _source_records(conn, dataset, summary)

    _upsert(
        conn,
        SHAPE,
        (
            {
                **s.model_dump(include={"shape_id", "distance_m", "source_id"}),
                "quality": str(s.quality),
                "geom": _jsonb(
                    {"type": "LineString", "coordinates": list(s.coordinates)}
                ),
                "source_record_id": _record_id(s.source_record, ids),
            }
            for s in dataset.shapes
        ),
        summary,
    )
    _upsert(
        conn,
        ROUTE,
        (
            {
                **r.model_dump(exclude={"source_record", "records"}),
                "source_record_id": _record_id(r.source_record, ids),
            }
            for r in dataset.routes
        ),
        summary,
    )
    _upsert(
        conn,
        PATTERN,
        (p.model_dump(exclude={"records"}) for p in dataset.patterns),
        summary,
    )
    # Las estaciones antes que sus andenes, por `parent_station_id`.
    stops = sorted(dataset.stops, key=lambda s: -s.location_type)
    _upsert(
        conn,
        STOP,
        (
            {**_stop_row(s, ids), "location_quality": str(s.location_quality)}
            for s in stops
        ),
        summary,
    )

    for entity_type, entities in (
        ("shape", [(s.shape_id, s.records) for s in dataset.shapes]),
        ("route", [(r.route_id, r.records) for r in dataset.routes]),
        ("route_pattern", [(p.pattern_id, p.records) for p in dataset.patterns]),
        ("stop", [(s.stop_id, s.records) for s in dataset.stops]),
    ):
        for entity, refs in entities:
            _link(conn, entity_type, entity, refs, ids, summary)

    _retire(conn, "transit.stop", [s.stop_id for s in stops], sources, summary)
    _retire(
        conn,
        "transit.route_pattern",
        [p.pattern_id for p in dataset.patterns],
        sources,
        summary,
    )
    _retire(
        conn, "transit.route", [r.route_id for r in dataset.routes], sources, summary
    )
    _issues(conn, dataset, summary)
    return summary
