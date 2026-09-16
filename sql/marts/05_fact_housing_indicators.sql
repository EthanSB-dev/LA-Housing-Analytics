-- fact_housing_indicators
-- GRAIN: one row per census tract per ACS release (currently just the
-- 2019-2023 5-year release; re-running the ACS ingestion script with a
-- different --year will add another release here once we care about
-- comparing releases over time).
-- FOREIGN KEY: tract_geoid -> dim_geography

CREATE OR REPLACE TABLE marts.fact_housing_indicators AS
SELECT
    tract_geoid,
    2023                            AS acs_release_year,  -- final year of the 2019-2023 window
    median_household_income,
    median_gross_rent,
    pct_severely_rent_burdened,
    pct_renter_occupied,
    pct_vacant,
    tenure_total_occupied_units,
    occupancy_total_units
FROM staging.stg_acs_tract;