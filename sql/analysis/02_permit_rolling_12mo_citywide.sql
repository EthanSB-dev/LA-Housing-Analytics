-- Time-series measure for the Executive Overview trend line: citywide
-- residential permit counts by month, with a trailing rolling 12-month
-- total to smooth out month-to-month noise.

WITH monthly AS (
    SELECT
        d.year_month,
        MIN(d.date_key) AS month_start,
        COUNT(*) AS residential_permit_count
    FROM marts.fact_building_permits f
    JOIN marts.dim_date d ON d.date_key = f.issue_date_key
    WHERE f.is_residential = TRUE
    GROUP BY d.year_month
)
SELECT
    year_month,
    residential_permit_count,
    SUM(residential_permit_count) OVER (
        ORDER BY month_start
        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
    ) AS rolling_12mo_total
FROM monthly
ORDER BY month_start;
