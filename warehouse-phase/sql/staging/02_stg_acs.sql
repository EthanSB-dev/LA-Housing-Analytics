-- Staging: cast ACS estimates to numeric and compute the derived percentage
-- indicators (rent burden %, renter share %, vacancy %) used downstream.
--
-- GRAIN: one row per census tract, LA County, 2019-2023 ACS 5-year release.

CREATE OR REPLACE TABLE staging.stg_acs_tract AS
SELECT
    state,
    county,
    tract,
    state || county || tract                                   AS tract_geoid,
    TRY_CAST(median_household_income AS DOUBLE)                AS median_household_income,
    TRY_CAST(median_gross_rent AS DOUBLE)                       AS median_gross_rent,
    TRY_CAST(rent_burden_total_renter_households AS DOUBLE)     AS rent_burden_total_renter_households,
    TRY_CAST(rent_burden_50pct_or_more AS DOUBLE)               AS rent_burden_50pct_or_more,

    -- Core affordability-pressure indicator: share of renter households
    -- paying 50%+ of income on rent ("severely rent burdened"). NULLIF
    -- guards against divide-by-zero in tracts with zero renter households.
    ROUND(
        TRY_CAST(rent_burden_50pct_or_more AS DOUBLE)
        / NULLIF(TRY_CAST(rent_burden_total_renter_households AS DOUBLE), 0) * 100,
        1
    )                                                            AS pct_severely_rent_burdened,

    TRY_CAST(tenure_total_occupied_units AS DOUBLE)             AS tenure_total_occupied_units,
    TRY_CAST(tenure_renter_occupied_units AS DOUBLE)            AS tenure_renter_occupied_units,
    ROUND(
        TRY_CAST(tenure_renter_occupied_units AS DOUBLE)
        / NULLIF(TRY_CAST(tenure_total_occupied_units AS DOUBLE), 0) * 100,
        1
    )                                                            AS pct_renter_occupied,

    TRY_CAST(occupancy_total_units AS DOUBLE)                   AS occupancy_total_units,
    TRY_CAST(occupancy_vacant_units AS DOUBLE)                  AS occupancy_vacant_units,
    ROUND(
        TRY_CAST(occupancy_vacant_units AS DOUBLE)
        / NULLIF(TRY_CAST(occupancy_total_units AS DOUBLE), 0) * 100,
        1
    )                                                            AS pct_vacant
FROM raw.acs_tract;
