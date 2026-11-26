"""Modelos de la capa staging (ADR-0033).

Un adaptador de fuente traduce cada registro crudo a uno de estos modelos, con
el vocabulario del esquema canónico (ADR-0029) pero todavía sin identificadores
canónicos ni fusión entre fuentes. Cada registro conserva su origen exacto
(`SourceRef`) para cargarse después en `provenance.source_record`.
"""

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rutagt.core.snapshots import SNAPSHOT_ID_PATTERN

Longitude = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Position = tuple[Longitude, Latitude]
SourceId = Annotated[str, Field(pattern=r"^[a-z0-9]+(_[a-z0-9]+)*$")]
NonEmpty = Annotated[str, Field(min_length=1)]


class StagingModel(BaseModel):
    """Base estricta: sin campos desconocidos y sin conversión silenciosa de tipos."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SourceRef(StagingModel):
    """Origen de un registro: fuente, identificador externo y atributos crudos."""

    source_id: SourceId
    external_id: NonEmpty
    raw: dict[str, Any]


class Severity(StrEnum):
    """Gravedad de un problema. `error` impide pasar el lote a la capa canónica."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Issue(StagingModel):
    """Problema detectado al adaptar un registro (`provenance.data_issue`)."""

    severity: Severity
    code: Annotated[str, Field(pattern=r"^[a-z0-9]+(_[a-z0-9]+)*$")]
    message: NonEmpty
    external_id: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class StagedStop(StagingModel):
    """Parada, andén o estación (`transit.stop`)."""

    entity_type: Literal["stop"] = "stop"
    source: SourceRef
    name: NonEmpty
    position: Position
    location_type: Annotated[int, Field(ge=0, le=4)] = 0
    code: str | None = None
    address: str | None = None
    zone: str | None = None
    route_codes: tuple[NonEmpty, ...] = ()
    direction_hint: str | None = None


class StagedRoute(StagingModel):
    """Ruta o variante (`transit.route` y `transit.route_pattern`)."""

    entity_type: Literal["route"] = "route"
    source: SourceRef
    route_code: NonEmpty
    variant_code: str | None = None
    short_name: NonEmpty
    long_name: str | None = None
    route_type: Annotated[int, Field(ge=0)] = 3


class StagedShape(StagingModel):
    """Trazado de una ruta o variante (`transit.shape`)."""

    entity_type: Literal["shape"] = "shape"
    source: SourceRef
    route_code: NonEmpty
    variant_code: str | None = None
    coordinates: Annotated[tuple[Position, ...], Field(min_length=2)]
    length_m: Annotated[float, Field(gt=0)]


StagedRecord = Annotated[
    StagedStop | StagedRoute | StagedShape, Field(discriminator="entity_type")
]


class StagingBatch(StagingModel):
    """Resultado de un adaptador para una fuente de un snapshot."""

    source_id: SourceId
    snapshot_id: Annotated[str, Field(pattern=SNAPSHOT_ID_PATTERN.pattern)]
    records: tuple[StagedRecord, ...]
    issues: tuple[Issue, ...] = ()

    @property
    def has_errors(self) -> bool:
        """Indica si algún problema impide pasar el lote a la capa canónica."""
        return any(issue.severity is Severity.ERROR for issue in self.issues)
