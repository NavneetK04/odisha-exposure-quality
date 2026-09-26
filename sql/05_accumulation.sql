-- ============================================================
-- PROJECT 2: ACCUMULATION ANALYSIS
-- Project 1 reference grid
-- 0.25 degree grid points
-- ============================================================

DROP TABLE IF EXISTS accumulation_dirty;
DROP TABLE IF EXISTS accumulation_cleansed;
DROP TABLE IF EXISTS accumulation_summary;
DROP TABLE IF EXISTS accumulation_top10;
DROP TABLE IF EXISTS accumulation_comparison;
DROP TABLE IF EXISTS accumulation_largest_changes;
DROP TABLE IF EXISTS accumulation_cleansed_fallback;
DROP TABLE IF EXISTS accumulation_fallback_comparison;
DROP TABLE IF EXISTS accumulation_critical_referred;

-- ============================================================
-- 0. MATERIAL REFERRED RECORDS EXCLUDED FROM PRIMARY
--    ACCUMULATION
--
-- P-001 records have potentially material TIV unit distortion.
-- P-003 has an unresolved single-location
-- concentration anomaly.
--
-- These records remain REFERRED in the audit treatment.
-- They are excluded from the primary accumulation because
-- their unresolved values could materially distort the
-- accumulation result.
--
-- They are retained for sensitivity analysis.
-- ============================================================

CREATE TABLE accumulation_critical_referred AS
SELECT
    p.row_id,
    p.location_id,
    p.district,
    p.latitude_clean,
    p.longitude_clean,
    p.tiv_total_clean AS stored_tiv,
    q.has_p001,
    q.has_p003,
    CASE
        WHEN q.has_p001 AND q.has_p003
            THEN 'P-001 and P-003 detected'
        WHEN q.has_p001
            THEN 'P-001 unit confusion detected'
        ELSE 'P-003 single-location concentration anomaly detected'
    END AS exclusion_reason
FROM portfolio_cleansed p
JOIN (
    SELECT
        row_id,
        BOOL_OR(rule_id = 'P-001') AS has_p001,
        BOOL_OR(rule_id = 'P-003') AS has_p003
    FROM quality_flags
    WHERE rule_id IN ('P-001', 'P-003')
    GROUP BY row_id
) q
    ON q.row_id = p.row_id;

DO $$
BEGIN
    IF (
        SELECT COUNT(*)
        FROM accumulation_critical_referred
    ) <> 41
    THEN
        RAISE EXCEPTION
            'critical_referred row count is %, expected 41; production detection exclusion set may have changed',
            (SELECT COUNT(*) FROM accumulation_critical_referred);
    END IF;
END $$;

-- ============================================================
-- 1. DIRTY PORTFOLIO
-- Assign each usable exposure to nearest Project 1 grid point
-- ============================================================

CREATE TABLE accumulation_dirty AS
SELECT
    g.grid_id,
    g.grid_lon,
    g.grid_lat,
    COUNT(*) AS location_count,
    SUM(p.tiv_total) AS total_tiv
FROM portfolio_raw p
CROSS JOIN LATERAL (
    SELECT
        ROW_NUMBER() OVER () AS grid_id,
        ST_X((dp).geom) AS grid_lon,
        ST_Y((dp).geom) AS grid_lat
    FROM project1_exposure_grid g2,
         ST_DumpPoints(g2.geometry) AS dp
    ORDER BY
        ST_Distance(
            ST_SetSRID(
                ST_MakePoint(p.longitude, p.latitude),
                4326
            ),
            dp.geom
        )
    LIMIT 1
) g
WHERE p.latitude IS NOT NULL
  AND p.longitude IS NOT NULL
  AND p.latitude BETWEEN -90 AND 90
  AND p.longitude BETWEEN -180 AND 180
  AND ST_Distance(
        ST_SetSRID(
            ST_MakePoint(p.longitude, p.latitude),
            4326
        ),
        ST_SetSRID(
            ST_MakePoint(g.grid_lon, g.grid_lat),
            4326
        )
      ) <= 0.177
GROUP BY
    g.grid_id,
    g.grid_lon,
    g.grid_lat;


-- ============================================================
-- 2. CLEANSED PORTFOLIO
-- Exclude quarantined records
-- ============================================================

