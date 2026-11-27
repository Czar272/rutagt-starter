-- Migración 0004: procedencia por entidad y clave de incidencias (ADR-0035).
-- Permite que la carga del dataset canónico sea idempotente y conserve todos
-- los registros de origen de cada entidad.

-- Una entidad canónica puede venir de varios registros (un andén repetido por
-- variante, un trazado compartido). Solo se insertan filas: es append-only y
-- conserva el historial de registros que alimentaron cada entidad.
CREATE TABLE provenance.entity_source_record (
  entity_type            text NOT NULL
                         CHECK (entity_type IN ('agency', 'route', 'route_pattern', 'shape', 'stop')),
  entity_id              text NOT NULL,
  source_record_id       bigint NOT NULL REFERENCES provenance.source_record ON DELETE RESTRICT,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (entity_type, entity_id, source_record_id)
);

CREATE INDEX entity_source_record_source_record_id_idx
  ON provenance.entity_source_record (source_record_id);

COMMENT ON TABLE provenance.entity_source_record
  IS 'Registros de origen de cada entidad canónica (ADR-0035)';

-- Clave estable de las incidencias que detecta el pipeline: la carga no las
-- duplica y conserva el estado que les dio la curación. Las incidencias
-- registradas a mano no tienen clave.
ALTER TABLE provenance.data_issue
  ADD COLUMN issue_key text CHECK (issue_key ~ '^[0-9a-f]{64}$');

CREATE UNIQUE INDEX data_issue_source_id_issue_key_key
  ON provenance.data_issue (source_id, issue_key)
  WHERE issue_key IS NOT NULL;

COMMENT ON COLUMN provenance.data_issue.issue_key
  IS 'SHA-256 de fuente, tipo, entidad y evidencia de una incidencia del pipeline';
