# Data Sources (verified)

This file documents every data source used in the project, per our own
standard: source URL, coverage, license, and known caveats -- recorded at
the time of verification, before ingestion, so nothing is assumed.

## 1. LADBS Building Permits (City of Los Angeles Open Data Portal)

- **Dataset**: "Building and Safety - Building Permits Issued from 2020 to Present (N)"
- **URL**: https://data.lacity.org/City-Infrastructure-Service-Requests/Building-and-Safety-Building-Permits-Issued-from-2/pi9x-tg5x
- **Socrata dataset ID**: `pi9x-tg5x`
- **Publisher**: LA Dept. of Building & Safety (LADBS)
- **License**: Creative Commons Attribution 4.0 International
- **Coverage**: 2020-present (a companion dataset, id `dyxf-7hc4`, covers
  2010-2019 if we extend the time window later)
- **Access method**: Public Socrata API, optional free app token
- **Known fields (unconfirmed until --inspect run)**: address, ZIP code,
  assessor parcel number (APN), zoning, Community Plan Area, Neighborhood
  Council area, permit type/sub-type, valuation, issue date, latitude/longitude
- **Caveat**: this is *permit* activity, not completed/occupied housing.
  A permit can be issued and never result in finished construction. We will
  say "permitted units," never "new housing built," anywhere this data
  is used.

## 2. U.S. Census Bureau ACS 5-Year Estimates

- **URL**: https://api.census.gov/data/2023/acs/acs5
- **Publisher**: U.S. Census Bureau
- **License**: Public domain (federal government work)
- **Coverage**: 2019-2023 5-year estimates (most recent available at time
  of writing), tract-level, Los Angeles County (state=06, county=037)
- **Access method**: Public API, requires a free API key
- **Tables used**:
  - B25070 - Gross rent as % of household income (rent burden)
  - B19013 - Median household income
  - B25064 - Median gross rent
  - B25003 - Tenure (owner- vs renter-occupied)
  - B25002 - Occupancy status (for vacancy rate)
- **Caveat**: 5-year *estimates*, not point-in-time counts -- each "year"
  is actually an average over 5 years, which smooths out short-term change.
  This matters when comparing to year-over-year permit trends, which are
  not smoothed the same way. We will state this explicitly wherever the two
  are compared.

## Deferred for later phases

- **LAHD affordable-housing production data**: exists but is distributed
  mainly via dashboards/PDFs rather than a clean queryable API. Revisit
  after the MVP is working end-to-end.
- **LA County Open Data** (parcels, homelessness indicators): not yet
  evaluated for this project; revisit if council-district or county-wide
  scope is added later.
- **Census tract boundary shapefiles (TIGER/Line)**: needed for the
  permit-to-tract spatial join. Not pulled yet -- comes in the geospatial
  preparation phase, alongside geopandas.
