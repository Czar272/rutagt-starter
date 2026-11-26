-- Reversión de la migración 0003.

DROP FUNCTION public.rutagt_effective_quality(
  transit.observation_quality, timestamptz, timestamptz, timestamptz
);
DROP TABLE provenance.quality_rule;

ALTER TABLE transit.shape DROP COLUMN quality_assessed_at;
ALTER TABLE transit.pattern_stop DROP COLUMN sequence_assessed_at;
ALTER TABLE transit.stop DROP COLUMN location_assessed_at;
