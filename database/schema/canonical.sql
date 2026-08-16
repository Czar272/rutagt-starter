-- Esquema canónico inicial de RutaGT (PostgreSQL 16 + PostGIS 3).
-- GTFS sigue siendo el formato de intercambio; estas tablas permiten además
-- procedencia, datos incompletos, observaciones reales y predicciones.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TYPE source_kind AS ENUM (
  'official_open_data', 'official_request', 'operator_partnership',
  'commercial_api', 'openstreetmap', 'field_survey', 'community_report'
);

CREATE TYPE record_status AS ENUM ('planned', 'active', 'suspended', 'retired', 'unknown');
CREATE TYPE observation_quality AS ENUM ('official', 'verified', 'probable', 'unverified');

CREATE TABLE data_source (
  source_id              text PRIMARY KEY,
  name                   text NOT NULL,
  authority              text,
  source_kind            source_kind NOT NULL,
  source_url             text,
  license_name           text,
  license_url            text,
  attribution            text,
  refresh_interval       interval,
  fetched_at             timestamptz,
  valid_from             timestamptz,
  valid_to               timestamptz,
  sha256                 text,
  metadata               jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE source_record (
  source_record_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id              text NOT NULL REFERENCES data_source(source_id),
  external_id            text,
  entity_type            text NOT NULL,
  fetched_at             timestamptz NOT NULL,
  checksum               text,
  raw_payload            jsonb NOT NULL,
  UNIQUE (source_id, external_id, checksum)
);

CREATE TABLE agency (
  agency_id              text PRIMARY KEY,
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
  status                 record_status NOT NULL DEFAULT 'unknown',
  source_id              text REFERENCES data_source(source_id),
  source_record_id       bigint REFERENCES source_record(source_record_id),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE route (
  route_id               text PRIMARY KEY,
  agency_id              text NOT NULL REFERENCES agency(agency_id),
  official_code          text,
  route_short_name       text,
  route_long_name        text,
  route_desc             text,
  mode                   text NOT NULL DEFAULT 'bus',
  system_name            text,
  route_color            char(6),
  route_text_color       char(6),
  public_vehicle_color   text,
  origin_name            text,
  destination_name       text,
  status                 record_status NOT NULL DEFAULT 'unknown',
  valid_from             date,
  valid_to               date,
  source_id              text REFERENCES data_source(source_id),
  source_record_id       bigint REFERENCES source_record(source_record_id),
  attributes             jsonb NOT NULL DEFAULT '{}',
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX route_official_code_idx ON route (official_code);
CREATE INDEX route_agency_idx ON route (agency_id);

CREATE TABLE shape (
  shape_id               text PRIMARY KEY,
  geom                   geometry(MultiLineString, 4326) NOT NULL,
  distance_m             numeric(12,2),
  source_id              text REFERENCES data_source(source_id),
  source_record_id       bigint REFERENCES source_record(source_record_id),
  valid_from             date,
  valid_to               date,
  quality                observation_quality NOT NULL DEFAULT 'unverified'
);

CREATE INDEX shape_geom_gix ON shape USING gist (geom);

CREATE TABLE route_pattern (
  pattern_id             text PRIMARY KEY,
  route_id               text NOT NULL REFERENCES route(route_id),
  shape_id               text REFERENCES shape(shape_id),
  direction_id           smallint CHECK (direction_id IN (0, 1)),
  headsign               text,
  variant_name           text,
  service_type           text,
  is_express             boolean NOT NULL DEFAULT false,
  wheelchair_accessible  boolean,
  bikes_allowed          boolean,
  status                 record_status NOT NULL DEFAULT 'unknown',
  source_id              text REFERENCES data_source(source_id),
  attributes             jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE stop (
  stop_id                text PRIMARY KEY,
  stop_code              text,
  stop_name              text NOT NULL,
  stop_desc              text,
  location               geometry(Point, 4326) NOT NULL,
  address                text,
  zone                   text,
  municipality           text,
  landmark               text,
  parent_station_id      text REFERENCES stop(stop_id),
  platform_code          text,
  direction_hint         text,
  side_of_road           text,
  wheelchair_boarding    smallint CHECK (wheelchair_boarding IN (0, 1, 2)),
  shelter                boolean,
  lighting               boolean,
  security_notes         text,
  photo_url              text,
  status                 record_status NOT NULL DEFAULT 'unknown',
  source_id              text REFERENCES data_source(source_id),
  source_record_id       bigint REFERENCES source_record(source_record_id),
  quality                observation_quality NOT NULL DEFAULT 'unverified',
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX stop_location_gix ON stop USING gist (location);
CREATE INDEX stop_name_idx ON stop (lower(stop_name));

CREATE TABLE pattern_stop (
  pattern_id             text NOT NULL REFERENCES route_pattern(pattern_id) ON DELETE CASCADE,
  stop_id                text NOT NULL REFERENCES stop(stop_id),
  stop_sequence          integer NOT NULL CHECK (stop_sequence > 0),
  pickup_type            smallint NOT NULL DEFAULT 0,
  drop_off_type          smallint NOT NULL DEFAULT 0,
  timepoint              boolean NOT NULL DEFAULT false,
  shape_dist_traveled_m  numeric(12,2),
  min_dwell_seconds      integer,
  PRIMARY KEY (pattern_id, stop_sequence),
  UNIQUE (pattern_id, stop_id, stop_sequence)
);

CREATE TABLE service_calendar (
  service_id             text PRIMARY KEY,
  monday                 boolean NOT NULL,
  tuesday                boolean NOT NULL,
  wednesday              boolean NOT NULL,
  thursday               boolean NOT NULL,
  friday                 boolean NOT NULL,
  saturday               boolean NOT NULL,
  sunday                 boolean NOT NULL,
  start_date             date NOT NULL,
  end_date               date NOT NULL CHECK (end_date >= start_date),
  source_id              text REFERENCES data_source(source_id)
);

CREATE TABLE service_exception (
  service_id             text NOT NULL REFERENCES service_calendar(service_id) ON DELETE CASCADE,
  service_date           date NOT NULL,
  exception_type         smallint NOT NULL CHECK (exception_type IN (1, 2)),
  reason                 text,
  PRIMARY KEY (service_id, service_date)
);

CREATE TABLE trip (
  trip_id                text PRIMARY KEY,
  route_id               text NOT NULL REFERENCES route(route_id),
  pattern_id             text NOT NULL REFERENCES route_pattern(pattern_id),
  service_id             text NOT NULL REFERENCES service_calendar(service_id),
  trip_headsign          text,
  block_id               text,
  wheelchair_accessible  smallint CHECK (wheelchair_accessible IN (0, 1, 2)),
  bikes_allowed          smallint CHECK (bikes_allowed IN (0, 1, 2)),
  source_id              text REFERENCES data_source(source_id)
);

CREATE TABLE stop_time (
  trip_id                text NOT NULL REFERENCES trip(trip_id) ON DELETE CASCADE,
  stop_id                text NOT NULL REFERENCES stop(stop_id),
  stop_sequence          integer NOT NULL CHECK (stop_sequence > 0),
  arrival_seconds        integer,
  departure_seconds      integer,
  pickup_type            smallint NOT NULL DEFAULT 0,
  drop_off_type          smallint NOT NULL DEFAULT 0,
  timepoint              boolean NOT NULL DEFAULT false,
  PRIMARY KEY (trip_id, stop_sequence)
);

CREATE INDEX stop_time_stop_idx ON stop_time (stop_id, arrival_seconds);

CREATE TABLE frequency (
  frequency_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  trip_id                text NOT NULL REFERENCES trip(trip_id) ON DELETE CASCADE,
  start_seconds          integer NOT NULL,
  end_seconds            integer NOT NULL,
  headway_seconds        integer NOT NULL CHECK (headway_seconds > 0),
  exact_times            boolean NOT NULL DEFAULT false,
  CHECK (end_seconds > start_seconds)
);

CREATE TABLE fare_product (
  fare_product_id        text PRIMARY KEY,
  agency_id              text REFERENCES agency(agency_id),
  name                   text NOT NULL,
  amount                 numeric(10,2) NOT NULL CHECK (amount >= 0),
  currency               char(3) NOT NULL DEFAULT 'GTQ',
  payment_media          text,
  rider_category         text,
  transfer_count         integer,
  transfer_duration_s    integer,
  valid_from             date,
  valid_to               date,
  source_id              text REFERENCES data_source(source_id)
);

CREATE TABLE fare_rule (
  fare_rule_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fare_product_id        text NOT NULL REFERENCES fare_product(fare_product_id),
  route_id               text REFERENCES route(route_id),
  origin_zone            text,
  destination_zone       text,
  min_distance_m         numeric(12,2),
  max_distance_m         numeric(12,2),
  start_time_seconds     integer,
  end_time_seconds       integer,
  priority               integer NOT NULL DEFAULT 0,
  conditions             jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE transfer (
  from_stop_id           text NOT NULL REFERENCES stop(stop_id),
  to_stop_id             text NOT NULL REFERENCES stop(stop_id),
  transfer_type          smallint NOT NULL DEFAULT 2,
  min_transfer_seconds   integer,
  walking_distance_m     numeric(10,2),
  walking_geom           geometry(LineString, 4326),
  wheelchair_accessible  boolean,
  notes                  text,
  source_id              text REFERENCES data_source(source_id),
  PRIMARY KEY (from_stop_id, to_stop_id)
);

CREATE INDEX transfer_geom_gix ON transfer USING gist (walking_geom);

CREATE TABLE vehicle (
  vehicle_id             text PRIMARY KEY,
  agency_id              text NOT NULL REFERENCES agency(agency_id),
  public_label           text,
  license_plate          text,
  livery_color           text,
  vehicle_type           text,
  capacity_seated        integer,
  capacity_total         integer,
  wheelchair_accessible  boolean,
  status                 record_status NOT NULL DEFAULT 'unknown',
  source_id              text REFERENCES data_source(source_id),
  attributes             jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE vehicle_position (
  vehicle_position_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  vehicle_id             text REFERENCES vehicle(vehicle_id),
  trip_id                text REFERENCES trip(trip_id),
  observed_at            timestamptz NOT NULL,
  location               geometry(Point, 4326) NOT NULL,
  bearing                numeric(6,2),
  speed_mps              numeric(8,3),
  current_stop_id        text REFERENCES stop(stop_id),
  current_status         text,
  occupancy_status       text,
  source_id              text REFERENCES data_source(source_id),
  raw_payload            jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX vehicle_position_time_idx ON vehicle_position (observed_at DESC);
CREATE INDEX vehicle_position_location_gix ON vehicle_position USING gist (location);

CREATE TABLE stop_event (
  stop_event_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  vehicle_id             text REFERENCES vehicle(vehicle_id),
  trip_id                text REFERENCES trip(trip_id),
  stop_id                text NOT NULL REFERENCES stop(stop_id),
  event_type             text NOT NULL CHECK (event_type IN ('arrival', 'departure', 'pass')),
  scheduled_at           timestamptz,
  observed_at            timestamptz NOT NULL,
  delay_seconds          integer,
  dwell_seconds          integer,
  source_id              text REFERENCES data_source(source_id)
);

CREATE INDEX stop_event_model_idx ON stop_event (stop_id, observed_at DESC);

CREATE TABLE service_alert (
  alert_id               text PRIMARY KEY,
  agency_id              text REFERENCES agency(agency_id),
  route_id               text REFERENCES route(route_id),
  stop_id                text REFERENCES stop(stop_id),
  effect                 text,
  cause                  text,
  header                 text NOT NULL,
  description            text,
  active_from            timestamptz,
  active_to              timestamptz,
  source_url             text,
  source_id              text REFERENCES data_source(source_id),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE traffic_observation (
  traffic_observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  observed_at            timestamptz NOT NULL,
  road_segment_id        text,
  geom                   geometry(LineString, 4326),
  speed_kph              numeric(7,2),
  congestion_level       text,
  incident_type          text,
  source_id              text REFERENCES data_source(source_id),
  attributes             jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX traffic_observation_time_idx ON traffic_observation (observed_at DESC);
CREATE INDEX traffic_observation_geom_gix ON traffic_observation USING gist (geom);

CREATE TABLE eta_prediction (
  eta_prediction_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  generated_at           timestamptz NOT NULL,
  trip_id                text REFERENCES trip(trip_id),
  stop_id                text NOT NULL REFERENCES stop(stop_id),
  predicted_arrival      timestamptz NOT NULL,
  p50_seconds            integer,
  p90_seconds            integer,
  model_version          text NOT NULL,
  features               jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX eta_prediction_lookup_idx
  ON eta_prediction (stop_id, generated_at DESC, predicted_arrival);

CREATE TABLE community_report (
  report_id              uuid PRIMARY KEY,
  report_type            text NOT NULL,
  route_id               text REFERENCES route(route_id),
  stop_id                text REFERENCES stop(stop_id),
  vehicle_id             text REFERENCES vehicle(vehicle_id),
  location               geometry(Point, 4326),
  reported_at            timestamptz NOT NULL,
  expires_at             timestamptz,
  description            text,
  evidence_url           text,
  moderation_status      text NOT NULL DEFAULT 'pending',
  verification_count     integer NOT NULL DEFAULT 0,
  reporter_hash          text,
  attributes             jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX community_report_location_gix ON community_report USING gist (location);
CREATE INDEX community_report_active_idx ON community_report (moderation_status, expires_at);
