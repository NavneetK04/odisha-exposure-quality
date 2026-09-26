-- Project 2: Odisha Exposure Data Quality & Portfolio Accumulation
-- 01_schema.sql

-- ============================================================
-- RAW PORTFOLIO
-- ============================================================

CREATE TABLE IF NOT EXISTS portfolio_raw (
    row_id SERIAL PRIMARY KEY,
    location_id VARCHAR(50),
    account_id VARCHAR(50),

    address_line TEXT,
    city VARCHAR(100),
    district VARCHAR(100),
    state VARCHAR(100),
    postcode VARCHAR(20),

    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geocode_level VARCHAR(30),

    occupancy_code VARCHAR(50),
    construction_code VARCHAR(50),

    year_built INTEGER,
    num_storeys INTEGER,
    floor_area_sqm DOUBLE PRECISION,

    tiv_building NUMERIC,
    tiv_contents NUMERIC,
    tiv_bi NUMERIC,
    tiv_total NUMERIC,

    currency VARCHAR(10),

    deductible NUMERIC,
    policy_limit NUMERIC
);


-- ============================================================
-- CLEANSED PORTFOLIO
-- ============================================================

CREATE TABLE IF NOT EXISTS portfolio_cleansed (
    row_id INTEGER PRIMARY KEY,

    location_id VARCHAR(50),
    account_id VARCHAR(50),

    address_line TEXT,
    city VARCHAR(100),
    district VARCHAR(100),
    state VARCHAR(100),
    postcode VARCHAR(20),

    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geocode_level VARCHAR(30),

    occupancy_code VARCHAR(50),
    construction_code VARCHAR(50),

    year_built INTEGER,
    num_storeys INTEGER,
    floor_area_sqm DOUBLE PRECISION,

    tiv_building NUMERIC,
    tiv_contents NUMERIC,
    tiv_bi NUMERIC,
    tiv_total NUMERIC,

    currency VARCHAR(10),

    deductible NUMERIC,
    policy_limit NUMERIC,

    -- Cleaned values
    latitude_clean DOUBLE PRECISION,
    longitude_clean DOUBLE PRECISION,
    construction_clean VARCHAR(50),
    occupancy_clean VARCHAR(50),
    currency_clean VARCHAR(10),
    tiv_total_clean NUMERIC,
    geocode_level_clean VARCHAR(30),

    -- Original values retained for audit
    latitude_orig DOUBLE PRECISION,
    longitude_orig DOUBLE PRECISION,
    construction_orig VARCHAR(50),
    occupancy_orig VARCHAR(50),
    currency_orig VARCHAR(10),
    tiv_total_orig NUMERIC,
    geocode_level_orig VARCHAR(30),

    -- Treatment / audit fields
    treatment_applied VARCHAR(30),
    treatment_rule VARCHAR(100),
    treatment_method TEXT,
    classification VARCHAR(50),
    priority VARCHAR(10),

    treated_by VARCHAR(100),
    treated_at TIMESTAMP,

    quarantined BOOLEAN DEFAULT FALSE,
    referred BOOLEAN DEFAULT FALSE
);


-- ============================================================
-- RULE CATALOGUE
-- ============================================================

CREATE TABLE IF NOT EXISTS rule_catalogue (
    rule_id VARCHAR(30) PRIMARY KEY,
    dimension VARCHAR(30) NOT NULL,
    description TEXT NOT NULL,

    severity VARCHAR(20),
    classification VARCHAR(20),

    rationale TEXT,

    affects_hazard BOOLEAN DEFAULT FALSE,
    affects_vulnerability BOOLEAN DEFAULT FALSE,
    affects_financial BOOLEAN DEFAULT FALSE,

    tested_by_injection BOOLEAN DEFAULT FALSE,
    injection_rule VARCHAR(30)
);


-- ============================================================
-- QUALITY FLAGS
-- ============================================================

CREATE TABLE IF NOT EXISTS quality_flags (
    flag_id SERIAL PRIMARY KEY,

    row_id INTEGER NOT NULL,
    rule_id VARCHAR(30) NOT NULL,

    flagged_value TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (rule_id)
        REFERENCES rule_catalogue(rule_id)
);


-- ============================================================
-- MATERIALITY TIV REFERENCE
-- ============================================================

CREATE TABLE IF NOT EXISTS materiality_tiv_reference (
    row_id INTEGER PRIMARY KEY,
    validated_tiv NUMERIC NOT NULL,
    validation_basis VARCHAR(50) NOT NULL
);


-- ============================================================
-- MATERIALITY SCORES
-- ============================================================

CREATE TABLE IF NOT EXISTS materiality_scores (
    row_id INTEGER NOT NULL,
    rule_id VARCHAR(30) NOT NULL,

    affects_hazard BOOLEAN DEFAULT FALSE,
    affects_vulnerability BOOLEAN DEFAULT FALSE,
    affects_financial BOOLEAN DEFAULT FALSE,

    tiv_percentile DOUBLE PRECISION,
    is_concentrated BOOLEAN DEFAULT FALSE,
    changes_decision BOOLEAN DEFAULT FALSE,

    priority VARCHAR(10),

    PRIMARY KEY (row_id, rule_id)
);


-- ============================================================
-- ADMINISTRATIVE BOUNDARIES
-- ============================================================

CREATE TABLE IF NOT EXISTS admin_boundaries (
    district VARCHAR(100) PRIMARY KEY,
    geometry geometry(MultiPolygon, 4326)
);


-- ============================================================
-- INDIA BOUNDARY
-- ============================================================

CREATE TABLE IF NOT EXISTS india_boundary (
    gid_0 VARCHAR(10) PRIMARY KEY,
    geometry geometry(MultiPolygon, 4326)
);


-- ============================================================
-- POSTCODE / DISTRICT REFERENCE
-- ============================================================

CREATE TABLE IF NOT EXISTS postcode_district_reference (
    postcode VARCHAR(20) PRIMARY KEY,
    district VARCHAR(100) NOT NULL,
    rank_no INTEGER
);