-- Q5/Q6/Q9: Need-versus-development gap. Classifies each tract into one of
-- four quadrants by combining development activity with affordability
-- pressure.
--
-- Development activity = residential permits per 1,000 existing occupied
-- housing units, 2020-present cumulative (a RATE, so large and small
-- tracts are comparable -- not a raw count).
-- Affordability pressure = the equal-weight index (see
-- 03_affordability_pressure_index.sql -- kept in sync manually; if you
-- change the weighting there, update it here too).
--
-- "High" and "low" are relative to the CITYWIDE MEDIAN of other LA tracts,
-- not an absolute cutoff -- this is a transparent simplification for
-- prioritization discussion, not an official government threshold.

WITH dev_activity AS (
    SELECT
        f.tract_geoid,
        COUNT(*) AS residential_permits_total,
        h.occupancy_total_units,
        ROUND(1000.0 * COUNT(*) / NULLIF(h.occupancy_total_units, 0), 2)
            AS permits_per_1000_units
    FROM marts.fact_building_permits f
    JOIN marts.fact_housing_indicators h ON h.tract_geoid = f.tract_geoid
    WHERE f.is_residential = TRUE
    GROUP BY f.tract_geoid, h.occupancy_total_units
),
pressure AS (
    SELECT
        tract_geoid,
        ROUND((
              100.0 * (pct_severely_rent_burdened - MIN(pct_severely_rent_burdened) OVER ())
                  / NULLIF(MAX(pct_severely_rent_burdened) OVER () - MIN(pct_severely_rent_burdened) OVER (), 0)
            + 100.0 * (pct_renter_occupied - MIN(pct_renter_occupied) OVER ())
                  / NULLIF(MAX(pct_renter_occupied) OVER () - MIN(pct_renter_occupied) OVER (), 0)
            + (100.0 - 100.0 * (median_household_income - MIN(median_household_income) OVER ())
                  / NULLIF(MAX(median_household_income) OVER () - MIN(median_household_income) OVER (), 0))
        ) / 3.0, 1) AS pressure_score_equal_weight
    FROM marts.fact_housing_indicators
    WHERE pct_severely_rent_burdened IS NOT NULL
      AND pct_renter_occupied IS NOT NULL
      AND median_household_income IS NOT NULL
      AND tenure_total_occupied_units >= 100  -- same minimum-size floor as 03_affordability_pressure_index.sql
),
combined AS (
    SELECT
        g.tract_geoid,
        g.community_plan_area,
        g.council_district,
        d.permits_per_1000_units,
        p.pressure_score_equal_weight,
        MEDIAN(d.permits_per_1000_units) OVER () AS median_dev_rate,
        MEDIAN(p.pressure_score_equal_weight) OVER () AS median_pressure
    FROM marts.dim_geography g
    JOIN dev_activity d ON d.tract_geoid = g.tract_geoid
    JOIN pressure p ON p.tract_geoid = g.tract_geoid
)
SELECT
    tract_geoid,
    community_plan_area,
    council_district,
    permits_per_1000_units,
    pressure_score_equal_weight,
    CASE
        WHEN pressure_score_equal_weight >= median_pressure AND permits_per_1000_units <  median_dev_rate THEN 'High pressure / Low development (priority gap)'
        WHEN pressure_score_equal_weight >= median_pressure AND permits_per_1000_units >= median_dev_rate THEN 'High pressure / High development'
        WHEN pressure_score_equal_weight <  median_pressure AND permits_per_1000_units >= median_dev_rate THEN 'Lower pressure / High development'
        ELSE 'Lower pressure / Low development'
    END AS quadrant
FROM combined
ORDER BY
    CASE WHEN pressure_score_equal_weight >= median_pressure AND permits_per_1000_units < median_dev_rate THEN 0 ELSE 1 END,
    pressure_score_equal_weight DESC;
