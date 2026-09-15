"""
Fetch tract-level American Community Survey (ACS) 5-year estimates for
Los Angeles County, covering the affordability indicators the project needs:
rent burden, median income, median gross rent, tenure (renter vs owner), and
occupancy/vacancy.

Source: U.S. Census Bureau ACS 5-Year Detailed Tables API
Docs:   https://www.census.gov/data/developers/data-sets/acs-5year.html
Access: Free API, requires a key (see .env.example)
Geography: census tract, State=California (06), County=Los Angeles (037)

WHY THESE SPECIFIC TABLES:
  B25070  Gross rent as a % of household income  -> rent burden
  B19013  Median household income                -> income context
  B25064  Median gross rent                       -> rent level
  B25003  Tenure (owner vs. renter occupied)      -> renter share
  B25002  Occupancy status                        -> vacancy rate

Usage:
    python src/ingestion/fetch_census_acs.py --year 2023
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

STATE_FIPS = "06"    # California
COUNTY_FIPS = "037"  # Los Angeles County

# Variable codes pulled, with the "E" (estimate) suffix. Census also offers
# a matching "M" (margin of error) for each -- worth adding once we get to
# the data-quality / confidence-reporting stage, intentionally left out of
# this first pull to keep things simple.
VARIABLES = {
    "B19013_001E": "median_household_income",
    "B25064_001E": "median_gross_rent",
    "B25070_001E": "rent_burden_total_renter_households",
    "B25070_010E": "rent_burden_50pct_or_more",  # 50%+ of income on rent
    "B25003_001E": "tenure_total_occupied_units",
    "B25003_003E": "tenure_renter_occupied_units",
    "B25002_001E": "occupancy_total_units",
    "B25002_003E": "occupancy_vacant_units",
}


def fetch(year: int) -> pd.DataFrame:
    load_dotenv()
    api_key = os.getenv("CENSUS_API_KEY")
    if not api_key:
        raise SystemExit(
            "CENSUS_API_KEY not found in .env -- get a free key at "
            "https://api.census.gov/data/key_signup.html and add it to .env "
            "before running this script."
        )

    get_fields = ",".join(["NAME"] + list(VARIABLES.keys()))
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {
        "get": get_fields,
        "for": "tract:*",
        "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}",
        "key": api_key,
    }

    print(f"Requesting {url} for {len(VARIABLES)} variables across all LA "
          f"County tracts...")
    resp = requests.get(url, params=params, timeout=60)
    if resp.status_code != 200:
        raise SystemExit(
            f"Census API returned {resp.status_code}: {resp.text[:500]}\n"
            "Common cause: a variable code doesn't exist for this year's "
            "5-year release -- Census occasionally retires/renames table "
            "cells between releases."
        )

    rows = resp.json()
    header, *data_rows = rows
    df = pd.DataFrame(data_rows, columns=header)
    df = df.rename(columns=VARIABLES)
    return df


def main(year: int) -> None:
    df = fetch(year)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / f"acs_tract_la_county_{year}.csv"
    df.to_csv(out_path, index=False)

    metadata = {
        "source_name": f"ACS 5-Year Estimates ({year})",
        "source_url": f"https://api.census.gov/data/{year}/acs/acs5",
        "license": "Public domain (U.S. federal government work)",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "geography": "Census tract, Los Angeles County, CA (state=06, county=037)",
        "variables": VARIABLES,
        "row_count": len(df),
        "output_file": out_path.name,
    }
    meta_path = RAW_DIR / f"acs_tract_la_county_{year}.metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved {len(df):,} tract rows to {out_path}")
    print(f"Saved retrieval metadata to {meta_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2023,
                         help="Final year of the ACS 5-year release, e.g. "
                              "2023 for the 2019-2023 estimates")
    args = parser.parse_args()
    main(args.year)
