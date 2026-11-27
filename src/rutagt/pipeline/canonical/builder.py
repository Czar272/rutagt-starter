"""Constructor canónico: combina los lotes de staging de un snapshot (ADR-0035).

Función pura: recibe los lotes ya leídos y la configuración, y devuelve un
`CanonicalDataset`. Reglas:

- **Rutas y variantes**: una `Route` por código de ruta y un `Pattern` por
  variante (o por ruta si la fuente no tiene variantes).
- **Trazados**: las variantes con coordenadas idénticas comparten un `Shape`,
  con el código menor del grupo. Un trazado unido desde varios tramos
  (`tramos_unidos`) queda `probable`; el resto, `official` (ADR-0031).
- **Paradas físicas**: los registros con el mismo nombre a menos de
  `SAME_PLACE_M` son una sola parada (la fuente repite el andén por variante).
- **Estaciones** (`group_stations`): las paradas con el mismo nombre forman una
  estación (`location_type = 1`) en el centroide de sus andenes, que quedan
  como hijos (`parent_station_id`) numerados `1, 2, …` por su primer registro.
- **Problemas**: los de staging pasan a `data_issue` sobre la entidad de su
  registro; el constructor añade `estacion_dispersa`, `nombres_unificados` y
  `sentido_contradictorio`.

No fusiona paradas distintas por cercanía ni resuelve duplicados posibles
(`numero_repetido`, `sentido_duplicado`): quedan como incidencias abiertas
para curación con evidencia.
"""

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from rutagt.core.errors import ConfigurationError, SourceError
from rutagt.pipeline.canonical.identifiers import (
    code_order,
    entity_id,
    place_key,
)
from rutagt.pipeline.canonical.models import (
    Agency,
    CanonicalDataset,
    DataIssue,
    DataSource,
    Pattern,
    PatternStop,
    Quality,
    RecordRef,
    Route,
    Rutero,
    Shape,
    SourceRecord,
    Stop,
)
from rutagt.pipeline.canonical.sequences import (
    SequenceResult,
    is_circuit,
    sequence_with_rutero,
    sequence_without_rutero,
)
from rutagt.pipeline.normalizers.common import haversine_m
from rutagt.pipeline.normalizers.models import (
    Severity,
    StagedRoute,
    StagedShape,
    StagedStop,
    StagingBatch,
)

Source = dict[str, Any]
"""Entrada de `config/sources.json`."""

SAME_PLACE_M = 1.0
"""Distancia hasta la que dos registros con el mismo nombre son la misma parada.

En 2025 los andenes repetidos por variante tienen coordenadas idénticas.
"""

STATION_RADIUS_M = 300.0
"""Distancia máxima de un andén al centro de su estación; la mayor de 2025 es 101 m."""


def _order(ref: RecordRef) -> tuple[str, tuple[int, int, str]]:
    return ref.source_id, code_order(ref.external_id)


def ref_of(record: StagedStop | StagedRoute | StagedShape) -> RecordRef:
    """Referencia al registro de origen de un registro de staging."""
    return RecordRef(
        source_id=record.source.source_id, external_id=record.source.external_id
    )


def checksum(value: Any) -> str:
    """SHA-256 del JSON canónico de un valor (claves ordenadas, sin espacios)."""
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass
class _Issues:
    """Acumula problemas y los convierte en `DataIssue` con su clave estable."""

    items: list[DataIssue] = field(default_factory=list)

    def add(
        self,
        *,
        source_id: str,
        entity_type: str,
        entity_id: str,
        issue_type: str,
        description: str,
        severity: Severity,
        evidence: Mapping[str, Any],
    ) -> None:
        full_evidence = {"severity": str(severity), **evidence}
        key = checksum([source_id, entity_type, entity_id, issue_type, full_evidence])
        self.items.append(
            DataIssue(
                issue_key=key,
                entity_type=entity_type,
                entity_id=entity_id,
                issue_type=issue_type,
                description=description,
                source_id=source_id,
                evidence=full_evidence,
            )
        )

    def from_staging(
        self, batch: StagingBatch, entity_of: Mapping[str, tuple[str, str]]
    ) -> None:
        """Problemas de un lote sobre la entidad de su registro, o sobre la fuente."""
        for issue in batch.issues:
            entity_type, entity = entity_of.get(
                issue.external_id or "", ("data_source", batch.source_id)
            )
            evidence = dict(issue.evidence)
            if issue.external_id is not None:
                evidence["external_id"] = issue.external_id
            self.add(
                source_id=batch.source_id,
                entity_type=entity_type,
                entity_id=entity,
                issue_type=issue.code,
                description=issue.message,
                severity=issue.severity,
                evidence=evidence,
            )