CREATE TABLE accumulation_cleansed AS
SELECT
    g.grid_id,
    g.grid_lon,
    g.grid_lat,
    COUNT(*) AS location_count,
    SUM(p.tiv_total_clean) AS total_tiv
FROM portfolio_cleansed p
CROSS JOIN LATERAL (
    SELECT
        ROW_NUMBER() OVER () AS grid_id,
        ST_X((dp).geom) AS grid_lon,
        ST_Y((dp).geom) AS grid_lat
    FROM project1_exposure_grid g2,
         ST_DumpPoints(g2.geometry) AS dp
    ORDER BY
        ST_Distance(
            ST_SetSRID(
                ST_MakePoint(p.longitude_clean, p.latitude_clean),
                4326
            ),
            dp.geom
        )
    LIMIT 1
) g
WHERE p.quarantined = FALSE
  AND NOT EXISTS (
      SELECT 1
      FROM accumulation_critical_referred x
      WHERE x.row_id = p.row_id
  )
  AND p.latitude_clean IS NOT NULL
  AND p.longitude_clean IS NOT NULL
  AND p.latitude_clean BETWEEN -90 AND 90
  AND p.longitude_clean BETWEEN -180 AND 180
  AND p.tiv_total_clean IS NOT NULL
  AND ST_Distance(
        ST_SetSRID(
            ST_MakePoint(p.longitude_clean, p.latitude_clean),
            4326
        ),
        ST_SetSRID(
            ST_MakePoint(g.grid_lon, g.grid_lat),
            4326
        )
      ) <= 0.177
GROUP BY
    g.grid_id,
    g.grid_lon,
    g.grid_lat;


-- ============================================================
-- 2B. CLEANSED PORTFOLIO WITH DISTRICT-LEVEL FALLBACK
--
-- Records with valid coordinates use their actual coordinates.
-- Records without coordinates are assigned to a district
-- representative point.
--
-- Fallback locations are ASSUMED and are used only for
-- accumulation sensitivity analysis.
-- ============================================================

CREATE TABLE accumulation_cleansed_fallback AS

WITH spatial_portfolio AS (

    -- Actual cleaned coordinates
    SELECT
        p.row_id,
        p.tiv_total_clean,
        p.latitude_clean AS latitude,
        p.longitude_clean AS longitude,
        'ACTUAL'::text AS geocode_scenario
    FROM portfolio_cleansed p
    WHERE p.quarantined = FALSE
        AND NOT EXISTS (
            SELECT 1
            FROM accumulation_critical_referred x
            WHERE x.row_id = p.row_id
        )
      AND p.tiv_total_clean IS NOT NULL
      AND p.latitude_clean IS NOT NULL
      AND p.longitude_clean IS NOT NULL
      AND p.latitude_clean BETWEEN -90 AND 90
      AND p.longitude_clean BETWEEN -180 AND 180

    UNION ALL

    -- District-level fallback
    SELECT
        p.row_id,
        p.tiv_total_clean,
        f.latitude,
        f.longitude,
        'ASSUMED'::text AS geocode_scenario
    FROM portfolio_cleansed p
JOIN district_fallback_points f
  ON p.district = f.district
WHERE p.quarantined = FALSE
  AND NOT EXISTS (
      SELECT 1
      FROM accumulation_critical_referred x
      WHERE x.row_id = p.row_id
  )
  AND p.tiv_total_clean IS NOT NULL
      AND (
          p.latitude_clean IS NULL
          OR p.longitude_clean IS NULL
      )
),

grid_assignment AS (

    SELECT
        s.row_id,
        s.tiv_total_clean,
        s.geocode_scenario,
        g.grid_lon,
        g.grid_lat

    FROM spatial_portfolio s

    CROSS JOIN LATERAL (

        SELECT
            ST_X((dp).geom) AS grid_lon,
            ST_Y((dp).geom) AS grid_lat

        FROM project1_exposure_grid g2,
             ST_DumpPoints(g2.geometry) AS dp

        ORDER BY
            ST_Distance(
                ST_SetSRID(
                    ST_MakePoint(s.longitude, s.latitude),
                    4326
                ),
                dp.geom
            )

        LIMIT 1

    ) g
)

