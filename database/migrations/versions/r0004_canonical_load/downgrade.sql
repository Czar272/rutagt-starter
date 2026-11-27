-- Revierte la migración 0004.

DROP INDEX provenance.data_issue_source_id_issue_key_key;
ALTER TABLE provenance.data_issue DROP COLUMN issue_key;
DROP TABLE provenance.entity_source_record;
