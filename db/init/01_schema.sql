-- Esquema del Gemelo Digital Estructural
-- PostgreSQL + PostGIS (huellas) + TimescaleDB (series de rigidez)

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- GIS: 4 edificaciones (llave building_id)
CREATE TABLE IF NOT EXISTS buildings (
    building_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    is_monitored  BOOLEAN NOT NULL DEFAULT FALSE,
    use_type      TEXT,
    levels        INTEGER,
    bays_x        INTEGER,
    bays_y        INTEGER,
    year_built    INTEGER,
    geom          geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS buildings_geom_idx ON buildings USING GIST (geom);

-- BIM/COBie: componentes estructurales (llave ifc_global_id = COBie ExtIdentifier)
CREATE TABLE IF NOT EXISTS components (
    ifc_global_id     CHAR(22) PRIMARY KEY,
    building_id       TEXT NOT NULL REFERENCES buildings (building_id),
    name              TEXT NOT NULL,
    type_name         TEXT,
    space             TEXT,
    description       TEXT,
    ext_system        TEXT,
    ext_object        TEXT,
    tag_number        TEXT,
    asset_identifier  TEXT,
    installation_date DATE
);
CREATE INDEX IF NOT EXISTS components_building_idx ON components (building_id);

CREATE TABLE IF NOT EXISTS component_attributes (
    ifc_global_id CHAR(22) NOT NULL REFERENCES components (ifc_global_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    value         TEXT,
    unit          TEXT,
    category      TEXT,
    description   TEXT,
    PRIMARY KEY (ifc_global_id, name)
);

-- IoT: diccionario sensor_id ↔ ifc_global_id ↔ building_id
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id      TEXT PRIMARY KEY,
    building_id    TEXT NOT NULL REFERENCES buildings (building_id),
    ifc_global_id  CHAR(22) NOT NULL REFERENCES components (ifc_global_id),
    ifc_class      TEXT NOT NULL,
    element_name   TEXT,
    level          INTEGER,
    grid_x         INTEGER,
    grid_y         INTEGER,
    sensor_type    TEXT,
    k_design_kn_m  DOUBLE PRECISION NOT NULL,
    modal_mass_t   DOUBLE PRECISION,
    installed_on   DATE
);

-- Serie temporal de rigidez (hypertable TimescaleDB)
CREATE TABLE IF NOT EXISTS stiffness_readings (
    time          TIMESTAMPTZ NOT NULL,
    sensor_id     TEXT NOT NULL REFERENCES sensors (sensor_id),
    k_kn_m        DOUBLE PRECISION NOT NULL,
    frequency_hz  DOUBLE PRECISION,
    PRIMARY KEY (sensor_id, time)
);
SELECT create_hypertable('stiffness_readings', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS stiffness_time_idx ON stiffness_readings (time DESC);