def _refs(
    records: Iterable[StagedStop | StagedRoute | StagedShape],
) -> tuple[RecordRef, ...]:
    return tuple(sorted({ref_of(record) for record in records}, key=_order))


def _has_issue(batch: StagingBatch, code: str) -> set[str]:
    return {
        issue.external_id
        for issue in batch.issues
        if issue.code == code and issue.external_id is not None
    }


# ---------------------------------------------------------------------------
# Rutas, variantes y trazados
# ---------------------------------------------------------------------------


def pattern_code(record: StagedRoute | StagedShape) -> str:
    """Código de la variante, o de la ruta si la fuente no tiene variantes."""
    return record.variant_code or record.route_code


@dataclass
class _RouteNetwork:
    routes: list[Route]
    shapes: list[Shape]
    patterns: list[Pattern]
    entity_of: dict[str, tuple[str, str]]


def build_routes(batch: StagingBatch, agency_id: str) -> _RouteNetwork:
    """Rutas, variantes y trazados de un lote de rutas."""
    staged_routes = [r for r in batch.records if isinstance(r, StagedRoute)]
    staged_shapes = [r for r in batch.records if isinstance(r, StagedShape)]
    joined = _has_issue(batch, "tramos_unidos")

    by_route: dict[str, list[StagedRoute]] = defaultdict(list)
    for route in staged_routes:
        by_route[route.route_code].append(route)
    routes = []
    for code in sorted(by_route, key=code_order):
        variants = sorted(by_route[code], key=lambda r: code_order(pattern_code(r)))
        base = variants[0]
        routes.append(
            Route(
                route_id=entity_id(agency_id, "route", code),
                agency_id=agency_id,
                official_code=code,
                route_short_name=base.short_name,
                route_long_name=base.long_name,
                route_type=base.route_type,
                source_id=batch.source_id,
                source_record=ref_of(base),
                records=_refs(variants),
            )
        )

    by_geometry: dict[tuple[tuple[float, float], ...], list[StagedShape]] = defaultdict(
        list
    )
    for shape in staged_shapes:
        by_geometry[shape.coordinates].append(shape)
    shapes = []
    shape_of: dict[str, str] = {}
    for group in by_geometry.values():
        group.sort(key=lambda s: code_order(pattern_code(s)))
        first = group[0]
        shape_id = entity_id(agency_id, "shape", pattern_code(first))
        shape_of.update((pattern_code(s), shape_id) for s in group)
        shapes.append(
            Shape(
                shape_id=shape_id,
                coordinates=first.coordinates,
                distance_m=round(first.length_m, 2),
                quality=(
                    Quality.PROBABLE
                    if any(s.source.external_id in joined for s in group)
                    else Quality.OFFICIAL
                ),
                source_id=batch.source_id,
                source_record=ref_of(first),
                records=_refs(group),
            )
        )
    shapes.sort(key=lambda s: code_order(s.shape_id.rsplit(":", 1)[1]))

    patterns = []
    entity_of: dict[str, tuple[str, str]] = {}
    for route in sorted(staged_routes, key=lambda r: code_order(pattern_code(r))):
        code = pattern_code(route)
        pattern_id = entity_id(agency_id, "pattern", code)
        entity_of[route.source.external_id] = ("route_pattern", pattern_id)
        patterns.append(
            Pattern(
                pattern_id=pattern_id,
                route_id=entity_id(agency_id, "route", route.route_code),
                shape_id=shape_of.get(code),
                variant_name=route.long_name,
                source_id=batch.source_id,
                records=(ref_of(route),),
            )
        )
    return _RouteNetwork(routes, shapes, patterns, entity_of)


