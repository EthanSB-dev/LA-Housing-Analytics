-- dim_geography
-- GRAIN: one row per census tract (matches ACS's 2,498 LA County tracts).
-- PRIMARY KEY: tract_geoid
--
-- Council district / community plan area / neighborhood council / area
-- planning commission come from the PERMIT data, not from ACS -- ACS
-- doesn't publish these. Since tract boundaries don't align perfectly with
-- council district boundaries, a handful of tracts have permits tagged
-- with more than one label (edge cases near a boundary). We take the most
-- frequently occurring label per tract and document this as a known
-- simplification, not an authoritative boundary assignment.
--
-- Tracts with ZERO permits in our data will have NULL geography labels
-- here (no permit ever tagged them) -- that's expected and meaningful:
-- a tract with high rent burden and no permit activity at all is exactly
-- the kind of gap this project is trying to surface, not a data error.

CREATE OR REPLACE TABLE marts.dim_geography AS
WITH permit_labels AS (
    SELECT
        tract_code,
        council_district,
        community_plan_area,
        neighborhood_council,
        area_planning_commission,
        COUNT(*) AS label_frequency
    FROM staging.stg_permits
    WHERE tract_code IS NOT NULL
    GROUP BY tract_code, council_district, community_plan_area,
             neighborhood_council, area_planning_commission
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY tract_code ORDER BY label_frequency DESC
           ) AS rn
    FROM permit_labels
)
SELECT
    a.tract_geoid,
    a.tract                            AS tract_code,
    r.council_district,
    r.community_plan_area,
    r.neighborhood_council,
    r.area_planning_commission
FROM staging.stg_acs_tract a
LEFT JOIN ranked r
    ON r.tract_code = a.tract
   AND r.rn = 1;
