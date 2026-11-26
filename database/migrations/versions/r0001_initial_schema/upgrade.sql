-- Migración 0001: esquema canónico inicial de RutaGT (PostgreSQL 17 + PostGIS 3.5).
-- Implementa la revisión del esquema (docs/architecture/canonical-schema-review.md)
-- y las convenciones del ADR-0029. Las referencias Dn remiten a sus decisiones.
-- Una migración aplicada no se modifica (ADR-0030): los cambios van en revisiones nuevas.

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------------
-- Esquemas (D23). `public` conserva solo extensiones y funciones auxiliares.
-- ---------------------------------------------------------------------------

CREATE SCHEMA provenance;
CREATE SCHEMA transit;
CREATE SCHEMA realtime;
CREATE SCHEMA community;

COMMENT ON SCHEMA provenance IS 'Fuentes, registros originales e incidencias de datos';
COMMENT ON SCHEMA transit IS 'Red de transporte y servicio programado (modelo compatible con GTFS)';
COMMENT ON SCHEMA realtime IS 'Observaciones, alertas y predicciones';
COMMENT ON SCHEMA community IS 'Reportes de la comunidad';

-- ---------------------------------------------------------------------------
-- Funciones auxiliares
-- ---------------------------------------------------------------------------

-- D1: identificadores de la red con formato <agencia>:<tipo>:<código>.
CREATE FUNCTION public.rutagt_is_entity_id(value text, kind text)
RETURNS boolean
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
RETURN value ~ ('^[a-z0-9]+(-[a-z0-9]+)*:' || kind || ':[A-Za-z0-9][A-Za-z0-9._-]*$');

COMMENT ON FUNCTION public.rutagt_is_entity_id(text, text)
  IS 'Valida identificadores <agencia>:<tipo>:<código> (ADR-0029)';

-- D13: mantiene updated_at en cada actualización.
CREATE FUNCTION public.rutagt_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- D12: distancia en metros sobre el elipsoide para geometrías EPSG:4326.
CREATE FUNCTION public.rutagt_distance_m(a geometry, b geometry)
RETURNS double precision
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
RETURN public.ST_Distance(a::public.geography, b::public.geography);

COMMENT ON FUNCTION public.rutagt_distance_m(geometry, geometry)
  IS 'Distancia en metros entre geometrías EPSG:4326 (ADR-0029)';

-- ---------------------------------------------------------------------------
-- Tipos enumerados (D24): solo conjuntos estables propios del proyecto.
-- ---------------------------------------------------------------------------

CREATE TYPE provenance.source_kind AS ENUM (
  'official_open_data', 'official_request', 'operator_partnership',
  'commercial_api', 'openstreetmap', 'field_survey', 'community_report'
);
CREATE TYPE provenance.issue_status AS ENUM ('open', 'confirmed', 'resolved', 'dismissed');
CREATE TYPE transit.record_status AS ENUM ('planned', 'active', 'suspended', 'retired', 'unknown');
CREATE TYPE transit.observation_quality AS ENUM ('official', 'verified', 'probable', 'unverified');

-- ---------------------------------------------------------------------------
-- provenance
-- ---------------------------------------------------------------------------

CREATE TABLE provenance.data_source (
  source_id              text PRIMARY KEY CHECK (source_id ~ '^[a-z0-9]+(_[a-z0-9]+)*$'),
  name                   text NOT NULL,
  authority              text,
  source_kind            provenance.source_kind NOT NULL,
  source_url             text,
  license_name           text,
  license_url            text,
  attribution            text,
  attribution_url        text,                                        -- D18
  refresh_interval       interval,
  fetched_at             timestamptz,
  valid_from             timestamptz,
  valid_to               timestamptz,
  sha256                 text CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  metadata               jsonb NOT NULL DEFAULT '{}',
  loaded_by_run          text,                                        -- D14
  created_at             timestamptz NOT NULL DEFAULT now(),          -- D13
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_to >= valid_from)                  -- D9
);