# ---------------------------------------------------------------------------
# Paradas, andenes y estaciones
# ---------------------------------------------------------------------------


def _record_order(record: StagedStop) -> tuple[int, int, str]:
    return code_order(record.source.external_id)


def _common_name(records: list[StagedStop]) -> str:
    """Nombre más frecuente; en empate, el del primer registro."""
    counts = Counter(record.name for record in records)
    top = max(counts.values())
    return next(record.name for record in records if counts[record.name] == top)


def physical_stops(records: list[StagedStop]) -> list[list[StagedStop]]:
    """Agrupa los registros de un mismo nombre que están en el mismo lugar."""
    clusters: list[list[StagedStop]] = []
    for record in sorted(records, key=_record_order):
        for cluster in clusters:
            if haversine_m(cluster[0].position, record.position) <= SAME_PLACE_M:
                cluster.append(record)
                break
        else:
            clusters.append([record])
    return clusters


def centroid(positions: Iterable[tuple[float, float]]) -> tuple[float, float]:
    """Centroide simple de posiciones cercanas (escala de una estación)."""
    points = list(positions)
    return (
        round(sum(p[0] for p in points) / len(points), 9),
        round(sum(p[1] for p in points) / len(points), 9),
    )


@dataclass
class _StopContext:
    agency_id: str
    source_id: str
    patterns: set[str]
    issues: _Issues
    entity_of: dict[str, tuple[str, str]] = field(default_factory=dict)


def _stop(
    ctx: _StopContext,
    stop_id: str,
    cluster: list[StagedStop],
    *,
    parent: str | None = None,
    platform_code: str | None = None,
) -> Stop:
    first = cluster[0]
    hints = sorted({r.direction_hint for r in cluster if r.direction_hint})
    if len(hints) > 1:
        ctx.issues.add(
            source_id=ctx.source_id,
            entity_type="stop",
            entity_id=stop_id,
            issue_type="sentido_contradictorio",
            description=f"{first.name} tiene registros con sentidos distintos",
            severity=Severity.WARNING,
            evidence={"sentidos": hints},
        )
    pattern_ids = sorted(
        {
            entity_id(ctx.agency_id, "pattern", code)
            for record in cluster
            for code in record.route_codes
            if code in ctx.patterns
        },
        key=lambda p: code_order(p.rsplit(":", 1)[1]),
    )
    for record in cluster:
        ctx.entity_of[record.source.external_id] = ("stop", stop_id)
    return Stop(
        stop_id=stop_id,
        stop_name=_common_name(cluster),
        location_type=0,
        location=first.position,
        location_quality=Quality.OFFICIAL,
        address=first.address,
        zone=first.zone,
        parent_station_id=parent,
        platform_code=platform_code,
        direction_hint=hints[0] if len(hints) == 1 else None,
        pattern_ids=tuple(pattern_ids),
        source_id=ctx.source_id,
        source_record=ref_of(first),
        records=_refs(cluster),
    )


