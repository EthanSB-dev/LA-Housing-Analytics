-- fact_building_permits
-- GRAIN: one row per raw permit record (see the grain caveat in
-- sql/staging/01_stg_permits.sql -- supplemental/amendment permits are
-- NOT collapsed into their original permit here).
-- FOREIGN KEYS: tract_geoid -> dim_geography, permit_type -> dim_permit_type,
--               issue_date_key -> dim_date

CREATE OR REPLACE TABLE marts.fact_building_permits AS
SELECT
    p.permit_nbr,
    CAST(p.issue_date AS DATE)        AS issue_date_key,
    g.tract_geoid,
    p.tract_code,
    p.council_district                AS permit_council_district,
    p.permit_type,
    p.development_category,
    p.is_residential,
    p.valuation,
    p.dwelling_units_changed,
    p.adu_units_changed,
    p.square_footage
FROM staging.stg_permits p
LEFT JOIN marts.dim_geography g
    ON g.tract_code = p.tract_code
WHERE p.issue_date IS NOT NULL;  -- rows with an unparseable/missing issue
                                  -- date can't be placed in time; excluded
                                  -- here and counted in the data-quality
                                  -- report, not silently dropped.
