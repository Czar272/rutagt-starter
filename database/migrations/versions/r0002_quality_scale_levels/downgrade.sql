-- Reversión de la migración 0002. PostgreSQL no permite quitar valores de un
-- ENUM: se recrea el tipo con los cuatro niveles originales. Los datos con los
-- niveles nuevos se convierten al más cercano de la escala anterior
-- (estimated -> probable, community -> unverified).

UPDATE transit.shape SET quality = 'probable' WHERE quality = 'estimated';
UPDATE transit.shape SET quality = 'unverified' WHERE quality = 'community';
UPDATE transit.stop SET location_quality = 'probable' WHERE location_quality = 'estimated';
UPDATE transit.stop SET location_quality = 'unverified' WHERE location_quality = 'community';
UPDATE transit.pattern_stop SET sequence_quality = 'probable' WHERE sequence_quality = 'estimated';
UPDATE transit.pattern_stop SET sequence_quality = 'unverified' WHERE sequence_quality = 'community';

ALTER TYPE transit.observation_quality RENAME TO observation_quality_0002;
CREATE TYPE transit.observation_quality AS ENUM ('official', 'verified', 'probable', 'unverified');

ALTER TABLE transit.shape
  ALTER COLUMN quality DROP DEFAULT,
  ALTER COLUMN quality TYPE transit.observation_quality
    USING quality::text::transit.observation_quality,
  ALTER COLUMN quality SET DEFAULT 'unverified';

ALTER TABLE transit.stop
  ALTER COLUMN location_quality DROP DEFAULT,
  ALTER COLUMN location_quality TYPE transit.observation_quality
    USING location_quality::text::transit.observation_quality,
  ALTER COLUMN location_quality SET DEFAULT 'unverified';

ALTER TABLE transit.pattern_stop
  ALTER COLUMN sequence_quality DROP DEFAULT,
  ALTER COLUMN sequence_quality TYPE transit.observation_quality
    USING sequence_quality::text::transit.observation_quality,
  ALTER COLUMN sequence_quality SET DEFAULT 'unverified';

DROP TYPE transit.observation_quality_0002;