def _station(ctx: _StopContext, key: str, platforms: list[Stop]) -> Stop:
    station_id = entity_id(ctx.agency_id, "stop", key)
    center = centroid(p.location for p in platforms)
    radius = max(haversine_m(center, p.location) for p in platforms)
    names = sorted({p.stop_name for p in platforms})
    first = platforms[0]
    if radius > STATION_RADIUS_M:
        ctx.issues.add(
            source_id=ctx.source_id,
            entity_type="stop",
            entity_id=station_id,
            issue_type="estacion_dispersa",
            description=(
                f"Un andén de {first.stop_name} está a {radius:.0f} m del centro "
                "de la estación"
            ),
            severity=Severity.WARNING,
            evidence={"radio_m": round(radius, 1)},
        )
    if len(names) > 1:
        ctx.issues.add(
            source_id=ctx.source_id,
            entity_type="stop",
            entity_id=station_id,
            issue_type="nombres_unificados",
            description=f"Andenes con nombres distintos unidos en {key}",
            severity=Severity.INFO,
            evidence={"nombres": names},
        )
    return Stop(
        stop_id=station_id,
        stop_name=Counter(p.stop_name for p in platforms).most_common(1)[0][0],
        location_type=1,
        location=center,
        location_quality=Quality.PROBABLE,
        address=first.address,
        zone=first.zone,
        parent_station_id=None,
        platform_code=None,
        direction_hint=None,
        pattern_ids=tuple(
            sorted(
                {p for platform in platforms for p in platform.pattern_ids},
                key=lambda p: code_order(p.rsplit(":", 1)[1]),
            )
        ),
        source_id=ctx.source_id,
        source_record=None,
        records=(),
    )


def build_stops(
    batch: StagingBatch,
    agency_id: str,
    patterns: Iterable[Pattern],
    *,
    group_stations: bool,
    issues: _Issues,
) -> tuple[list[Stop], dict[str, tuple[str, str]]]:
    """Paradas de un lote; con `group_stations`, estaciones y sus andenes."""
    ctx = _StopContext(
        agency_id=agency_id,
        source_id=batch.source_id,
        patterns={p.pattern_id.rsplit(":", 1)[1] for p in patterns},
        issues=issues,
    )
    by_place: dict[str, list[StagedStop]] = defaultdict(list)
    for record in batch.records:
        if isinstance(record, StagedStop):
            by_place[place_key(record.name)].append(record)

    stops: list[Stop] = []
    for key in sorted(by_place):
        clusters = physical_stops(by_place[key])
        if group_stations:
            station_id = entity_id(agency_id, "stop", key)
            platforms = [
                _stop(
                    ctx,
                    entity_id(agency_id, "stop", f"{key}.{number}"),
                    cluster,
                    parent=station_id,
                    platform_code=str(number),
                )
                for number, cluster in enumerate(clusters, start=1)
            ]
            stops.append(_station(ctx, key, platforms))
            stops.extend(platforms)
        elif len(clusters) == 1:
            stops.append(_stop(ctx, entity_id(agency_id, "stop", key), clusters[0]))
        else:
            stops.extend(
                _stop(ctx, entity_id(agency_id, "stop", f"{key}.{number}"), cluster)
                for number, cluster in enumerate(clusters, start=1)
            )
    return stops, ctx.entity_of


# ---------------------------------------------------------------------------
# Secuencias (ADR-0036)
# ---------------------------------------------------------------------------


@dataclass
class _Sequenced:
    patterns: list[Pattern]
    stops: list[Stop]
    pattern_stops: list[PatternStop]


def _ruteros_by_pattern(
    ruteros: Sequence[Rutero], patterns: Iterable[Pattern], issues: _Issues
) -> dict[str, Rutero]:
    known = {pattern.pattern_id for pattern in patterns}
    found: dict[str, Rutero] = {}
    for rutero in ruteros:
        pattern_id = entity_id(rutero.agency_id, "pattern", rutero.pattern_code)
        if pattern_id not in known:
            # La fuente dejó de publicar la variante o el dataset es parcial.
            issues.add(
                source_id=rutero.source_id,
                entity_type="data_source",
                entity_id=rutero.source_id,
                issue_type="rutero_sin_variante",
                description=f"El rutero es de {pattern_id}, que no está en el dataset",
                severity=Severity.WARNING,
                evidence={"pattern_id": pattern_id},
            )
            continue
        if pattern_id in found:
            raise ConfigurationError(f"Hay dos ruteros para {pattern_id}")
        found[pattern_id] = rutero
    return found