SELECT
    grid_lon,
    grid_lat,
    COUNT(*) AS location_count,
    SUM(tiv_total_clean) AS total_tiv,

    COUNT(*) FILTER (
        WHERE geocode_scenario = 'ASSUMED'
    ) AS assumed_location_count,

    SUM(tiv_total_clean) FILTER (
        WHERE geocode_scenario = 'ASSUMED'
    ) AS assumed_tiv

FROM grid_assignment

GROUP BY
    grid_lon,
    grid_lat;


-- ============================================================
-- 2C. CONSERVATIVE VS FALLBACK COMPARISON
-- ============================================================

CREATE TABLE accumulation_fallback_comparison AS

WITH conservative AS (

    SELECT
        SUM(total_tiv) AS portfolio_tiv,
        SUM(location_count) AS locations
    FROM accumulation_cleansed

),

fallback AS (

    SELECT
        SUM(total_tiv) AS portfolio_tiv,
        SUM(location_count) AS locations,
        SUM(assumed_tiv) AS assumed_tiv,
        SUM(assumed_location_count) AS assumed_locations
    FROM accumulation_cleansed_fallback

),

conservative_top10 AS (

    SELECT
        SUM(total_tiv) AS top10_tiv
    FROM (
        SELECT
            total_tiv,
            RANK() OVER (
                ORDER BY total_tiv DESC
            ) AS tiv_rank
        FROM accumulation_cleansed
    ) x
    WHERE tiv_rank <= 10

),

fallback_top10 AS (

    SELECT
        SUM(total_tiv) AS top10_tiv
    FROM (
        SELECT
            total_tiv,
            RANK() OVER (
                ORDER BY total_tiv DESC
            ) AS tiv_rank
        FROM accumulation_cleansed_fallback
    ) x
    WHERE tiv_rank <= 10

)

SELECT
    'CONSERVATIVE' AS scenario,
    c.locations,
    c.portfolio_tiv,
    t.top10_tiv,
    t.top10_tiv / c.portfolio_tiv * 100
        AS top10_tiv_share_pct,
    NULL::bigint AS assumed_locations,
    NULL::numeric AS assumed_tiv

FROM conservative c
CROSS JOIN conservative_top10 t

UNION ALL

SELECT
    'DISTRICT_FALLBACK',
    f.locations,
    f.portfolio_tiv,
    t.top10_tiv,
    t.top10_tiv / f.portfolio_tiv * 100,
    f.assumed_locations,
    f.assumed_tiv

FROM fallback f
CROSS JOIN fallback_top10 t;


-- ============================================================
-- 3. PORTFOLIO TOTALS
-- ============================================================

CREATE TABLE accumulation_summary AS

SELECT
    'DIRTY' AS portfolio_status,
    COUNT(*) AS grid_cells,
    SUM(location_count) AS locations,
    SUM(total_tiv) AS portfolio_tiv
FROM accumulation_dirty

UNION ALL

SELECT
    'CLEANSED',
    COUNT(*),
    SUM(location_count),
    SUM(total_tiv)
FROM accumulation_cleansed;


-- ============================================================
-- 4. TOP 10 ACCUMULATION CELLS
-- ============================================================

CREATE TABLE accumulation_top10 AS

WITH combined AS (

    SELECT
        'DIRTY' AS portfolio_status,
        grid_lon,
        grid_lat,
        location_count,
        total_tiv
    FROM accumulation_dirty

    UNION ALL

    SELECT
        'CLEANSED',
        grid_lon,
        grid_lat,
        location_count,
        total_tiv
    FROM accumulation_cleansed
),

ranked AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY portfolio_status
            ORDER BY total_tiv DESC
        ) AS tiv_rank
    FROM combined
)

SELECT *
FROM ranked
WHERE tiv_rank <= 10;

-- ============================================================
-- 4B. CONCENTRATION METRICS
--     Top-1, Top-3, Top-5 and HHI
-- ============================================================

DROP TABLE IF EXISTS accumulation_concentration;

CREATE TABLE accumulation_concentration AS

