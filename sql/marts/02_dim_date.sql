-- dim_date
-- GRAIN: one row per calendar day, 2020-01-01 through today.
-- PRIMARY KEY: date_key

CREATE OR REPLACE TABLE marts.dim_date AS
SELECT
    CAST(d AS DATE)          AS date_key,
    EXTRACT(YEAR FROM d)     AS year,
    EXTRACT(MONTH FROM d)    AS month,
    EXTRACT(QUARTER FROM d)  AS quarter,
    STRFTIME(d, '%Y-%m')     AS year_month
FROM RANGE(TIMESTAMP '2020-01-01', CURRENT_DATE, INTERVAL 1 DAY) AS t(d);