def _with_rutero(
    pattern: Pattern,
    shape: Shape,
    served: list[Stop],
    rutero: Rutero,
    issues: _Issues,
    codes: dict[str, set[str]],
) -> tuple[SequenceResult, dict[str, Any]]:
    result = sequence_with_rutero(pattern.pattern_id, shape, served, rutero)
    attributes: dict[str, Any] = {"sequence_source": rutero.source_id}
    for assignment in result.assignments:
        stop = assignment.stop
        if assignment.stop_code == rutero.terminal_stop_code:
            attributes["terminal_stop_id"] = stop.stop_id
        if assignment.confirmed:
            codes[stop.stop_id].add(assignment.stop_code)
            continue
        reviewed = assignment.reviewed is not None
        issues.add(
            source_id=rutero.source_id,
            entity_type="stop",
            entity_id=stop.stop_id,
            issue_type=(
                "asignacion_contradice_revision" if reviewed else "parada_por_revisar"
            ),
            description=(
                f"La parada {assignment.stop_code} del rutero se asignó a "
                f"{stop.stop_name}, "
                + (
                    f"pero la revisión manual eligió el registro {assignment.reviewed}"
                    if reviewed
                    else "con una dirección poco parecida"
                )
            ),
            severity=Severity.WARNING,
            evidence={
                "pattern_id": pattern.pattern_id,
                "secuencia": assignment.sequence,
                "codigo": assignment.stop_code,
                "puntaje": assignment.score,
                "registros": [r.external_id for r in stop.records],
                "revision": assignment.reviewed,
            },
        )
    excluded = {r.external_id: r.reason for r in rutero.excluded_layer_records}
    for stop in result.unassigned:
        reasons = [
            excluded[r.external_id] for r in stop.records if r.external_id in excluded
        ]
        issues.add(
            source_id=rutero.source_id,
            entity_type="stop",
            entity_id=stop.stop_id,
            issue_type="parada_fuera_de_rutero",
            description=(
                f"{stop.stop_name} sirve a {pattern.pattern_id} según la capa, "
                "pero no está en su rutero"
            ),
            severity=Severity.WARNING,
            evidence={
                "pattern_id": pattern.pattern_id,
                "registros": [r.external_id for r in stop.records],
                "motivo_revision": reasons[0] if reasons else None,
            },
        )
    return result, attributes


def _official_codes(
    stops: list[Stop], codes: Mapping[str, set[str]], issues: _Issues
) -> list[Stop]:
    """Asigna a cada parada el código del rutero que la identificó."""
    result = []
    for stop in stops:
        found = sorted(codes.get(stop.stop_id, set()))
        if len(found) > 1:
            issues.add(
                source_id=stop.source_id,
                entity_type="stop",
                entity_id=stop.stop_id,
                issue_type="codigo_contradictorio",
                description=f"{stop.stop_name} tiene códigos distintos en los ruteros",
                severity=Severity.WARNING,
                evidence={"codigos": found},
            )
        result.append(
            stop.model_copy(update={"stop_code": found[0]}) if len(found) == 1 else stop
        )
    return result


