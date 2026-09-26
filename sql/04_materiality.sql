-- ============================================================
-- 04_materiality.sql
-- Record-level materiality assessment
-- ============================================================

TRUNCATE TABLE materiality_scores;


-- ------------------------------------------------------------
-- 1. Validated TIV percentile
--
-- For the synthetic portfolio, validated TIV comes from the
-- clean reference portfolio. This prevents injected financial
-- anomalies from determining their own materiality.
--
-- Rows without a clean reference retain raw TIV as an
-- unvalidated fallback.
-- ------------------------------------------------------------

DROP TABLE IF EXISTS tmp_tiv_percentile;

CREATE TEMP TABLE tmp_tiv_percentile AS
SELECT
    p.row_id,

    COALESCE(
        r.validated_tiv,
        p.tiv_total
    ) AS materiality_tiv,

    CASE
        WHEN COALESCE(r.validated_tiv, p.tiv_total) IS NULL
            THEN NULL
        ELSE ROUND(
            100.0 * PERCENT_RANK() OVER (
                ORDER BY COALESCE(r.validated_tiv, p.tiv_total)
            )::numeric,
            2
        )
    END AS tiv_percentile

FROM portfolio_raw p

LEFT JOIN materiality_tiv_reference r
    ON r.row_id = p.row_id;


-- ------------------------------------------------------------
-- 2. Assign each portfolio record to a 0.25 degree cell
-- ------------------------------------------------------------

DROP TABLE IF EXISTS tmp_portfolio_cells;

CREATE TEMP TABLE tmp_portfolio_cells AS
SELECT
    row_id,
    FLOOR(longitude / 0.25)::integer AS cell_x,
    FLOOR(latitude  / 0.25)::integer AS cell_y
FROM portfolio_raw
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND latitude BETWEEN -90 AND 90
  AND longitude BETWEEN -180 AND 180;


-- ------------------------------------------------------------
-- 3. Portfolio baseline count per spatial cell
-- ------------------------------------------------------------

DROP TABLE IF EXISTS tmp_cell_baseline;

CREATE TEMP TABLE tmp_cell_baseline AS
SELECT
    cell_x,
    cell_y,
    COUNT(*) AS portfolio_count
FROM tmp_portfolio_cells
GROUP BY cell_x, cell_y;


-- ------------------------------------------------------------
-- 4. Flagged records with spatial cells
-- ------------------------------------------------------------

DROP TABLE IF EXISTS tmp_flagged;

CREATE TEMP TABLE tmp_flagged AS
SELECT DISTINCT
    q.row_id,
    q.rule_id,
    t.materiality_tiv,
    t.tiv_percentile,
    pc.cell_x,
    pc.cell_y,
    rc.severity,
    rc.classification,
    rc.affects_hazard,
    rc.affects_vulnerability,
    rc.affects_financial
FROM quality_flags q
JOIN portfolio_raw p
    ON p.row_id = q.row_id
JOIN rule_catalogue rc
    ON rc.rule_id = q.rule_id
LEFT JOIN tmp_tiv_percentile t
    ON t.row_id = q.row_id
LEFT JOIN tmp_portfolio_cells pc
    ON pc.row_id = q.row_id;


-- ------------------------------------------------------------
-- 5. Number of flagged records for each rule
-- ------------------------------------------------------------

DROP TABLE IF EXISTS tmp_rule_totals;

CREATE TEMP TABLE tmp_rule_totals AS
SELECT
    rule_id,
    COUNT(*) AS total_flags
FROM tmp_flagged
GROUP BY rule_id;


-- ------------------------------------------------------------
-- 6. Number of flagged records in each rule/cell
-- ------------------------------------------------------------

DROP TABLE IF EXISTS tmp_rule_cells;

CREATE TEMP TABLE tmp_rule_cells AS
SELECT
    rule_id,
    cell_x,
    cell_y,
    COUNT(*) AS flagged_count
FROM tmp_flagged
WHERE cell_x IS NOT NULL
  AND cell_y IS NOT NULL
GROUP BY rule_id, cell_x, cell_y;


-- ------------------------------------------------------------
-- 7. Calculate spatial enrichment
--
-- enrichment =
--     flagged share of cell
--     --------------------
--     portfolio share of cell
--
-- >= 2 means the rule is at least twice as concentrated
-- in that cell as the portfolio itself.
--
-- Minimum 5 flagged records prevents tiny samples from
-- being called concentrated.
-- ------------------------------------------------------------