CREATE TABLE provenance.source_record (
  source_record_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id              text NOT NULL REFERENCES provenance.data_source ON DELETE RESTRICT,
  external_id            text,
  entity_type            text NOT NULL,
  fetched_at             timestamptz NOT NULL,
  checksum               text,
  raw_payload            jsonb NOT NULL,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id, checksum)
);

-- D22: discrepancias entre fuentes, con evidencia.
CREATE TABLE provenance.data_issue (
  data_issue_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entity_type            text NOT NULL,
  entity_id              text NOT NULL,
  issue_type             text NOT NULL,
  description            text NOT NULL,
  source_id              text NOT NULL REFERENCES provenance.data_source ON DELETE RESTRICT,
  compared_source_id     text REFERENCES provenance.data_source ON DELETE RESTRICT,
  status                 provenance.issue_status NOT NULL DEFAULT 'open',
  evidence               jsonb NOT NULL DEFAULT '{}',
  detected_at            timestamptz NOT NULL DEFAULT now(),
  resolved_at            timestamptz,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (resolved_at IS NULL OR resolved_at >= detected_at)
);

CREATE INDEX data_issue_entity_idx ON provenance.data_issue (entity_type, entity_id);
CREATE INDEX data_issue_source_id_idx ON provenance.data_issue (source_id);
CREATE INDEX data_issue_compared_source_id_idx ON provenance.data_issue (compared_source_id);

-- ---------------------------------------------------------------------------
-- transit: catálogo
-- ---------------------------------------------------------------------------

