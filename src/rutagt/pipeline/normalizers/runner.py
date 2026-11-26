"""Ejecución de adaptadores sobre un snapshot crudo (ADR-0033).

Por cada fuente con adaptador, el runner lee el archivo crudo y su procedencia,
verifica el SHA-256, ejecuta el adaptador y escribe en
`data/staging/<snapshot_id>/`:

- `<source_id>.json`: el `StagingBatch` serializado;
- `<source_id>.json.provenance.json`: entradas, commit y conteos (ADR-0032);
- `run_manifest.json`: resumen de la ejecución.

Una fuente que falla no detiene las demás, igual que en el recolector.
"""

import logging
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
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
from rutagt.core.logging import log_context
from rutagt.core.settings import PROJECT_ROOT
from rutagt.pipeline.normalizers.base import RawInput, get_adapter, registered_sources
from rutagt.pipeline.normalizers.models import StagingBatch

logger = logging.getLogger(__name__)

GENERATOR = "rutagt-normalize"

Source = dict[str, Any]
"""Entrada del catálogo `config/sources.json`."""


@dataclass
class RunSummary:
    """Resultado de normalizar un snapshot."""

    run_id: str
    successful: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Sin fuentes fallidas ni lotes con problemas de severidad `error`."""
        return not self.failed and not any(r["has_errors"] for r in self.successful)


def select_adapted_sources(
    sources: list[Source], requested: list[str] | None = None
) -> list[Source]:
    """Fuentes del catálogo con adaptador, o las solicitadas explícitamente."""
    adapted = set(registered_sources())
    by_id = {source["id"]: source for source in sources}
    if not requested:
        return [source for source in sources if source["id"] in adapted]
    unknown = sorted(set(requested) - set(by_id))
    if unknown:
        raise ConfigurationError(f"Fuentes desconocidas: {', '.join(unknown)}")
    missing = sorted(set(requested) - adapted)
    if missing:
        raise ConfigurationError(f"Fuentes sin adaptador: {', '.join(missing)}")
    return [by_id[source_id] for source_id in dict.fromkeys(requested)]


def read_raw(source: Source, snapshot: Path) -> tuple[RawInput, str]:
    """Lee el archivo crudo y su procedencia; devuelve la entrada y su SHA-256."""
    path = snapshot / source["output"]
    try:
        content = path.read_bytes()
        provenance = read_json(provenance_path(path))
    except OSError as exc:
        raise SourceError(
            f"El snapshot {snapshot.name} no contiene {source['output']}: {exc}"
        ) from exc
    checksum = sha256_bytes(content)
    if provenance.get("sha256") != checksum:
        raise SourceError(
            f"{source['output']} no coincide con el SHA-256 de su procedencia"
        )
    try:
        parsed = read_json(path)
    except ValueError as exc:
        raise SourceError(f"{source['output']} no es JSON válido: {exc}") from exc
    raw = RawInput(
        source_id=source["id"],
        snapshot_id=snapshot.name,
        content=parsed,
        provenance=provenance,
    )
    return raw, checksum


def _adapt(source: Source, snapshot: Path) -> tuple[StagingBatch, str]:
    raw, checksum = read_raw(source, snapshot)
    try:
        batch = get_adapter(source["id"])(raw)
    except ValidationError as exc:
        raise SourceError(
            f"El adaptador produjo registros inválidos: {exc.error_count()} errores; "
            f"primero: {exc.errors()[0]['msg']} en {exc.errors()[0]['loc']}"
        ) from exc
    if (batch.source_id, batch.snapshot_id) != (source["id"], snapshot.name):
        raise SourceError(
            "El adaptador devolvió un lote de otra fuente o snapshot: "
            f"{batch.source_id}/{batch.snapshot_id}"
        )
    return batch, checksum


def write_batch(
    batch: StagingBatch,
    staging: Path,
    *,
    run_id: str,
    input_file: str,
    input_sha256: str,
) -> dict[str, Any]:
    """Escribe el lote y su procedencia; devuelve el resumen para el manifiesto."""
    destination = staging / f"{batch.source_id}.json"
    body = write_json_atomic(destination, batch.model_dump(mode="json"))
    code_version = git_revision(PROJECT_ROOT)
    summary = {
        "source_id": batch.source_id,
        "records": dict(sorted(Counter(r.entity_type for r in batch.records).items())),
        "issues": dict(sorted(Counter(str(i.severity) for i in batch.issues).items())),
        "has_errors": batch.has_errors,
    }
    write_json_atomic(
        provenance_path(destination),
        {
            "generator": GENERATOR,
            "generated_at": utc_now(),
            "run_id": run_id,
            "snapshot_id": batch.snapshot_id,
            "inputs": [{"file": input_file, "sha256": input_sha256}],
            "code_version": code_version,
            # Las correcciones manuales se versionan en el repositorio, junto al
            # código que las aplica (ADR-0033).
            "corrections_version": code_version,
            "sha256": sha256_bytes(body),
            **summary,
        },
    )
    return summary


def normalize_snapshot(
    sources: list[Source], snapshot: Path, staging_root: Path
) -> RunSummary:
    """Ejecuta los adaptadores de `sources` sobre un snapshot y escribe staging."""
    summary = RunSummary(run_id=uuid.uuid4().hex)
    staging = staging_root / snapshot.name
    started_at = utc_now()
    with log_context(run_id=summary.run_id, snapshot_id=snapshot.name):
        logger.info(
            "Normalizando %d fuentes del snapshot %s", len(sources), snapshot.name
        )
        for source in sources:
            with log_context(source_id=source["id"]):
                start = time.perf_counter()
                try:
                    batch, checksum = _adapt(source, snapshot)
                    result = write_batch(
                        batch,
                        staging,
                        run_id=summary.run_id,
                        input_file=source["output"],
                        input_sha256=checksum,
                    )
                except (SourceError, ConfigurationError, OSError) as exc:
                    summary.failed.append(
                        {"source_id": source["id"], "error": str(exc)}
                    )
                    logger.error("Falló %s: %s", source["id"], exc)
                    continue
                except Exception as exc:
                    # Un error inesperado en un adaptador no detiene los demás.
                    summary.failed.append(
                        {"source_id": source["id"], "error": repr(exc)}
                    )
                    logger.exception("Error inesperado en %s", source["id"])
                    continue
                result["duration_seconds"] = round(time.perf_counter() - start, 3)
                summary.successful.append(result)
                log = logger.warning if result["has_errors"] else logger.info
                log(
                    "%s: %s, problemas %s",
                    source["id"],
                    result["records"],
                    result["issues"],
                )
        write_json_atomic(
            staging / "run_manifest.json",
            {
                "generator": GENERATOR,
                "run_id": summary.run_id,
                "snapshot_id": snapshot.name,
                "started_at": started_at,
                "finished_at": utc_now(),
                "ok": summary.ok,
                "successful": summary.successful,
                "failed": summary.failed,
            },
        )
    return summary