WITH ranked AS (
    SELECT
        grid_lon,
        grid_lat,
        location_count,
        total_tiv,
        ROW_NUMBER() OVER (
            ORDER BY total_tiv DESC
        ) AS rank_no
    FROM accumulation_cleansed
),
totals AS (
    SELECT SUM(total_tiv) AS portfolio_tiv
    FROM ranked
)

SELECT
    totals.portfolio_tiv,

    MAX(r.total_tiv)
        / totals.portfolio_tiv
        AS top1_share,

    SUM(
        CASE WHEN r.rank_no <= 3
             THEN r.total_tiv ELSE 0 END
    ) / totals.portfolio_tiv
        AS top3_share,

    SUM(
        CASE WHEN r.rank_no <= 5
             THEN r.total_tiv ELSE 0 END
    ) / totals.portfolio_tiv
        AS top5_share,

    SUM(
        POWER(r.total_tiv / totals.portfolio_tiv, 2)
    ) AS hhi,

    COUNT(*) AS occupied_cells

FROM ranked r
CROSS JOIN totals

GROUP BY totals.portfolio_tiv;

-- ============================================================
-- 4C. MATERIAL REFERRED SENSITIVITY ANALYSIS
--
-- PRIMARY:
--   Exclude unresolved P-001 and P-003 records.
--
-- P-001 SENSITIVITY:
--   Add P-001 records back at stored TIV.
--
-- P-003 SENSITIVITY:
--   Add P-003 P1 records back at stored TIV.
--
-- COMBINED SENSITIVITY:
--   Add both P-001 and P-003 records back.
--
-- These scenarios do NOT change treatment status.
-- They quantify the effect of unresolved records on
-- accumulation conclusions.
-- ============================================================

DROP TABLE IF EXISTS accumulation_sensitivity;

CREATE TABLE accumulation_sensitivity AS

WITH scenario_portfolio AS (

    -- --------------------------------------------------------
    -- PRIMARY
    -- --------------------------------------------------------
    SELECT
        'PRIMARY'::text AS scenario,
        p.row_id,
        p.tiv_total_clean,
        p.latitude_clean,
        p.longitude_clean
    FROM portfolio_cleansed p
    WHERE p.quarantined = FALSE
      AND NOT EXISTS (
          SELECT 1
          FROM accumulation_critical_referred x
          WHERE x.row_id = p.row_id
      )

    UNION ALL

    -- --------------------------------------------------------
    -- P-001 SENSITIVITY
    -- Primary + P-001 records
    -- --------------------------------------------------------
    SELECT
        'P001_SENSITIVITY'::text AS scenario,
        p.row_id,
        p.tiv_total_clean,
        p.latitude_clean,
        p.longitude_clean
    FROM portfolio_cleansed p
    WHERE p.quarantined = FALSE
      AND (
          NOT EXISTS (
              SELECT 1
              FROM accumulation_critical_referred x
              WHERE x.row_id = p.row_id
          )
          OR EXISTS (
              SELECT 1
              FROM accumulation_critical_referred x
              WHERE x.row_id = p.row_id
                AND x.has_p001
          )
      )

    UNION ALL

    -- --------------------------------------------------------
    -- P-003 SENSITIVITY
    -- Primary + P-003 row
    -- --------------------------------------------------------
    SELECT
        'P003_SENSITIVITY'::text AS scenario,
        p.row_id,
        p.tiv_total_clean,
        p.latitude_clean,
        p.longitude_clean
    FROM portfolio_cleansed p
    WHERE p.quarantined = FALSE
      AND (
          NOT EXISTS (
              SELECT 1
              FROM accumulation_critical_referred x
              WHERE x.row_id = p.row_id
          )
          OR EXISTS (
              SELECT 1
              FROM accumulation_critical_referred x
              WHERE x.row_id = p.row_id
                AND x.has_p003
          )
      )

    UNION ALL

    -- --------------------------------------------------------
    -- COMBINED SENSITIVITY
    -- Primary + P-001 + P-003
    -- --------------------------------------------------------
    SELECT
        'COMBINED_SENSITIVITY'::text AS scenario,
        p.row_id,
        p.tiv_total_clean,
        p.latitude_clean,
        p.longitude_clean
    FROM portfolio_cleansed p
    WHERE p.quarantined = FALSE
),