DROP TABLE IF EXISTS tmp_concentration;

CREATE TEMP TABLE tmp_concentration AS
SELECT
    rc.rule_id,
    rc.cell_x,
    rc.cell_y,
    rc.flagged_count,
    rt.total_flags,
    cb.portfolio_count,

    (
        (rc.flagged_count::numeric / NULLIF(rt.total_flags, 0))
        /
        (
            cb.portfolio_count::numeric
            /
            NULLIF(
                (SELECT COUNT(*) FROM tmp_portfolio_cells),
                0
            )
        )
    ) AS enrichment_ratio,

    (
        rc.flagged_count >= 5
        AND
        (
            (rc.flagged_count::numeric / NULLIF(rt.total_flags, 0))
            /
            (
                cb.portfolio_count::numeric
                /
                NULLIF(
                    (SELECT COUNT(*) FROM tmp_portfolio_cells),
                    0
                )
            )
        ) >= 2.0
    ) AS is_concentrated

FROM tmp_rule_cells rc
JOIN tmp_rule_totals rt
    ON rt.rule_id = rc.rule_id
JOIN tmp_cell_baseline cb
    ON cb.cell_x = rc.cell_x
   AND cb.cell_y = rc.cell_y;


-- ------------------------------------------------------------
-- 8. Insert record-level materiality results
-- ------------------------------------------------------------

INSERT INTO materiality_scores (
    row_id,
    rule_id,
    affects_hazard,
    affects_vulnerability,
    affects_financial,
    tiv_percentile,
    is_concentrated,
    changes_decision,
    priority
)
SELECT
    f.row_id,
    f.rule_id,

    f.affects_hazard,
    f.affects_vulnerability,
    f.affects_financial,

    f.tiv_percentile,

    COALESCE(c.is_concentrated, FALSE),

    -- --------------------------------------------------------
    -- Decision impact
    --
    -- A finding can change a decision when it affects a material
    -- axis and is either a top-10% TIV exposure or spatially
    -- concentrated.
    -- --------------------------------------------------------
    CASE
    WHEN (
        f.affects_hazard
        OR f.affects_vulnerability
        OR f.affects_financial
    )
    AND (
        f.tiv_percentile >= 90
        OR COALESCE(c.is_concentrated, FALSE)
    )
        THEN TRUE

    ELSE FALSE
    END AS changes_decision,

    -- --------------------------------------------------------
    -- Priority
    --
    -- P1:
    --   ERROR + HIGH/CRITICAL severity + material axis + top 10% TIV
    --
    -- P2:
    --   material axis + top 50% TIV
    --   OR spatial concentration
    --
    -- P3:
    --   everything else
    -- --------------------------------------------------------
    CASE

    -- P1:
    -- ERROR + HIGH/CRITICAL severity
    -- + materiality axis
    -- + validated TIV >= 90th percentile

    WHEN f.classification = 'ERROR'
         AND f.severity IN ('HIGH', 'CRITICAL')
         AND (
             f.affects_hazard
             OR f.affects_vulnerability
             OR f.affects_financial
         )
         AND f.tiv_percentile >= 90
        THEN 'P1'

    -- P2:
    -- Material axis + >= 50th percentile
    -- OR spatial concentration

    WHEN (
        (
            f.affects_hazard
            OR f.affects_vulnerability
            OR f.affects_financial
        )
        AND f.tiv_percentile >= 50
    )
    OR COALESCE(c.is_concentrated, FALSE)
        THEN 'P2'

    ELSE 'P3'

END AS priority

FROM tmp_flagged f
LEFT JOIN tmp_concentration c
    ON c.rule_id = f.rule_id
   AND c.cell_x = f.cell_x
   AND c.cell_y = f.cell_y;


-- ------------------------------------------------------------
-- 9. Basic QA
-- ------------------------------------------------------------

SELECT
    COUNT(*) AS materiality_records
FROM materiality_scores;


SELECT
    priority,
    COUNT(*) AS flags
FROM materiality_scores
GROUP BY priority
ORDER BY priority;


SELECT
    affects_hazard,
    affects_vulnerability,
    affects_financial,
    COUNT(*) AS flags
FROM materiality_scores
GROUP BY
    affects_hazard,
    affects_vulnerability,
    affects_financial
ORDER BY
    affects_hazard DESC,
    affects_vulnerability DESC,
    affects_financial DESC;
