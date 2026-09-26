TRUNCATE TABLE quality_flags RESTART IDENTITY;

-- ============================================================
-- COMPLETENESS
-- ============================================================

-- C1: Missing latitude or longitude
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'C-001',
    CONCAT('latitude=', latitude, ', longitude=', longitude)
FROM portfolio_raw
WHERE latitude IS NULL
   OR longitude IS NULL;


-- C2: Missing construction code
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'C-002',
    'construction_code=NULL'
FROM portfolio_raw
WHERE construction_code IS NULL
   OR TRIM(construction_code) = '';


-- C3: Missing year built
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'C-003',
    'year_built=NULL'
FROM portfolio_raw
WHERE year_built IS NULL;


-- C4: Missing number of storeys
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'C-004',
    'num_storeys=NULL'
FROM portfolio_raw
WHERE num_storeys IS NULL;


-- C5: Missing contents TIV
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'C-005',
    'tiv_contents=NULL'
FROM portfolio_raw
WHERE tiv_contents IS NULL;


-- C6: Missing deductible
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'C-006',
    'deductible=NULL'
FROM portfolio_raw
WHERE deductible IS NULL;


-- C7: Missing occupancy
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'C-007',
    'occupancy_code=NULL'
FROM portfolio_raw
WHERE occupancy_code IS NULL
   OR TRIM(occupancy_code) = '';


-- ============================================================
-- VALIDITY
-- ============================================================

-- V1: Negative total TIV

INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'V-001',
    tiv_total::text
FROM portfolio_raw
WHERE tiv_total < 0;


-- V2: Zero building TIV
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'V-002',
    tiv_building::text
FROM portfolio_raw
WHERE tiv_building = 0;


-- V3: Invalid latitude/longitude range
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'V-003',
    CONCAT('latitude=', latitude, ', longitude=', longitude)
FROM portfolio_raw
WHERE (latitude IS NOT NULL
       AND (latitude < -90 OR latitude > 90))
   OR (longitude IS NOT NULL
       AND (longitude < -180 OR longitude > 180));


-- V4: Future construction year
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'V-004',
    year_built::text
FROM portfolio_raw
WHERE year_built > EXTRACT(YEAR FROM CURRENT_DATE);


-- V5: Extremely early construction year
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'V-005',
    year_built::text
FROM portfolio_raw
WHERE year_built < 1850;


-- V6: Non-positive storeys
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'V-006',
    num_storeys::text
FROM portfolio_raw
WHERE num_storeys <= 0;


-- V7: Deductible greater than total TIV

INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'V-007',
    CONCAT(
        'deductible=', deductible,
        ', tiv_total=', tiv_total
    )
FROM portfolio_raw
WHERE deductible > tiv_total;

-- ============================================================
-- CONSISTENCY
-- ============================================================

-- X1: Timber construction with unusually high storey count
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'X-001',
    CONCAT('construction=', construction_code,
           ', storeys=', num_storeys)
FROM portfolio_raw
WHERE LOWER(TRIM(construction_code)) = 'timber'
  AND num_storeys > 4;


-- X2: RCC construction with unusually early construction year
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'X-002',
    CONCAT('construction=', construction_code,
           ', year=', year_built)
FROM portfolio_raw
WHERE LOWER(TRIM(construction_code)) = 'rcc'
  AND year_built < 1900;


-- X3: Residential exposure with exceptionally large TIV
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'X-003',
    CONCAT('occupancy=', occupancy_code,
           ', tiv_building=', tiv_building)
FROM portfolio_raw
WHERE LOWER(TRIM(occupancy_code)) IN ('res', 'residential')
  AND tiv_building >= 800000000;


-- X4: Industrial exposure with unusually high storey count
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'X-004',
    CONCAT('occupancy=', occupancy_code,
           ', storeys=', num_storeys)
FROM portfolio_raw
WHERE LOWER(TRIM(occupancy_code)) = 'ind'
  AND num_storeys > 20;


-- X5: Floor area inconsistent with building value
-- Flag unusually high building TIV density using the
-- threshold calibrated once on the clean baseline.
-- Threshold = 7 × clean-baseline median TIV per square metre.

INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'X-005',
    CONCAT(
        'floor_area=', p.floor_area_sqm,
        ', tiv_building=', p.tiv_building,
        ', tiv_per_sqm=',
        ROUND(
            (p.tiv_building / NULLIF(p.floor_area_sqm, 0))::numeric,
            2
        ),
        ', threshold_per_sqm=',
        ROUND(r.threshold_per_sqm::numeric, 2)
    )
