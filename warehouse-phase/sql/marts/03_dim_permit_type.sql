-- dim_permit_type
-- GRAIN: one row per distinct (permit_type, development_category,
-- is_residential) combination actually observed in the data.
-- PRIMARY KEY: permit_type

CREATE OR REPLACE TABLE marts.dim_permit_type AS
SELECT DISTINCT
    permit_type,
    development_category,
    is_residential
FROM staging.stg_permits;
