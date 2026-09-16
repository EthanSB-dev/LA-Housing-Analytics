-- Staging: standardize types, derive the Census tract GEOID, and flag
-- residential permits.
--
-- GRAIN: one row per raw permit record. IMPORTANT -- permit_nbr is NOT
-- guaranteed unique here: LADBS issues supplemental/amendment permits that
-- reference an original permit_nbr with a different internal suffix (we
-- saw this in the initial sample: a "change contractor" supplement shared
-- most of its permit_nbr with the original project). This table does not
-- de-duplicate those rows -- see docs/data_dictionary.md for how this is
-- handled (or not yet handled) downstream.

CREATE OR REPLACE TABLE staging.stg_permits AS
SELECT
    permit_nbr,
    primary_address,
    zip_code,
    TRY_CAST(cd AS INTEGER)                           AS council_district,
    apn,
    zone,
    apc                                                AS area_planning_commission,
    cpa                                                AS community_plan_area,
    cnc                                                AS neighborhood_council,
    ct                                                 AS tract_raw,

    -- Derive the 6-digit Census tract code from LADBS's "1234.56" notation:
    -- left of the decimal is the base tract number (zero-padded to 4 digits),
    -- right of the decimal is the suffix (zero-padded to 2 digits). Combined
    -- with state=06 + county=037, this matches the "tract" field the Census
    -- API itself returns -- confirmed against real sample values (e.g. LADBS
    -- "2654.20" -> Census tract code "265420").
    LPAD(SPLIT_PART(ct, '.', 1), 4, '0')
        || LPAD(COALESCE(NULLIF(SPLIT_PART(ct, '.', 2), ''), '00'), 2, '0')
                                                        AS tract_code,

    permit_type,
    permit_sub_type,
    use_code,
    use_desc,
    TRY_CAST(issue_date AS TIMESTAMP)                  AS issue_date,
    TRY_CAST(status_date AS TIMESTAMP)                 AS status_date,
    status_desc,
    TRY_CAST(valuation AS DOUBLE)                      AS valuation,
    TRY_CAST(lat AS DOUBLE)                            AS latitude,
    TRY_CAST(lon AS DOUBLE)                            AS longitude,
    TRY_CAST(du_changed AS INTEGER)                    AS dwelling_units_changed,
    TRY_CAST(adu_changed AS INTEGER)                   AS adu_units_changed,
    TRY_CAST(square_footage AS DOUBLE)                 AS square_footage,
    work_desc,
    business_unit,

    -- Residential filter, confirmed against real category counts (not
    -- guessed): permit_sub_type alone still includes non-unit structures on
    -- a residential lot (pools, garages, grading), so use_desc must ALSO be
    -- an actual housing-unit type. "Accessory Living Quarters" and
    -- "Servant's Quarters" are deliberately excluded -- habitable rooms on
    -- an existing house, not separately created housing units. Full
    -- reasoning in docs/data_dictionary.md.
    CASE
        WHEN permit_sub_type IN ('1 or 2 Family Dwelling', 'Apartment')
         AND use_desc IN (
                'Dwelling - Single Family', 'Apartment',
                'Accessory Dwelling Unit', 'Duplex',
                'Condo-Multi Family', 'Condo-Single Family',
                'Condominium', 'Condo-Duplex',
                'Junior Accessory Dwelling Unit', 'Dwelling - multiple',
                'Apartment House', 'Joint Living and Working Quarters'
             )
        THEN TRUE
        ELSE FALSE
    END                                                 AS is_residential,

    -- Development-type grouping for the new/addition/alter/demolition
    -- breakdown the dashboard needs.
    CASE
        WHEN permit_type = 'Bldg-New'          THEN 'New Construction'
        WHEN permit_type = 'Bldg-Addition'     THEN 'Addition'
        WHEN permit_type = 'Bldg-Alter/Repair' THEN 'Alteration/Repair'
        WHEN permit_type = 'Bldg-Demolition'   THEN 'Demolition'
        WHEN permit_type = 'Bldg-Relocation'   THEN 'Relocation'
        ELSE 'Other/Non-Building'
    END                                                 AS development_category
FROM raw.ladbs_permits;