CREATE TABLE transit.agency (
  agency_id              text PRIMARY KEY CHECK (agency_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  agency_name            text NOT NULL,
  public_brand           text,
  operator_legal_name    text,
  regulator_name         text,
  agency_url             text,
  agency_phone           text,
  agency_email           text,
  agency_timezone        text NOT NULL DEFAULT 'America/Guatemala',
  agency_lang            text NOT NULL DEFAULT 'es',
  municipality           text,
  logo_url               text,
  status                 transit.record_status NOT NULL DEFAULT 'unknown',
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  source_record_id       bigint REFERENCES provenance.source_record ON DELETE RESTRICT,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX agency_source_id_idx ON transit.agency (source_id);
CREATE INDEX agency_source_record_id_idx ON transit.agency (source_record_id);

CREATE TABLE transit.route (
  route_id               text PRIMARY KEY CHECK (public.rutagt_is_entity_id(route_id, 'route')),
  agency_id              text NOT NULL REFERENCES transit.agency ON DELETE RESTRICT,
  official_code          text,
  route_short_name       text,
  route_long_name        text,
  route_desc             text,
  -- D6: tipos básicos y extendidos de GTFS; 3 = autobús.
  route_type             smallint NOT NULL DEFAULT 3
                         CHECK (route_type IN (0, 1, 2, 3, 4, 5, 6, 7, 11, 12)
                                OR route_type BETWEEN 100 AND 1799),
  system_name            text,
  route_color            text CHECK (route_color ~ '^[0-9A-Fa-f]{6}$'),       -- D5
  route_text_color       text CHECK (route_text_color ~ '^[0-9A-Fa-f]{6}$'),
  public_vehicle_color   text,
  origin_name            text,
  destination_name       text,
  status                 transit.record_status NOT NULL DEFAULT 'unknown',
  valid_from             date,
  valid_to               date,
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  source_record_id       bigint REFERENCES provenance.source_record ON DELETE RESTRICT,
  attributes             jsonb NOT NULL DEFAULT '{}',
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE INDEX route_agency_id_idx ON transit.route (agency_id);
CREATE INDEX route_official_code_idx ON transit.route (official_code);
CREATE INDEX route_source_id_idx ON transit.route (source_id);
CREATE INDEX route_source_record_id_idx ON transit.route (source_record_id);

-- D16: un trazado continuo por patrón.
CREATE TABLE transit.shape (
  shape_id               text PRIMARY KEY CHECK (public.rutagt_is_entity_id(shape_id, 'shape')),
  geom                   geometry(LineString, 4326) NOT NULL,
  distance_m             numeric(12,2) CHECK (distance_m >= 0),
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  source_record_id       bigint REFERENCES provenance.source_record ON DELETE RESTRICT,
  valid_from             date,
  valid_to               date,
  quality                transit.observation_quality NOT NULL DEFAULT 'unverified',
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE INDEX shape_geom_gix ON transit.shape USING gist (geom);
CREATE INDEX shape_source_id_idx ON transit.shape (source_id);
CREATE INDEX shape_source_record_id_idx ON transit.shape (source_record_id);

CREATE TABLE transit.route_pattern (
  pattern_id             text PRIMARY KEY CHECK (public.rutagt_is_entity_id(pattern_id, 'pattern')),
  route_id               text NOT NULL REFERENCES transit.route ON DELETE RESTRICT,
  shape_id               text REFERENCES transit.shape ON DELETE RESTRICT,
  direction_id           smallint CHECK (direction_id IN (0, 1)),
  headsign               text,
  variant_name           text,
  service_type           text,
  is_express             boolean NOT NULL DEFAULT false,
  wheelchair_accessible  boolean,
  bikes_allowed          boolean,
  status                 transit.record_status NOT NULL DEFAULT 'unknown',
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  attributes             jsonb NOT NULL DEFAULT '{}',
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX route_pattern_route_id_idx ON transit.route_pattern (route_id);
CREATE INDEX route_pattern_shape_id_idx ON transit.route_pattern (shape_id);
CREATE INDEX route_pattern_source_id_idx ON transit.route_pattern (source_id);

CREATE TABLE transit.stop (
  stop_id                text PRIMARY KEY CHECK (public.rutagt_is_entity_id(stop_id, 'stop')),
  stop_code              text,
  stop_name              text NOT NULL,
  stop_desc              text,
  -- D15: 0 parada, 1 estación, 2 entrada o salida, 3 nodo genérico, 4 área de abordaje.
  location_type          smallint NOT NULL DEFAULT 0 CHECK (location_type BETWEEN 0 AND 4),
  location               geometry(Point, 4326),
  address                text,
  zone                   text,
  municipality           text,
  landmark               text,
  parent_station_id      text REFERENCES transit.stop ON DELETE RESTRICT,
  platform_code          text,
  direction_hint         text,
  side_of_road           text,
  wheelchair_boarding    smallint CHECK (wheelchair_boarding IN (0, 1, 2)),
  shelter                boolean,
  lighting               boolean,
  security_notes         text,
  photo_url              text,
  status                 transit.record_status NOT NULL DEFAULT 'unknown',
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  source_record_id       bigint REFERENCES provenance.source_record ON DELETE RESTRICT,
  location_quality       transit.observation_quality NOT NULL DEFAULT 'unverified',  -- D21
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  -- GTFS: ubicación obligatoria para paradas, estaciones y entradas.
  CHECK (location IS NOT NULL OR location_type IN (3, 4)),
  -- GTFS: las estaciones no tienen padre; entradas, nodos y áreas sí.
  CHECK (CASE location_type
           WHEN 0 THEN true
           WHEN 1 THEN parent_station_id IS NULL
           ELSE parent_station_id IS NOT NULL
         END)
);

CREATE INDEX stop_location_gix ON transit.stop USING gist (location);
CREATE INDEX stop_name_idx ON transit.stop (lower(stop_name));
CREATE INDEX stop_parent_station_id_idx ON transit.stop (parent_station_id);
CREATE INDEX stop_source_id_idx ON transit.stop (source_id);
CREATE INDEX stop_source_record_id_idx ON transit.stop (source_record_id);

-- D2: sin UNIQUE redundante; una parada puede repetirse en un circuito.
CREATE TABLE transit.pattern_stop (
  pattern_id             text NOT NULL REFERENCES transit.route_pattern ON DELETE CASCADE,
  stop_id                text NOT NULL REFERENCES transit.stop ON DELETE RESTRICT,
  stop_sequence          integer NOT NULL CHECK (stop_sequence > 0),
  pickup_type            smallint NOT NULL DEFAULT 0 CHECK (pickup_type BETWEEN 0 AND 3),
  drop_off_type          smallint NOT NULL DEFAULT 0 CHECK (drop_off_type BETWEEN 0 AND 3),
  timepoint              boolean NOT NULL DEFAULT false,
  shape_dist_traveled_m  numeric(12,2) CHECK (shape_dist_traveled_m >= 0),
  min_dwell_seconds      integer CHECK (min_dwell_seconds >= 0),
  sequence_quality       transit.observation_quality NOT NULL DEFAULT 'unverified',  -- D21
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (pattern_id, stop_sequence)
);

CREATE INDEX pattern_stop_stop_id_idx ON transit.pattern_stop (stop_id);

-- ---------------------------------------------------------------------------
-- transit: servicio
-- ---------------------------------------------------------------------------

CREATE TABLE transit.service_calendar (
  service_id             text PRIMARY KEY CHECK (public.rutagt_is_entity_id(service_id, 'service')),
  monday                 boolean NOT NULL,
  tuesday                boolean NOT NULL,
  wednesday              boolean NOT NULL,
  thursday               boolean NOT NULL,
  friday                 boolean NOT NULL,
  saturday               boolean NOT NULL,
  sunday                 boolean NOT NULL,
  start_date             date NOT NULL,
  end_date               date NOT NULL,
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (end_date >= start_date),
  CHECK (monday OR tuesday OR wednesday OR thursday OR friday OR saturday OR sunday)  -- D8
);

CREATE INDEX service_calendar_source_id_idx ON transit.service_calendar (source_id);

CREATE TABLE transit.service_exception (
  service_id             text NOT NULL REFERENCES transit.service_calendar ON DELETE CASCADE,
  service_date           date NOT NULL,
  exception_type         smallint NOT NULL CHECK (exception_type IN (1, 2)),
  reason                 text,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (service_id, service_date)
);

-- D20: sentido y trazado se derivan del patrón al exportar.
CREATE TABLE transit.trip (
  trip_id                text PRIMARY KEY CHECK (public.rutagt_is_entity_id(trip_id, 'trip')),
  route_id               text NOT NULL REFERENCES transit.route ON DELETE RESTRICT,
  pattern_id             text NOT NULL REFERENCES transit.route_pattern ON DELETE RESTRICT,
  service_id             text NOT NULL REFERENCES transit.service_calendar ON DELETE RESTRICT,
  trip_headsign          text,
  block_id               text,
  wheelchair_accessible  smallint CHECK (wheelchair_accessible IN (0, 1, 2)),
  bikes_allowed          smallint CHECK (bikes_allowed IN (0, 1, 2)),
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX trip_route_id_idx ON transit.trip (route_id);
CREATE INDEX trip_pattern_id_idx ON transit.trip (pattern_id);
CREATE INDEX trip_service_id_idx ON transit.trip (service_id);
CREATE INDEX trip_source_id_idx ON transit.trip (source_id);

CREATE TABLE transit.stop_time (
  trip_id                text NOT NULL REFERENCES transit.trip ON DELETE CASCADE,
  stop_id                text NOT NULL REFERENCES transit.stop ON DELETE RESTRICT,
  stop_sequence          integer NOT NULL CHECK (stop_sequence > 0),
  arrival_seconds        integer CHECK (arrival_seconds >= 0),                      -- D7
  departure_seconds      integer CHECK (departure_seconds >= 0),
  pickup_type            smallint NOT NULL DEFAULT 0 CHECK (pickup_type BETWEEN 0 AND 3),
  drop_off_type          smallint NOT NULL DEFAULT 0 CHECK (drop_off_type BETWEEN 0 AND 3),
  timepoint              boolean NOT NULL DEFAULT false,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (trip_id, stop_sequence),
  CHECK (departure_seconds >= arrival_seconds)
);

CREATE INDEX stop_time_stop_idx ON transit.stop_time (stop_id, arrival_seconds);

CREATE TABLE transit.frequency (
  frequency_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  trip_id                text NOT NULL REFERENCES transit.trip ON DELETE CASCADE,
  start_seconds          integer NOT NULL CHECK (start_seconds >= 0),
  end_seconds            integer NOT NULL,
  headway_seconds        integer NOT NULL CHECK (headway_seconds > 0),
  exact_times            boolean NOT NULL DEFAULT false,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (end_seconds > start_seconds)
);

CREATE INDEX frequency_trip_id_idx ON transit.frequency (trip_id);

-- D19: modelo interno de tarifas; su correspondencia con GTFS Fares v2 se define en RGT-51.
CREATE TABLE transit.fare_product (
  fare_product_id        text PRIMARY KEY CHECK (public.rutagt_is_entity_id(fare_product_id, 'fare')),
  agency_id              text REFERENCES transit.agency ON DELETE RESTRICT,
  name                   text NOT NULL,
  amount                 numeric(10,2) NOT NULL CHECK (amount >= 0),
  currency               char(3) NOT NULL DEFAULT 'GTQ' CHECK (currency ~ '^[A-Z]{3}$'),
  payment_media          text,
  rider_category         text,
  transfer_count         integer CHECK (transfer_count >= 0),
  transfer_duration_s    integer CHECK (transfer_duration_s >= 0),
  valid_from             date,
  valid_to               date,
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE INDEX fare_product_agency_id_idx ON transit.fare_product (agency_id);
CREATE INDEX fare_product_source_id_idx ON transit.fare_product (source_id);

CREATE TABLE transit.fare_rule (
  fare_rule_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fare_product_id        text NOT NULL REFERENCES transit.fare_product ON DELETE RESTRICT,
  route_id               text REFERENCES transit.route ON DELETE RESTRICT,
  origin_zone            text,
  destination_zone       text,
  min_distance_m         numeric(12,2) CHECK (min_distance_m >= 0),
  max_distance_m         numeric(12,2),
  start_time_seconds     integer,
  end_time_seconds       integer,
  priority               integer NOT NULL DEFAULT 0,
  conditions             jsonb NOT NULL DEFAULT '{}',
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (max_distance_m >= min_distance_m)                                           -- D10
);

CREATE INDEX fare_rule_fare_product_id_idx ON transit.fare_rule (fare_product_id);
CREATE INDEX fare_rule_route_id_idx ON transit.fare_rule (route_id);

CREATE TABLE transit.transfer (
  from_stop_id           text NOT NULL REFERENCES transit.stop ON DELETE RESTRICT,
  to_stop_id             text NOT NULL REFERENCES transit.stop ON DELETE RESTRICT,
  transfer_type          smallint NOT NULL DEFAULT 2 CHECK (transfer_type BETWEEN 0 AND 5),  -- D10
  min_transfer_seconds   integer CHECK (min_transfer_seconds >= 0),
  walking_distance_m     numeric(10,2) CHECK (walking_distance_m >= 0),
  walking_geom           geometry(LineString, 4326),
  wheelchair_accessible  boolean,
  notes                  text,
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (from_stop_id, to_stop_id)
);

CREATE INDEX transfer_geom_gix ON transit.transfer USING gist (walking_geom);
CREATE INDEX transfer_to_stop_id_idx ON transit.transfer (to_stop_id);
CREATE INDEX transfer_source_id_idx ON transit.transfer (source_id);

CREATE TABLE transit.vehicle (
  vehicle_id             text PRIMARY KEY CHECK (public.rutagt_is_entity_id(vehicle_id, 'vehicle')),
  agency_id              text NOT NULL REFERENCES transit.agency ON DELETE RESTRICT,
  public_label           text,
  license_plate          text,
  livery_color           text,
  vehicle_type           text,
  capacity_seated        integer CHECK (capacity_seated >= 0),
  capacity_total         integer CHECK (capacity_total >= 0),
  wheelchair_accessible  boolean,
  status                 transit.record_status NOT NULL DEFAULT 'unknown',
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  attributes             jsonb NOT NULL DEFAULT '{}',
  loaded_by_run          text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX vehicle_agency_id_idx ON transit.vehicle (agency_id);
CREATE INDEX vehicle_source_id_idx ON transit.vehicle (source_id);

-- D17: versiones publicadas del feed GTFS (feed_info.txt).
CREATE TABLE transit.feed_version (
  feed_version_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  feed_version           text NOT NULL UNIQUE,
  feed_publisher_name    text NOT NULL,
  feed_publisher_url     text NOT NULL,
  feed_lang              text NOT NULL DEFAULT 'es',
  default_lang           text,
  feed_start_date        date,
  feed_end_date          date,
  feed_contact_email     text,
  feed_contact_url       text,
  sha256                 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  published_at           timestamptz,
  created_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (feed_end_date IS NULL OR feed_end_date >= feed_start_date)
);

-- ---------------------------------------------------------------------------
-- realtime (D3: particionamiento por tiempo cuando exista ingesta, épica RGT-9)
-- ---------------------------------------------------------------------------

CREATE TABLE realtime.vehicle_position (
  vehicle_position_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  vehicle_id             text REFERENCES transit.vehicle ON DELETE RESTRICT,
  trip_id                text REFERENCES transit.trip ON DELETE RESTRICT,
  observed_at            timestamptz NOT NULL,
  location               geometry(Point, 4326) NOT NULL,
  bearing                numeric(6,2) CHECK (bearing >= 0 AND bearing < 360),
  speed_mps              numeric(8,3) CHECK (speed_mps >= 0),
  current_stop_id        text REFERENCES transit.stop ON DELETE RESTRICT,
  current_status         text,
  occupancy_status       text,
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  raw_payload            jsonb NOT NULL DEFAULT '{}',
  created_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX vehicle_position_time_idx ON realtime.vehicle_position (observed_at DESC);
CREATE INDEX vehicle_position_location_gix ON realtime.vehicle_position USING gist (location);
CREATE INDEX vehicle_position_vehicle_id_idx ON realtime.vehicle_position (vehicle_id);
CREATE INDEX vehicle_position_trip_id_idx ON realtime.vehicle_position (trip_id);
CREATE INDEX vehicle_position_current_stop_id_idx ON realtime.vehicle_position (current_stop_id);
CREATE INDEX vehicle_position_source_id_idx ON realtime.vehicle_position (source_id);

CREATE TABLE realtime.stop_event (
  stop_event_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  vehicle_id             text REFERENCES transit.vehicle ON DELETE RESTRICT,
  trip_id                text REFERENCES transit.trip ON DELETE RESTRICT,
  stop_id                text NOT NULL REFERENCES transit.stop ON DELETE RESTRICT,
  event_type             text NOT NULL CHECK (event_type IN ('arrival', 'departure', 'pass')),
  scheduled_at           timestamptz,
  observed_at            timestamptz NOT NULL,
  delay_seconds          integer,
  dwell_seconds          integer CHECK (dwell_seconds >= 0),
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  created_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX stop_event_model_idx ON realtime.stop_event (stop_id, observed_at DESC);
CREATE INDEX stop_event_vehicle_id_idx ON realtime.stop_event (vehicle_id);
CREATE INDEX stop_event_trip_id_idx ON realtime.stop_event (trip_id);
CREATE INDEX stop_event_source_id_idx ON realtime.stop_event (source_id);

CREATE TABLE realtime.service_alert (
  alert_id               text PRIMARY KEY CHECK (public.rutagt_is_entity_id(alert_id, 'alert')),
  agency_id              text REFERENCES transit.agency ON DELETE RESTRICT,
  route_id               text REFERENCES transit.route ON DELETE RESTRICT,
  stop_id                text REFERENCES transit.stop ON DELETE RESTRICT,
  effect                 text,
  cause                  text,
  header                 text NOT NULL,
  description            text,
  active_from            timestamptz,
  active_to              timestamptz,
  source_url             text,
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (active_to IS NULL OR active_to >= active_from)
);

CREATE INDEX service_alert_agency_id_idx ON realtime.service_alert (agency_id);
CREATE INDEX service_alert_route_id_idx ON realtime.service_alert (route_id);
CREATE INDEX service_alert_stop_id_idx ON realtime.service_alert (stop_id);
CREATE INDEX service_alert_source_id_idx ON realtime.service_alert (source_id);

CREATE TABLE realtime.traffic_observation (
  traffic_observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  observed_at            timestamptz NOT NULL,
  road_segment_id        text,
  geom                   geometry(LineString, 4326),
  speed_kph              numeric(7,2) CHECK (speed_kph >= 0),
  congestion_level       text,
  incident_type          text,
  source_id              text REFERENCES provenance.data_source ON DELETE RESTRICT,
  attributes             jsonb NOT NULL DEFAULT '{}',
  created_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX traffic_observation_time_idx ON realtime.traffic_observation (observed_at DESC);
CREATE INDEX traffic_observation_geom_gix ON realtime.traffic_observation USING gist (geom);
CREATE INDEX traffic_observation_source_id_idx ON realtime.traffic_observation (source_id);

CREATE TABLE realtime.eta_prediction (
  eta_prediction_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  generated_at           timestamptz NOT NULL,
  trip_id                text REFERENCES transit.trip ON DELETE RESTRICT,
  stop_id                text NOT NULL REFERENCES transit.stop ON DELETE RESTRICT,
  predicted_arrival      timestamptz NOT NULL,
  p50_seconds            integer,
  p90_seconds            integer,
  model_version          text NOT NULL,
  features               jsonb NOT NULL DEFAULT '{}',
  created_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (p90_seconds >= p50_seconds)
);

CREATE INDEX eta_prediction_lookup_idx
  ON realtime.eta_prediction (stop_id, generated_at DESC, predicted_arrival);
CREATE INDEX eta_prediction_trip_id_idx ON realtime.eta_prediction (trip_id);

-- ---------------------------------------------------------------------------
-- community
-- ---------------------------------------------------------------------------

CREATE TABLE community.community_report (
  report_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_type            text NOT NULL,
  route_id               text REFERENCES transit.route ON DELETE RESTRICT,
  stop_id                text REFERENCES transit.stop ON DELETE RESTRICT,
  vehicle_id             text REFERENCES transit.vehicle ON DELETE RESTRICT,
  location               geometry(Point, 4326),
  reported_at            timestamptz NOT NULL,
  expires_at             timestamptz,
  description            text,
  evidence_url           text,
  moderation_status      text NOT NULL DEFAULT 'pending',
  verification_count     integer NOT NULL DEFAULT 0 CHECK (verification_count >= 0),
  reporter_hash          text,
  attributes             jsonb NOT NULL DEFAULT '{}',
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (expires_at IS NULL OR expires_at >= reported_at)
);

CREATE INDEX community_report_location_gix ON community.community_report USING gist (location);
CREATE INDEX community_report_active_idx ON community.community_report (moderation_status, expires_at);
CREATE INDEX community_report_route_id_idx ON community.community_report (route_id);
CREATE INDEX community_report_stop_id_idx ON community.community_report (stop_id);
CREATE INDEX community_report_vehicle_id_idx ON community.community_report (vehicle_id);

-- ---------------------------------------------------------------------------
-- D13: trigger de updated_at en toda tabla que tenga la columna.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
  t record;
BEGIN
  FOR t IN
    SELECT table_schema, table_name
    FROM information_schema.columns
    WHERE column_name = 'updated_at'
      AND table_schema IN ('provenance', 'transit', 'realtime', 'community')
  LOOP
    EXECUTE format(
      'CREATE TRIGGER set_updated_at BEFORE UPDATE ON %I.%I '
      'FOR EACH ROW EXECUTE FUNCTION public.rutagt_set_updated_at()',
      t.table_schema, t.table_name
    );
  END LOOP;
END;
$$;
