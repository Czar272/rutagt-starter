-- Migración 0003: reglas de vigencia de la calidad (ADR-0031).

-- Fecha de evaluación de cada atributo con calidad.
ALTER TABLE transit.stop
  ADD COLUMN location_assessed_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE transit.pattern_stop
  ADD COLUMN sequence_assessed_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE transit.shape
  ADD COLUMN quality_assessed_at timestamptz NOT NULL DEFAULT now();

-- Antigüedad máxima de cada nivel y nivel al que baja al vencer.
CREATE TABLE provenance.quality_rule (
  quality                transit.observation_quality PRIMARY KEY,
  max_age                interval CHECK (max_age > interval '0'),
  expires_with_source    boolean NOT NULL DEFAULT false,
  degrades_to            transit.observation_quality,
  description            text NOT NULL,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  -- Solo se degrada hacia un nivel de menor confianza.
  CHECK (degrades_to > quality),
  -- Un nivel que vence debe indicar a qué nivel baja, y uno que no vence, no.
  CHECK ((max_age IS NOT NULL OR expires_with_source) = (degrades_to IS NOT NULL))
);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON provenance.quality_rule
  FOR EACH ROW EXECUTE FUNCTION public.rutagt_set_updated_at();

INSERT INTO provenance.quality_rule
  (quality, max_age, expires_with_source, degrades_to, description)
VALUES
  ('official', NULL, true, 'probable',
   'Publicado por la autoridad o el operador; vigente mientras la fuente lo esté'),
  ('verified', interval '365 days', false, 'probable',
   'Confirmado en campo o por fuentes independientes; vence al año'),
  ('probable', NULL, false, NULL,
   'Inferido de datos oficiales con un método documentado; se recalcula con sus insumos'),
  ('estimated', NULL, false, NULL,
   'Calculado con supuestos declarados; se presenta como rango'),
  ('community', interval '30 days', false, 'unverified',
   'Aportado por la comunidad sin confirmar; vence a los 30 días'),
  ('unverified', NULL, false, NULL,
   'Sin evidencia suficiente o con una incidencia abierta');

-- Calidad efectiva: aplica la regla de vigencia del nivel en un momento dado.
-- No modifica el dato almacenado.
CREATE FUNCTION public.rutagt_effective_quality(
  level              transit.observation_quality,
  assessed_at        timestamptz,
  source_valid_to    timestamptz DEFAULT NULL,
  as_of              timestamptz DEFAULT now()
)
RETURNS transit.observation_quality
LANGUAGE sql STABLE PARALLEL SAFE
RETURN (
  SELECT CASE
           WHEN (r.max_age IS NOT NULL AND assessed_at + r.max_age < as_of)
             OR (r.expires_with_source AND source_valid_to < as_of)
           THEN r.degrades_to
           ELSE r.quality
         END
  FROM provenance.quality_rule r
  WHERE r.quality = level
);

COMMENT ON FUNCTION public.rutagt_effective_quality(
  transit.observation_quality, timestamptz, timestamptz, timestamptz
) IS 'Calidad efectiva según las reglas de vigencia de provenance.quality_rule (ADR-0031)';
