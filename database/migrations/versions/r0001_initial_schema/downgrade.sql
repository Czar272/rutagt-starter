-- Reversión de la migración 0001. Conserva la extensión PostGIS, que puede
-- haber existido antes de la migración.

DROP SCHEMA community CASCADE;
DROP SCHEMA realtime CASCADE;
DROP SCHEMA transit CASCADE;
DROP SCHEMA provenance CASCADE;

DROP FUNCTION public.rutagt_distance_m(geometry, geometry);
DROP FUNCTION public.rutagt_set_updated_at();
DROP FUNCTION public.rutagt_is_entity_id(text, text);
