-- Migración 0002: completa la escala de calidad (ADR-0031).
-- El orden del tipo es el orden de la escala, de mayor a menor confianza:
-- official, verified, probable, estimated, community, unverified.
-- Va separada de la 0003 porque un valor nuevo de un ENUM no puede usarse
-- en la misma transacción en que se agrega.

ALTER TYPE transit.observation_quality ADD VALUE 'estimated' AFTER 'probable';
ALTER TYPE transit.observation_quality ADD VALUE 'community' AFTER 'estimated';

COMMENT ON TYPE transit.observation_quality
  IS 'Escala de calidad, de mayor a menor confianza (ADR-0031)';