FROM portfolio_raw p
CROSS JOIN x005_reference r
WHERE p.floor_area_sqm > 0
  AND p.tiv_building IS NOT NULL
  AND (p.tiv_building / p.floor_area_sqm) > r.threshold_per_sqm;


-- X6: Postcode inconsistent with district
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'X-006',
    CONCAT('postcode=', p.postcode,
           ', district=', p.district,
           ', reference_district=', r.district)
FROM portfolio_raw p
JOIN postcode_district_reference r
  ON TRIM(p.postcode) = TRIM(r.postcode)
WHERE p.district IS NOT NULL
  AND p.postcode IS NOT NULL
  AND p.district <> r.district;

-- X7: City inconsistent with district
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'X-007',
    CONCAT('city=', city,
           ', district=', district)
FROM portfolio_raw
WHERE
      (LOWER(TRIM(district)) = 'khordha'
       AND LOWER(TRIM(city)) <> 'bhubaneswar')
   OR (LOWER(TRIM(district)) = 'cuttack'
       AND LOWER(TRIM(city)) <> 'cuttack')
   OR (LOWER(TRIM(district)) = 'puri'
       AND LOWER(TRIM(city)) <> 'puri')
   OR (LOWER(TRIM(district)) = 'jagatsinghpur'
       AND LOWER(TRIM(city)) <> 'paradip');


-- ============================================================
-- DUPLICATION
-- ============================================================

-- D1: Exact duplicate records
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'D-001',
    'Exact duplicate of another portfolio record'
FROM portfolio_raw p
JOIN portfolio_raw q
  ON p.row_id > q.row_id
 AND p.location_id = q.location_id
 AND p.account_id = q.account_id
 AND COALESCE(p.address_line, '') = COALESCE(q.address_line, '')
 AND COALESCE(p.city, '') = COALESCE(q.city, '')
 AND COALESCE(p.district, '') = COALESCE(q.district, '')
 AND COALESCE(p.state, '') = COALESCE(q.state, '')
 AND COALESCE(p.postcode, '') = COALESCE(q.postcode, '')
 AND COALESCE(p.latitude, -999) = COALESCE(q.latitude, -999)
 AND COALESCE(p.longitude, -999) = COALESCE(q.longitude, -999)
 AND COALESCE(p.occupancy_code, '') = COALESCE(q.occupancy_code, '')
 AND COALESCE(p.construction_code, '') = COALESCE(q.construction_code, '')
 AND COALESCE(p.year_built, -999) = COALESCE(q.year_built, -999)
 AND COALESCE(p.num_storeys, -999) = COALESCE(q.num_storeys, -999)
 AND COALESCE(p.floor_area_sqm, -999) = COALESCE(q.floor_area_sqm, -999)
 AND COALESCE(p.tiv_building, -999) = COALESCE(q.tiv_building, -999)
 AND COALESCE(p.tiv_contents, -999) = COALESCE(q.tiv_contents, -999)
 AND COALESCE(p.tiv_bi, -999) = COALESCE(q.tiv_bi, -999)
 AND COALESCE(p.tiv_total, -999) = COALESCE(q.tiv_total, -999)
 AND COALESCE(p.currency, '') = COALESCE(q.currency, '')
 AND COALESCE(p.deductible, -999) = COALESCE(q.deductible, -999)
 AND COALESCE(p.policy_limit, -999) = COALESCE(q.policy_limit, -999);


-- D2: Same coordinates assigned to different location IDs
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT DISTINCT
    p.row_id,
    'D-002',
    CONCAT(
        'location_id=', p.location_id,
        ', shared coordinates with another location'
    )
FROM portfolio_raw p
JOIN portfolio_raw q
  ON p.row_id <> q.row_id
 AND p.location_id <> q.location_id
 AND p.latitude IS NOT NULL
 AND p.longitude IS NOT NULL
 AND q.latitude IS NOT NULL
 AND q.longitude IS NOT NULL
 AND p.latitude = q.latitude
 AND p.longitude = q.longitude;


-- ============================================================
-- D3: Near-duplicate address
-- Classification: UNKNOWN
--
-- Controlled synthetic test:
-- Original:   Synthetic location
-- Corrupted:  Synthetic location Ltd.
--
-- The rule flags addresses containing the injected suffix.
-- These are candidates for review, not automatic corrections.
-- ============================================================

INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'D-003',
    CONCAT(
        'address=', address_line,
        ', near-duplicate address candidate'
    )
FROM portfolio_raw
WHERE address_line IS NOT NULL
  AND LOWER(TRIM(address_line)) LIKE '% ltd.';


-- D4: Same location ID with different TIV
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'D-004',
    CONCAT(
        'location_id=', p.location_id,
        ', tiv_building=', p.tiv_building,
        ', conflicting TIV'
    )
FROM portfolio_raw p
WHERE EXISTS (
    SELECT 1
    FROM portfolio_raw q
    WHERE q.location_id = p.location_id
      AND q.row_id <> p.row_id
      AND q.tiv_building IS DISTINCT FROM p.tiv_building
);


-- ============================================================
-- PLAUSIBILITY
-- ============================================================

-- P-001: Building TIV exceeds the frozen clean-baseline threshold.
-- The threshold is calibrated once on the authoritative clean portfolio
-- and stored in p001_reference. It is the smallest integer multiple
-- of the clean-baseline median that exceeds the clean-baseline maximum.

INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'P-001',
    CONCAT(
        'tiv_building=', p.tiv_building,
        ', clean_baseline_median=', r.median_tiv_building,
        ', multiplier=', r.multiplier,
        ', threshold_tiv_building=', r.threshold_tiv_building
    )
FROM portfolio_raw p
CROSS JOIN p001_reference r
WHERE p.tiv_building > r.threshold_tiv_building;


-- P2: Repeated round TIV value
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'P-002',
    CONCAT(
        'tiv_total=', p.tiv_total,
        ', rounded_value=', ROUND(p.tiv_total::numeric, 0),
        ', occurrences=', x.occurrences
    )
FROM portfolio_raw p
JOIN (
    SELECT
        ROUND(tiv_total::numeric, 0) AS rounded_tiv,
        COUNT(*) AS occurrences
    FROM portfolio_raw
    WHERE tiv_total IS NOT NULL
    GROUP BY ROUND(tiv_total::numeric, 0)
    HAVING COUNT(*) >= 10
) x
    ON ROUND(p.tiv_total::numeric, 0) = x.rounded_tiv
WHERE p.tiv_total > 0
  AND ABS(
        p.tiv_total::numeric
        - ROUND(p.tiv_total::numeric / 1000000.0) * 1000000.0
      ) < 1.0;


-- P3: Single location represents an unusually large share
-- of total portfolio TIV
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'P-003',
    CONCAT(
        'tiv_building=', p.tiv_building,
        ', portfolio_share=', 
        ROUND(
            100.0 * p.tiv_total /
            NULLIF(t.total_tiv, 0),
            2
        ),
        '%'
    )
FROM portfolio_raw p
CROSS JOIN (
    SELECT SUM(tiv_total) AS total_tiv
    FROM portfolio_raw
    WHERE tiv_total IS NOT NULL
      AND tiv_total > 0
) t
WHERE p.tiv_total IS NOT NULL
  AND p.tiv_total > 0
  AND p.tiv_total / NULLIF(t.total_tiv, 0) >= 0.10;


-- P4: Suspicious concentration of construction year
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'P-004',
    CONCAT(
        'year_built=', p.year_built,
        ', occurrences=', x.occurrences
    )
FROM portfolio_raw p
JOIN (
    SELECT
        year_built,
        COUNT(*) AS occurrences
    FROM portfolio_raw
    WHERE year_built IS NOT NULL
    GROUP BY year_built
    HAVING COUNT(*) >= 100
) x
  ON p.year_built = x.year_built
WHERE p.year_built = 1900;


-- P5: Industrial properties with suspicious one-storey default
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'P-005',
    CONCAT(
        'occupancy=', p.occupancy_code,
        ', storeys=', p.num_storeys,
        ', industrial_one_storey_share=',
        ROUND(
            100.0 * x.one_storey /
            NULLIF(x.total_industrial, 0),
            2
        ),
        '%'
    )
FROM portfolio_raw p
CROSS JOIN (
    SELECT
        COUNT(*) FILTER (
            WHERE LOWER(TRIM(occupancy_code)) = 'ind'
              AND num_storeys = 1
        ) AS one_storey,
        COUNT(*) FILTER (
            WHERE LOWER(TRIM(occupancy_code)) = 'ind'
        ) AS total_industrial
    FROM portfolio_raw
) x
WHERE LOWER(TRIM(p.occupancy_code)) = 'ind'
  AND p.num_storeys = 1
  AND x.one_storey::numeric /
      NULLIF(x.total_industrial, 0) >= 0.50;


