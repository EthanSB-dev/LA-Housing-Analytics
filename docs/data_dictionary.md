# Data Dictionary

## staging.stg_permits
Grain: one row per raw LADBS permit record. `permit_nbr` is NOT guaranteed
unique -- supplemental/amendment permits (e.g. a "change contractor" filing)
can share most of a permit_nbr with an original project. Not deduplicated
in this table; see the data-quality report printed by
`src/pipeline/build_warehouse.py` for how many such repeats exist.

**tract_code derivation**: LADBS reports census tract as e.g. `"2654.20"`.
The 6-digit Census GEOID tract segment is
`LPAD(integer_part, 4, '0') || LPAD(decimal_part, 2, '0')`, confirmed against
a real sample value from the source data.

**is_residential filter**: `permit_sub_type` alone is insufficient --
non-housing structures on a residential lot (pools, garages, grading) also
carry `permit_sub_type = '1 or 2 Family Dwelling'`. A permit counts as
residential only if `permit_sub_type` is Dwelling-related **and**
`use_desc` is one of:
Dwelling - Single Family, Apartment, Accessory Dwelling Unit, Duplex,
Condo-Multi Family, Condo-Single Family, Condominium, Condo-Duplex,
Junior Accessory Dwelling Unit, Dwelling - multiple, Apartment House,
Joint Living and Working Quarters.

**Deliberately excluded** (habitable rooms, not separately created housing
units): Accessory Living Quarters, Servant's Quarters. If a stakeholder
disagrees with this call, it's a one-line change to the `use_desc IN (...)`
list in `sql/staging/01_stg_permits.sql`.

## staging.stg_acs_tract
Grain: one row per census tract, LA County, 2019-2023 ACS 5-year estimates.
`pct_severely_rent_burdened` = renter households paying 50%+ of income on
rent, as a % of all renter households in the tract -- the project's primary
affordability-pressure indicator.

## marts.dim_geography
Grain: one row per ACS census tract (2,498 rows). PK: `tract_geoid`.
Council district / community plan area / neighborhood council / area
planning commission come from permit data, not ACS. Where a tract's permits
carried more than one label for these fields (boundary edge cases), the
most frequent label is used -- **this is a simplification, not an
authoritative boundary assignment.** Tracts with zero permits will have
NULL values here, which is meaningful (no development activity recorded),
not an error.

## marts.dim_date
Grain: one calendar day, 2020-01-01 to today. PK: `date_key`.

## marts.dim_permit_type
Grain: one row per distinct (permit_type, development_category,
is_residential) combination actually present in the data. PK: `permit_type`.

## marts.fact_building_permits
Grain: one row per permit record with a parseable issue date (see grain
caveat on `stg_permits` above -- supplements/amendments not collapsed).
FKs: `tract_geoid` -> dim_geography, `permit_type` -> dim_permit_type,
`issue_date_key` -> dim_date.

Permits missing an issue date are excluded here and counted explicitly in
the data-quality report -- not silently dropped without a record of it.

## marts.fact_housing_indicators
Grain: one row per tract per ACS release (currently only 2019-2023).
FK: `tract_geoid` -> dim_geography.

## Known limitation: tract-match rate improves over time (investigated)

~7% of permits (28,740 of 412,133) don't match any ACS census tract on
`tract_code`. This is NOT a formatting bug -- unmatched codes are
well-formed 6-digit values, confirmed by direct inspection. The mismatch
rate is NOT flat over time, which rules out a one-time tract-boundary
redraw as the sole explanation:

| Year | Permits | Unmatched | % Unmatched |
|------|---------|-----------|--------------|
| 2020 | 51,894  | 8,106     | 15.6% |
| 2021 | 57,416  | 8,674     | 15.1% |
| 2022 | 65,328  | 7,965     | 12.2% |
| 2023 | 64,154  | 2,039     | 3.2%  |
| 2024 | 64,768  | 996       | 1.5%  |
| 2025 | 63,352  | 589       | 0.9%  |
| 2026 | 45,169  | 319       | 0.7%  |

The smooth decline (rather than a sharp jump) suggests LADBS's own
tract-tagging accuracy improved gradually over this period -- plausibly a
geocoding system change or backfilled corrections on their end. This is an
inference from the pattern, not a confirmed root cause; LADBS's internal
systems aren't something we have visibility into.

**Practical handling**: citywide and permit-type-level analysis uses all
412,133 permits and is unaffected. Tract-level analysis uses only matched
permits, and 2020-2021 tract-level figures should be read as undercounts
relative to 2023+ -- called out explicitly wherever tract-level
year-over-year comparisons are shown (dashboard "Data and Limitations"
page, README).
