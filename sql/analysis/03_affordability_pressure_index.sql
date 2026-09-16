-- Q4: Which tracts show the highest affordability pressure?
--
-- Explainable, min-max normalized (0-100) index built from three ACS
-- indicators. This is an INDEPENDENT construction from public data, not
-- an official government metric -- documented fully in docs/methodology.md,
-- including this sensitivity check comparing two weighting schemes.
--
-- MINIMUM-SIZE FLOOR: tracts with fewer than 100 occupied housing units
-- are excluded. Several near-empty tracts (some with fewer than 20 units,
-- some with zero -- consistent with the Census's special-land-use tract
-- convention for parks/industrial/institutional land) were producing
-- extreme, statistically noisy percentages (e.g. "100% rent burdened"
-- from a single household) that dominated the top of the ranking without
-- reflecting any real neighborhood-level pattern. 100 units is a
-- judgment call, not an official standard -- documented in
-- docs/methodology.md, easy to change in the WHERE clause below.

WITH normalized AS (
    SELECT
        tract_geoid,
        pct_severely_rent_burdened,
        pct_renter_occupied,
        median_household_income,
        ROUND(100.0 * (pct_severely_rent_burdened - MIN(pct_severely_rent_burdened) OVER ())
            / NULLIF(MAX(pct_severely_rent_burdened) OVER () - MIN(pct_severely_rent_burdened) OVER (), 0), 1)
            AS rent_burden_norm,
        ROUND(100.0 * (pct_renter_occupied - MIN(pct_renter_occupied) OVER ())
            / NULLIF(MAX(pct_renter_occupied) OVER () - MIN(pct_renter_occupied) OVER (), 0), 1)
            AS renter_share_norm,
        -- Income is inverted (100 - x) so LOWER income maps to HIGHER
        -- pressure, consistent with the other two components.
        ROUND(100.0 - 100.0 * (median_household_income - MIN(median_household_income) OVER ())
            / NULLIF(MAX(median_household_income) OVER () - MIN(median_household_income) OVER (), 0), 1)
            AS low_income_norm
    FROM marts.fact_housing_indicators
    WHERE pct_severely_rent_burdened IS NOT NULL
      AND pct_renter_occupied IS NOT NULL
      AND median_household_income IS NOT NULL
      AND tenure_total_occupied_units >= 100
)
SELECT
    tract_geoid,
    rent_burden_norm,
    renter_share_norm,
    low_income_norm,
    -- Scheme A: equal weight across all three components
    ROUND((rent_burden_norm + renter_share_norm + low_income_norm) / 3.0, 1)
        AS pressure_score_equal_weight,
    RANK() OVER (ORDER BY (rent_burden_norm + renter_share_norm + low_income_norm) / 3.0 DESC)
        AS pressure_rank_equal_weight,
    -- Scheme B: rent burden weighted higher -- it's the most direct
    -- affordability outcome; renter share and income are contributing
    -- context, not the outcome itself.
    ROUND(rent_burden_norm * 0.5 + renter_share_norm * 0.25 + low_income_norm * 0.25, 1)
        AS pressure_score_burden_weighted,
    RANK() OVER (ORDER BY rent_burden_norm * 0.5 + renter_share_norm * 0.25 + low_income_norm * 0.25 DESC)
        AS pressure_rank_burden_weighted
FROM normalized
ORDER BY pressure_score_equal_weight DESC;
