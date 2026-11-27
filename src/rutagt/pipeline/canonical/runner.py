"""Lectura de staging y escritura de la capa normalizada (ADR-0035).

Lee los lotes de `data/staging/<snapshot>/` verificando su SHA-256, la
procedencia cruda de cada fuente y `config/agencies.json`; ejecuta el
constructor y escribe en `data/normalized/<snapshot>/`:

- `canonical.json`: el `CanonicalDataset`;
- `canonical.json.provenance.json`: entradas, commit y conteos (ADR-0032).
"""

import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from rutagt.core.errors import ConfigurationError, SourceError
from rutagt.core.io import (
    git_revision,
    provenance_path,
    read_json,
    sha256_bytes,
    utc_now,
    write_json_atomic,
)
from rutagt.core.settings import PROJECT_ROOT
from rutagt.pipeline.canonical.builder import Source, build_dataset
from rutagt.pipeline.canonical.models import Agency, CanonicalDataset, Rutero
from rutagt.pipeline.normalizers.models import StagingBatch

GENERATOR = "rutagt-canonical"
DATASET_FILE = "canonical.json"


def canonical_sources(sources: list[Source]) -> list[Source]:
    """Fuentes habilitadas que declaran agencia: las que llegan a la red canónica."""
    return [
        source
        for source in sources
        if source.get("agency") and source.get("disabled_reason") is None
    ]


def load_agencies(path: Path) -> list[Agency]:
    """Agencias de `config/agencies.json`, validadas."""
    try:
        content = read_json(path)
        agencies = [Agency.model_validate(item) for item in content["agencies"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigurationError(f"No se pudo leer {path}: {exc}") from exc
    ids = [agency.agency_id for agency in agencies]
    if len(ids) != len(set(ids)):
        raise ConfigurationError(f"Hay agencias duplicadas en {path}")
    return agencies


def load_ruteros(directory: Path) -> list[Rutero]:
    """Ruteros oficiales transcritos (`*.json`) de un directorio, validados."""
    ruteros = []
    for path in sorted(directory.glob("*.json")):
        try:
            ruteros.append(Rutero.model_validate_json(path.read_bytes()))
        except (OSError, ValidationError) as exc:
            raise ConfigurationError(f"Rutero inválido {path}: {exc}") from exc
    return ruteros


def read_verified(path: Path) -> tuple[bytes, dict[str, Any]]:
    """Contenido de un archivo y su procedencia, tras verificar el SHA-256."""
    try:
        body = path.read_bytes()
        provenance: dict[str, Any] = read_json(provenance_path(path))
    except (OSError, ValueError) as exc:
        raise SourceError(f"No se pudo leer {path} o su procedencia: {exc}") from exc
    if provenance.get("sha256") != sha256_bytes(body):
        raise SourceError(f"El SHA-256 de {path} no coincide con su procedencia")
    return body, provenance


def read_batch(staging: Path, source_id: str) -> tuple[StagingBatch, str]:
    """Lote de staging verificado y su SHA-256."""
    body, provenance = read_verified(staging / f"{source_id}.json")
    try:
        batch = StagingBatch.model_validate_json(body)
    except ValidationError as exc:
        raise SourceError(f"El lote de {source_id} no es válido: {exc}") from exc
    return batch, str(provenance["sha256"])


def raw_provenance(snapshot: Path, source: Source) -> dict[str, Any]:
    """Procedencia del archivo crudo de una fuente en el snapshot."""
    path = provenance_path(snapshot / source["output"])
    try:
        content: dict[str, Any] = read_json(path)
    except (OSError, ValueError) as exc:
        raise SourceError(f"No se pudo leer la procedencia {path}: {exc}") from exc
    return content


def build_snapshot(
    sources: list[Source],
    agencies: list[Agency],
    raw_snapshot: Path,
    staging_root: Path,
    normalized_root: Path,
    ruteros: list[Rutero] | None = None,
) -> CanonicalDataset:
    """Construye la red canónica de un snapshot y la escribe con su procedencia."""
    snapshot_id = raw_snapshot.name
    staging = staging_root / snapshot_id
    batches: dict[str, StagingBatch] = {}
    inputs = []
    for source in sources:
        batch, checksum = read_batch(staging, source["id"])
        if batch.snapshot_id != snapshot_id:
            raise SourceError(
                f"El lote de {source['id']} es del snapshot {batch.snapshot_id}"
            )
        batches[source["id"]] = batch
        inputs.append({"file": f"{source['id']}.json", "sha256": checksum})
    dataset = build_dataset(
        snapshot_id,
        batches,
        sources,
        agencies,
        {source["id"]: raw_provenance(raw_snapshot, source) for source in sources},
        ruteros or [],
    )
    destination = normalized_root / snapshot_id / DATASET_FILE
    body = write_json_atomic(destination, dataset.model_dump(mode="json"))
    write_json_atomic(
        provenance_path(destination),
        {
            "generator": GENERATOR,
            "generated_at": utc_now(),
            "run_id": uuid.uuid4().hex,
            "snapshot_id": snapshot_id,
            "inputs": inputs,
            "code_version": git_revision(PROJECT_ROOT),
            "sha256": sha256_bytes(body),
            "counts": counts(dataset),
        },
    )
    return dataset


def counts(dataset: CanonicalDataset) -> dict[str, Any]:
    """Conteo de entidades e incidencias del dataset."""
    return {
        "routes": len(dataset.routes),
        "patterns": len(dataset.patterns),
        "shapes": len(dataset.shapes),
        "stations": sum(stop.location_type == 1 for stop in dataset.stops),
        "stops": sum(stop.location_type == 0 for stop in dataset.stops),
        "pattern_stops": len(dataset.pattern_stops),
        "source_records": len(dataset.source_records),
        "issues": dict(
            sorted(Counter(str(i.evidence["severity"]) for i in dataset.issues).items())
        ),
    }


def read_dataset(normalized_root: Path, snapshot_id: str) -> CanonicalDataset:
    """Dataset canónico verificado de un snapshot."""
    body, _ = read_verified(normalized_root / snapshot_id / DATASET_FILE)
    try:
        return CanonicalDataset.model_validate_json(body)
    except ValidationError as exc:
        raise SourceError(f"El dataset de {snapshot_id} no es válido: {exc}") from exc
