-- Q1: Which tracts have the fastest growth/decline in residential permit
-- activity over time? Year-over-year % change in residential permit
-- counts per tract.
--
-- CAVEATS:
-- - 2020-2021 tract-level counts are undercounted relative to 2023+ due to
--   the tract-match rate limitation (see docs/data_dictionary.md) --
--   read early-year growth rates with that in mind.
-- - 2026 is a partial year as of this pull; its year-over-year figure will
--   understate full-year activity.
-- - Tracts with fewer than 5 permits in the prior year are excluded from
--   the ranking: going from 1 permit to 3 is "200% growth" but reflects
--   noise, not a meaningful trend.

WITH yearly_counts AS (
    SELECT
        f.tract_geoid,
        d.year,
        COUNT(*) AS residential_permit_count
    FROM marts.fact_building_permits f
    JOIN marts.dim_date d ON d.date_key = f.issue_date_key
    WHERE f.is_residential = TRUE
      AND f.tract_geoid IS NOT NULL
    GROUP BY f.tract_geoid, d.year
),
with_growth AS (
    SELECT
        tract_geoid,
        year,
        residential_permit_count,
        LAG(residential_permit_count) OVER (
            PARTITION BY tract_geoid ORDER BY year
        ) AS prior_year_count
    FROM yearly_counts
)
SELECT
    g.tract_geoid,
    g.community_plan_area,
    g.council_district,
    w.year,
    w.residential_permit_count,
    w.prior_year_count,
    ROUND(100.0 * (w.residential_permit_count - w.prior_year_count)
          / NULLIF(w.prior_year_count, 0), 1) AS pct_change_yoy,
    RANK() OVER (
        PARTITION BY w.year
        ORDER BY (w.residential_permit_count - w.prior_year_count) / NULLIF(w.prior_year_count, 0) DESC
    ) AS growth_rank
FROM with_growth w
JOIN marts.dim_geography g ON g.tract_geoid = w.tract_geoid
WHERE w.prior_year_count IS NOT NULL
  AND w.prior_year_count >= 5
ORDER BY w.year DESC, growth_rank
LIMIT 200;
