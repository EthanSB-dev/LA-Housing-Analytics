-- Staging: cast ACS estimates to numeric, convert Census's sentinel
-- "estimate not available" code to NULL, and compute the derived
-- percentage indicators (rent burden %, renter share %, vacancy %).
--
-- GRAIN: one row per census tract, LA County, 2019-2023 ACS 5-year release.
--
-- SENTINEL VALUE FIX: the Census Bureau uses -666666666 to mean "estimate
-- could not be computed" (typically a zero-population or too-small-sample
-- tract for that variable) -- NOT a real extreme value. Confirmed by
-- inspecting real pulled data: every affected tract showed EXACTLY
-- -666666666 for median_household_income. Left as a plain cast, this
-- sentinel would be treated as a genuine (and absurd) income figure and
-- badly distort any normalization or ranking downstream. NULLIF converts
-- it to NULL -- genuinely missing -- everywhere it could appear.

CREATE OR REPLACE TABLE staging.stg_acs_tract AS
WITH cast_and_cleaned AS (
    SELECT
        state,
        county,
        tract,
        NULLIF(TRY_CAST(median_household_income AS DOUBLE), -666666666)            AS median_household_income,
        NULLIF(TRY_CAST(median_gross_rent AS DOUBLE), -666666666)                  AS median_gross_rent,
        NULLIF(TRY_CAST(rent_burden_total_renter_households AS DOUBLE), -666666666) AS rent_burden_total_renter_households,
        NULLIF(TRY_CAST(rent_burden_50pct_or_more AS DOUBLE), -666666666)           AS rent_burden_50pct_or_more,
        NULLIF(TRY_CAST(tenure_total_occupied_units AS DOUBLE), -666666666)         AS tenure_total_occupied_units,
        NULLIF(TRY_CAST(tenure_renter_occupied_units AS DOUBLE), -666666666)        AS tenure_renter_occupied_units,
        NULLIF(TRY_CAST(occupancy_total_units AS DOUBLE), -666666666)               AS occupancy_total_units,
        NULLIF(TRY_CAST(occupancy_vacant_units AS DOUBLE), -666666666)              AS occupancy_vacant_units
    FROM raw.acs_tract
)
SELECT
    state,
    county,
    tract,
    state || county || tract                           AS tract_geoid,
    median_household_income,
    median_gross_rent,
    rent_burden_total_renter_households,
    rent_burden_50pct_or_more,
    ROUND(
        rent_burden_50pct_or_more / NULLIF(rent_burden_total_renter_households, 0) * 100,
        1
    )                                                    AS pct_severely_rent_burdened,
    tenure_total_occupied_units,
    tenure_renter_occupied_units,
    ROUND(
        tenure_renter_occupied_units / NULLIF(tenure_total_occupied_units, 0) * 100,
        1
    )                                                    AS pct_renter_occupied,
    occupancy_total_units,
    occupancy_vacant_units,
    ROUND(
        occupancy_vacant_units / NULLIF(occupancy_total_units, 0) * 100,
        1
    )                                                    AS pct_vacant
FROM cast_and_cleaned;