grid_assignment AS (

    SELECT
        s.scenario,
        s.row_id,
        s.tiv_total_clean,

        g.grid_lon,
        g.grid_lat

    FROM scenario_portfolio s

    CROSS JOIN LATERAL (

        SELECT
            ST_X((dp).geom) AS grid_lon,
            ST_Y((dp).geom) AS grid_lat

        FROM project1_exposure_grid g2,
             ST_DumpPoints(g2.geometry) AS dp

        WHERE s.latitude_clean IS NOT NULL
          AND s.longitude_clean IS NOT NULL

        ORDER BY
            ST_Distance(
                ST_SetSRID(
                    ST_MakePoint(
                        s.longitude_clean,
                        s.latitude_clean
                    ),
                    4326
                ),
                dp.geom
            )

        LIMIT 1

    ) g
)

SELECT
    scenario,
    grid_lon,
    grid_lat,
    COUNT(*) AS location_count,
    SUM(tiv_total_clean) AS total_tiv

FROM grid_assignment

GROUP BY
    scenario,
    grid_lon,
    grid_lat;

-- ============================================================
-- 4D. SENSITIVITY SUMMARY
-- ============================================================

DROP TABLE IF EXISTS accumulation_sensitivity_summary;

CREATE TABLE accumulation_sensitivity_summary AS

SELECT
    scenario,
    COUNT(*) AS grid_cells,
    SUM(location_count) AS spatial_locations,
    SUM(total_tiv) AS spatial_tiv
FROM accumulation_sensitivity
GROUP BY scenario
ORDER BY scenario;


-- ============================================================
-- 5. DIRTY VS CLEANSED
-- ============================================================

CREATE TABLE accumulation_comparison AS

SELECT
    COALESCE(d.grid_lon, c.grid_lon) AS grid_lon,
    COALESCE(d.grid_lat, c.grid_lat) AS grid_lat,

    COALESCE(d.location_count, 0) AS dirty_locations,
    COALESCE(c.location_count, 0) AS cleansed_locations,

    COALESCE(d.total_tiv, 0) AS dirty_tiv,
    COALESCE(c.total_tiv, 0) AS cleansed_tiv,

    COALESCE(c.total_tiv, 0)
      - COALESCE(d.total_tiv, 0) AS tiv_change,

    CASE
        WHEN COALESCE(d.total_tiv, 0) <> 0
        THEN 100.0 *
             (
                 COALESCE(c.total_tiv, 0)
                 - d.total_tiv
             ) / d.total_tiv
        ELSE NULL
    END AS tiv_change_pct

FROM accumulation_dirty d

FULL OUTER JOIN accumulation_cleansed c
    ON d.grid_lon = c.grid_lon
   AND d.grid_lat = c.grid_lat;


-- ============================================================
-- 6. LARGEST CHANGES
-- ============================================================

CREATE TABLE accumulation_largest_changes AS

SELECT *
FROM accumulation_comparison
ORDER BY ABS(tiv_change) DESC
LIMIT 20;


-- ============================================================
-- 7. DISTRICT ACCUMULATION
-- ============================================================

DROP TABLE IF EXISTS accumulation_district;

CREATE TABLE accumulation_district AS

SELECT
    'DIRTY' AS portfolio_status,
    district,
    COUNT(*) AS location_count,
    SUM(tiv_total) AS total_tiv
FROM portfolio_raw
GROUP BY district

UNION ALL

SELECT
    'CLEANSED',
    district,
    COUNT(*),
    SUM(tiv_total_clean)
FROM portfolio_cleansed
WHERE quarantined = FALSE
  AND NOT EXISTS (
      SELECT 1
      FROM accumulation_critical_referred x
      WHERE x.row_id = portfolio_cleansed.row_id
  )
GROUP BY district;


-- ============================================================
-- 8. OCCUPANCY ACCUMULATION
-- ============================================================

DROP TABLE IF EXISTS accumulation_occupancy;

CREATE TABLE accumulation_occupancy AS

SELECT
    'DIRTY' AS portfolio_status,
    occupancy_code,
    COUNT(*) AS location_count,
    SUM(tiv_total) AS total_tiv
FROM portfolio_raw
GROUP BY occupancy_code

UNION ALL