def sequence_patterns(
    patterns: list[Pattern],
    shapes: list[Shape],
    stops: list[Stop],
    ruteros: Sequence[Rutero],
    issues: _Issues,
) -> _Sequenced:
    """Secuencia de cada variante con trazado: del rutero o por proyección."""
    shape_by_id = {shape.shape_id: shape for shape in shapes}
    by_rutero = _ruteros_by_pattern(ruteros, patterns, issues)
    served: dict[str, list[Stop]] = defaultdict(list)
    for stop in stops:
        if stop.location_type == 0:
            for pattern_id in stop.pattern_ids:
                served[pattern_id].append(stop)

    codes: dict[str, set[str]] = defaultdict(set)
    result_patterns = []
    pattern_stops: list[PatternStop] = []
    for pattern in patterns:
        shape = shape_by_id.get(pattern.shape_id or "")
        members = served.get(pattern.pattern_id, [])
        if shape is None or not members:
            result_patterns.append(pattern)
            continue
        attributes: dict[str, Any] = {"circuit": is_circuit(shape)}
        result: SequenceResult | None = None
        rutero = by_rutero.get(pattern.pattern_id)
        if rutero is not None:
            try:
                result, extra = _with_rutero(
                    pattern, shape, members, rutero, issues, codes
                )
                attributes.update(extra)
            except ValueError:
                issues.add(
                    source_id=rutero.source_id,
                    entity_type="route_pattern",
                    entity_id=pattern.pattern_id,
                    issue_type="rutero_incompleto",
                    description=(
                        f"La capa tiene menos paradas de {pattern.pattern_id} "
                        "que el rutero"
                    ),
                    severity=Severity.WARNING,
                    evidence={"rutero": len(rutero.stops), "capa": len(members)},
                )
        if result is None:
            result = sequence_without_rutero(pattern.pattern_id, shape, members)
            attributes["sequence_source"] = "trazado"
            issues.add(
                source_id=pattern.source_id,
                entity_type="route_pattern",
                entity_id=pattern.pattern_id,
                issue_type="secuencia_sin_rutero",
                description=(
                    f"La secuencia de {pattern.pattern_id} sale del orden sobre "
                    "el trazado; falta el rutero oficial"
                ),
                severity=Severity.WARNING,
                evidence={"paradas": len(members)},
            )
        pattern_stops += result.pattern_stops
        result_patterns.append(pattern.model_copy(update={"attributes": attributes}))
    return _Sequenced(
        result_patterns, _official_codes(stops, codes, issues), pattern_stops
    )


# ---------------------------------------------------------------------------
# Fuentes, registros y dataset
# ---------------------------------------------------------------------------


def data_source(source: Source, raw_provenance: Mapping[str, Any]) -> DataSource:
    """Fila de `provenance.data_source` con la vigencia del snapshot."""
    for required in ("source_kind", "agency"):
        if not source.get(required):
            raise ConfigurationError(
                f"La fuente {source['id']} no declara '{required}' en el catálogo"
            )
    if raw_provenance.get("sha256") is None or not raw_provenance.get("fetched_at"):
        raise SourceError(
            f"La procedencia cruda de {source['id']} no tiene sha256 ni fetched_at"
        )
    catalog = source.get("catalog_url") or source.get("url")
    metadata = {
        key: raw_provenance[key]
        for key in ("resolved_item_id", "record_count", "license_note")
        if raw_provenance.get(key) is not None
    }
    return DataSource(
        source_id=source["id"],
        name=source["name"],
        authority=source.get("authority"),
        source_kind=source["source_kind"],
        source_url=raw_provenance.get("resolved_layer_url") or catalog,
        attribution=source.get("authority"),
        attribution_url=catalog,
        fetched_at=raw_provenance["fetched_at"],
        sha256=raw_provenance["sha256"],
        metadata=metadata,
    )


def rutero_source(rutero: Rutero) -> DataSource:
    """Fila de `provenance.data_source` de un rutero oficial transcrito."""
    document = rutero.source
    validated_at = document.get("validation", {}).get("validated_at")
    if not (document.get("document_sha256") and validated_at):
        raise ConfigurationError(
            f"El rutero {rutero.source_id} no declara document_sha256 ni "
            "validation.validated_at"
        )
    return DataSource(
        source_id=rutero.source_id,
        name=f"Rutero oficial {rutero.pattern_code}: {rutero.route_name}",
        authority=document.get("authority"),
        source_kind="official_open_data",
        source_url=document.get("url"),
        attribution=document.get("authority"),
        attribution_url=document.get("url"),
        # Fecha en que la transcripción se validó contra el documento oficial.
        fetched_at=f"{validated_at}T00:00:00+00:00",
        sha256=document["document_sha256"],
        metadata={
            key: document[key]
            for key in ("version", "valid_from", "document", "validation")
            if key in document
        },
    )