-- ============================================================
-- GEOGRAPHY
-- ============================================================

-- G1: Coordinates fall outside the mapped Odisha land area
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'G-001',
    CONCAT(
        'latitude=', p.latitude,
        ', longitude=', p.longitude
    )
FROM portfolio_raw p
WHERE p.latitude IS NOT NULL
  AND p.longitude IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM admin_boundaries a
      WHERE ST_Contains(
          a.geometry,
          ST_SetSRID(
              ST_MakePoint(p.longitude, p.latitude),
              4326
          )
      )
  );


-- G2: Coordinates are consistent with a possible latitude/longitude swap
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'G-002',
    CONCAT(
        'latitude=', p.latitude,
        ', longitude=', p.longitude
    )
FROM portfolio_raw p
WHERE p.latitude IS NOT NULL
  AND p.longitude IS NOT NULL
  AND ABS(p.latitude) <= 90
  AND ABS(p.longitude) <= 90
  AND p.latitude <> p.longitude
  AND EXISTS (
      SELECT 1
      FROM admin_boundaries a
      WHERE ST_Contains(
          a.geometry,
          ST_SetSRID(
              ST_MakePoint(p.latitude, p.longitude),
              4326
          )
      )
  );


-- G3: Null-island / zero-zero coordinates
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'G-003',
    CONCAT(
        'latitude=', latitude,
        ', longitude=', longitude
    )
FROM portfolio_raw
WHERE latitude = 0
  AND longitude = 0;


-- G4: Coordinates outside India
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'G-004',
    CONCAT(
        'latitude=', p.latitude,
        ', longitude=', p.longitude
    )
FROM portfolio_raw p
WHERE p.latitude IS NOT NULL
  AND p.longitude IS NOT NULL
  AND p.latitude BETWEEN -90 AND 90
  AND p.longitude BETWEEN -180 AND 180
  AND NOT EXISTS (
      SELECT 1
      FROM india_boundary i
      WHERE i.gid_0 = 'IND'
        AND ST_Contains(
            i.geometry,
            ST_SetSRID(
                ST_MakePoint(p.longitude, p.latitude),
                4326
            )
        )
  );


-- G5: Excessive postcode-level coordinate clustering
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    p.row_id,
    'G-005',
    CONCAT(
        'latitude=', p.latitude,
        ', longitude=', p.longitude,
        ', geocode_level=', p.geocode_level,
        ', coordinate_cluster_count=', x.coordinate_count
    )
FROM portfolio_raw p
JOIN (
    SELECT
        latitude,
        longitude,
        COUNT(*) AS coordinate_count
    FROM portfolio_raw
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
      AND LOWER(TRIM(geocode_level)) = 'postcode'
    GROUP BY latitude, longitude
    HAVING COUNT(*) >= 10
) x
  ON p.latitude = x.latitude
 AND p.longitude = x.longitude
WHERE LOWER(TRIM(p.geocode_level)) = 'postcode';

-- ============================================================
-- CODING
-- ============================================================

-- K1: Free-text / non-standard construction code
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'K-001',
    CONCAT('construction_code=', construction_code)
FROM portfolio_raw
WHERE LOWER(TRIM(construction_code)) NOT IN (
    'rcc',
    'masonry',
    'steel',
    'timber'
)
AND construction_code IS NOT NULL
AND TRIM(construction_code) <> '';


-- K2: Unknown / non-standard occupancy code
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'K-002',
    CONCAT('occupancy_code=', occupancy_code)
FROM portfolio_raw
WHERE LOWER(TRIM(occupancy_code)) NOT IN (
    'res',
    'com',
    'ind',
    'pub'
)
AND occupancy_code IS NOT NULL
AND TRIM(occupancy_code) <> '';


-- K3: Mixed construction coding scheme
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'K-003',
    CONCAT('construction_code=', construction_code)
FROM portfolio_raw
WHERE TRIM(construction_code) IN ('01', '02', '03', '04');


-- K4: Currency inconsistent with portfolio convention
INSERT INTO quality_flags (row_id, rule_id, flagged_value)
SELECT
    row_id,
    'K-004',
    CONCAT('currency=', currency)
FROM portfolio_raw
WHERE currency IS NOT NULL
  AND TRIM(currency) <> 'INR';