"""Modelos de la capa normalizada: entidades canónicas listas para cargar (ADR-0035).

Cada entidad tiene su identificador canónico `<agencia>:<tipo>:<código>`
(ADR-0029) y la lista de registros de origen que la produjeron (`records`),
con la que el cargador llena `provenance.entity_source_record`. Los nombres de
los campos siguen las columnas del esquema canónico.
"""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from rutagt.core.snapshots import SNAPSHOT_ID_PATTERN

Longitude = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Position = tuple[Longitude, Latitude]
SourceId = Annotated[str, Field(pattern=r"^[a-z0-9]+(_[a-z0-9]+)*$")]
AgencyId = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]

ENTITY_ID = r"^[a-z0-9]+(-[a-z0-9]+)*:{kind}:[A-Za-z0-9][A-Za-z0-9._-]*$"
"""Mismo formato que `public.rutagt_is_entity_id` en la base."""


RouteId = Annotated[str, Field(pattern=ENTITY_ID.format(kind="route"))]
PatternId = Annotated[str, Field(pattern=ENTITY_ID.format(kind="pattern"))]
ShapeId = Annotated[str, Field(pattern=ENTITY_ID.format(kind="shape"))]
StopId = Annotated[str, Field(pattern=ENTITY_ID.format(kind="stop"))]


class CanonicalModel(BaseModel):
    """Base estricta e inmutable, igual que la capa staging."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Quality(StrEnum):
    """Niveles de `transit.observation_quality` que asigna el constructor."""

    OFFICIAL = "official"
    PROBABLE = "probable"


class RecordRef(CanonicalModel):
    """Registro de origen de una entidad: fuente e identificador externo."""

    source_id: SourceId
    external_id: NonEmpty


class SourceRecord(CanonicalModel):
    """Registro original (`provenance.source_record`)."""

    source_id: SourceId
    external_id: NonEmpty
    entity_type: NonEmpty
    checksum: Sha256
    raw_payload: dict[str, Any]


class DataSource(CanonicalModel):
    """Fuente con la vigencia del snapshot cargado (`provenance.data_source`)."""

    source_id: SourceId
    name: NonEmpty
    authority: str | None
    source_kind: NonEmpty
    source_url: str | None
    attribution: str | None
    attribution_url: str | None
    fetched_at: NonEmpty
    sha256: Sha256
    metadata: dict[str, Any]


class Agency(CanonicalModel):
    """Agencia (`transit.agency`), declarada en `config/agencies.json`."""

    agency_id: AgencyId
    agency_name: NonEmpty
    public_brand: str | None = None
    regulator_name: str | None = None
    agency_url: str | None = None
    agency_timezone: NonEmpty = "America/Guatemala"
    agency_lang: NonEmpty = "es"
    municipality: str | None = None


class Route(CanonicalModel):
    """Línea o ruta comercial (`transit.route`)."""

    route_id: RouteId
    agency_id: AgencyId
    official_code: NonEmpty
    route_short_name: NonEmpty
    route_long_name: str | None
    route_type: int
    source_id: SourceId
    source_record: RecordRef
    records: tuple[RecordRef, ...]


class Shape(CanonicalModel):
    """Trazado continuo, compartido por las variantes iguales (`transit.shape`)."""

    shape_id: ShapeId
    coordinates: Annotated[tuple[Position, ...], Field(min_length=2)]
    distance_m: Annotated[float, Field(ge=0)]
    quality: Quality
    source_id: SourceId
    source_record: RecordRef
    records: tuple[RecordRef, ...]


class Pattern(CanonicalModel):
    """Variante de una ruta con su trazado (`transit.route_pattern`)."""

    pattern_id: PatternId
    route_id: RouteId
    shape_id: ShapeId | None
    variant_name: str | None
    source_id: SourceId
    records: tuple[RecordRef, ...]


class Stop(CanonicalModel):
    """Parada, andén (`location_type` 0) o estación (1) (`transit.stop`).

    `pattern_ids` guarda las variantes que la sirven según la fuente; no tiene
    columna propia: es el insumo de la reconciliación de secuencias (RGT-43).
    """

    stop_id: StopId
    stop_name: NonEmpty
    location_type: Annotated[int, Field(ge=0, le=1)]
    location: Position
    location_quality: Quality
    address: str | None
    zone: str | None
    parent_station_id: StopId | None
    platform_code: str | None
    direction_hint: str | None
    pattern_ids: tuple[NonEmpty, ...]
    source_id: SourceId
    source_record: RecordRef | None
    records: tuple[RecordRef, ...]


class DataIssue(CanonicalModel):
    """Problema con evidencia (`provenance.data_issue`).

    `issue_key` lo identifica entre cargas para no duplicarlo (ADR-0035).
    """

    issue_key: Sha256
    entity_type: NonEmpty
    entity_id: NonEmpty
    issue_type: NonEmpty
    description: NonEmpty
    source_id: SourceId
    evidence: dict[str, Any]


class CanonicalDataset(CanonicalModel):
    """Red canónica de un snapshot: lo que el cargador escribe en PostGIS."""

    snapshot_id: Annotated[str, Field(pattern=SNAPSHOT_ID_PATTERN.pattern)]
    data_sources: tuple[DataSource, ...]
    source_records: tuple[SourceRecord, ...]
    agencies: tuple[Agency, ...]
    routes: tuple[Route, ...]
    shapes: tuple[Shape, ...]
    patterns: tuple[Pattern, ...]
    stops: tuple[Stop, ...]
    issues: tuple[DataIssue, ...]

    @property
    def source_ids(self) -> list[str]:
        """Fuentes que aporta el dataset, para retirar lo que ya no publican."""
        return [source.source_id for source in self.data_sources]