SELECT
    'CLEANSED',
    occupancy_code,
    COUNT(*),
    SUM(tiv_total_clean)
FROM portfolio_cleansed
WHERE quarantined = FALSE
  AND NOT EXISTS (
      SELECT 1
      FROM accumulation_critical_referred x
      WHERE x.row_id = portfolio_cleansed.row_id
  )
GROUP BY occupancy_code;


-- ============================================================
-- 9. CONSTRUCTION ACCUMULATION
-- ============================================================

DROP TABLE IF EXISTS accumulation_construction;

CREATE TABLE accumulation_construction AS

SELECT
    'DIRTY' AS portfolio_status,
    construction_code,
    COUNT(*) AS location_count,
    SUM(tiv_total) AS total_tiv
FROM portfolio_raw
GROUP BY construction_code

UNION ALL

SELECT
    'CLEANSED',
    construction_clean,
    COUNT(*),
    SUM(tiv_total_clean)
FROM portfolio_cleansed
WHERE quarantined = FALSE
  AND NOT EXISTS (
      SELECT 1
      FROM accumulation_critical_referred x
      WHERE x.row_id = portfolio_cleansed.row_id
  )
GROUP BY construction_clean;

-- ============================================================
-- 9A. ACCUMULATION SENSITIVITY REGRESSION GUARD
-- ============================================================

DO $$
BEGIN
    IF (
        SELECT COUNT(DISTINCT scenario)
        FROM accumulation_sensitivity
        WHERE scenario IN (
            'PRIMARY',
            'P001_SENSITIVITY',
            'P003_SENSITIVITY',
            'COMBINED_SENSITIVITY'
        )
    ) <> 4
    THEN
        RAISE EXCEPTION
            'One or more accumulation sensitivity scenarios are missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM accumulation_sensitivity
        WHERE scenario = 'P003_SENSITIVITY'
          AND total_tiv <> (
              SELECT total_tiv
              FROM accumulation_sensitivity
              WHERE scenario = 'PRIMARY'
              LIMIT 1
          )
    )
    THEN
        RAISE EXCEPTION
            'P003 sensitivity collapsed to PRIMARY; check scenario inclusion predicate';
    END IF;
END $$;


-- ============================================================
-- 10. ACCUMULATION IMPACT SUMMARY
-- ============================================================

DROP TABLE IF EXISTS accumulation_impact_summary;

CREATE TABLE accumulation_impact_summary AS

WITH all_cells AS (

    SELECT
        'DIRTY'::text AS scenario,
        total_tiv
    FROM accumulation_dirty

    UNION ALL

    SELECT
        scenario,
        total_tiv
    FROM accumulation_sensitivity

),

ranked AS (

    SELECT
        scenario,
        total_tiv,

        ROW_NUMBER() OVER (
            PARTITION BY scenario
            ORDER BY total_tiv DESC
        ) AS rn,

        SUM(total_tiv) OVER (
            PARTITION BY scenario
        ) AS portfolio_tiv

    FROM all_cells

),

summary AS (

    SELECT
        scenario,
        MAX(portfolio_tiv) AS portfolio_tiv,

        MAX(
            CASE
                WHEN rn = 1
                THEN total_tiv
            END
        ) / MAX(portfolio_tiv) AS top1_share,

        SUM(
            CASE
                WHEN rn <= 3
                THEN total_tiv
                ELSE 0
            END
        ) / MAX(portfolio_tiv) AS top3_share,

        SUM(
            CASE
                WHEN rn <= 5
                THEN total_tiv
                ELSE 0
            END
        ) / MAX(portfolio_tiv) AS top5_share,

        SUM(
            POWER(
                total_tiv / portfolio_tiv,
                2
            )
        ) AS hhi,

        COUNT(*) AS occupied_cells

    FROM ranked

    GROUP BY scenario
)

SELECT *
FROM summary

ORDER BY
    CASE scenario
        WHEN 'DIRTY' THEN 1
        WHEN 'PRIMARY' THEN 2
        WHEN 'P003_SENSITIVITY' THEN 3
        WHEN 'P001_SENSITIVITY' THEN 4
        WHEN 'COMBINED_SENSITIVITY' THEN 5
        ELSE 99
    END;