def source_records(batch: StagingBatch) -> list[SourceRecord]:
    """Registros originales del lote, uno por identificador externo."""
    seen: dict[str, SourceRecord] = {}
    for record in batch.records:
        external_id = record.source.external_id
        if external_id not in seen:
            seen[external_id] = SourceRecord(
                source_id=batch.source_id,
                external_id=external_id,
                entity_type=record.entity_type,
                checksum=checksum(record.source.raw),
                raw_payload=record.source.raw,
            )
    return [seen[key] for key in sorted(seen, key=code_order)]


def build_dataset(
    snapshot_id: str,
    batches: Mapping[str, StagingBatch],
    sources: list[Source],
    agencies: list[Agency],
    raw_provenance: Mapping[str, Mapping[str, Any]],
    ruteros: Sequence[Rutero] = (),
) -> CanonicalDataset:
    """Combina los lotes de un snapshot en la red canónica.

    `sources` son las fuentes del catálogo que llegan a la capa canónica;
    todas deben tener lote en `batches`, sin problemas de severidad `error`.
    `ruteros` son los ruteros oficiales transcritos que fijan la secuencia de
    su variante (ADR-0036).
    """
    known_agencies = {agency.agency_id for agency in agencies}
    by_id = {source["id"]: source for source in sources}
    for source in sources:
        batch = batches.get(source["id"])
        if batch is None:
            raise SourceError(f"Falta el lote de staging de {source['id']}")
        if batch.has_errors:
            raise SourceError(
                f"El lote de {source['id']} tiene problemas de severidad error "
                "y no puede pasar a la capa canónica (ADR-0033)"
            )
        if source.get("agency") not in known_agencies:
            raise ConfigurationError(
                f"La fuente {source['id']} usa una agencia desconocida: "
                f"{source.get('agency')!r}"
            )

    issues = _Issues()
    routes: list[Route] = []
    shapes: list[Shape] = []
    patterns_by_source: dict[str, list[Pattern]] = {}
    stops: list[Stop] = []
    route_sources = [
        s
        for s in sources
        if any(isinstance(r, StagedRoute) for r in batches[s["id"]].records)
    ]
    for source in route_sources:
        batch = batches[source["id"]]
        network = build_routes(batch, source["agency"])
        routes += network.routes
        shapes += network.shapes
        patterns_by_source[source["id"]] = network.patterns
        issues.from_staging(batch, network.entity_of)
    for source in sources:
        if source in route_sources:
            continue
        batch = batches[source["id"]]
        shapes_source = source.get("shapes_source")
        if shapes_source is not None and shapes_source not in by_id:
            raise ConfigurationError(
                f"La fuente {source['id']} necesita {shapes_source} en el dataset"
            )
        built, entity_of = build_stops(
            batch,
            source["agency"],
            patterns_by_source.get(shapes_source or "", []),
            group_stations=bool(source.get("group_stations")),
            issues=issues,
        )
        stops += built
        issues.from_staging(batch, entity_of)

    patterns = [p for ps in patterns_by_source.values() for p in ps]
    sequenced = sequence_patterns(patterns, shapes, stops, ruteros, issues)

    used_agencies = {source["agency"] for source in sources}
    return CanonicalDataset(
        snapshot_id=snapshot_id,
        data_sources=tuple(
            sorted(
                [
                    *(
                        data_source(source, raw_provenance.get(source["id"], {}))
                        for source in sources
                    ),
                    *(rutero_source(rutero) for rutero in ruteros),
                ],
                key=lambda s: s.source_id,
            )
        ),
        source_records=tuple(
            record
            for source in sorted(sources, key=lambda s: str(s["id"]))
            for record in source_records(batches[source["id"]])
        ),
        agencies=tuple(a for a in agencies if a.agency_id in used_agencies),
        routes=tuple(routes),
        shapes=tuple(shapes),
        patterns=tuple(sequenced.patterns),
        stops=tuple(sequenced.stops),
        pattern_stops=tuple(sequenced.pattern_stops),
        issues=tuple(issues.items),
    )
