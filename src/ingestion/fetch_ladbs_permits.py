"""
Fetch residential-relevant building permit records from the City of Los
Angeles Open Data portal (LADBS "Building Permits Issued from 2020 to
Present" dataset), published by the Dept. of Building & Safety.

Source: https://data.lacity.org/City-Infrastructure-Service-Requests/Building-and-Safety-Building-Permits-Issued-from-2/pi9x-tg5x
License: Creative Commons Attribution 4.0 International
Access:  Public Socrata API, dataset id "pi9x-tg5x"

WHY THIS SCRIPT HAS AN --inspect MODE:
We have not yet confirmed the exact column names this dataset uses (Socrata
field names are often abbreviated, e.g. "permit_type" vs "PERMIT_TYPE").
Rather than guessing and building the SQL schema around wrong field names,
--inspect pulls a small sample, prints the real columns, and saves them to
disk so we can look at them together before writing sql/schema/*.sql.

Usage:
    python src/ingestion/fetch_ladbs_permits.py --inspect
    python src/ingestion/fetch_ladbs_permits.py --full --start-date 2020-01-01
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sodapy import Socrata

DATASET_ID = "pi9x-tg5x"
DOMAIN = "data.lacity.org"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
PAGE_SIZE = 50_000  # Socrata's practical max per request; we paginate beyond this


def get_client() -> Socrata:
    """
    Build the Socrata client. The app token is optional -- without one you
    can still query the API, but requests may be rate-limited more
    aggressively. See .env.example for where to get a free token.
    """
    load_dotenv()  # reads the .env file in the project root, if present
    token = os.getenv("LA_OPEN_DATA_APP_TOKEN")
    if not token:
        print("No LA_OPEN_DATA_APP_TOKEN found in .env -- continuing without "
              "one. This works but may be rate-limited on larger pulls.")
    return Socrata(DOMAIN, token)


def inspect(client: Socrata) -> None:
    """Pull a handful of rows, print the real column names, save a sample."""
    sample = client.get(DATASET_ID, limit=5)
    if not sample:
        print("Got zero rows back -- something's wrong with the dataset id "
              "or connectivity. Check the dataset still exists at "
              "https://data.lacity.org/d/pi9x-tg5x")
        return

    columns = sorted(sample[0].keys())
    print(f"\nGot {len(sample)} sample rows with {len(columns)} columns:\n")
    for col in columns:
        print(f"  - {col}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    sample_path = RAW_DIR / "ladbs_permits_sample.json"
    with open(sample_path, "w") as f:
        json.dump(sample, f, indent=2)
    print(f"\nFull sample rows (with values) saved to: {sample_path}")
    print("Open that file and share the field names back in chat so we can "
          "map them into the data model accurately.")


def fetch_full(client: Socrata, start_date: str) -> None:
    """
    Pull all records with an issue date on/after start_date, paginating
    through Socrata's row limit, and save the combined result plus a
    metadata sidecar documenting exactly how/when it was retrieved.
    """
    where_clause = f"issue_date >= '{start_date}'"
    print(f"Querying with filter: {where_clause}")
    print("(If this errors with an 'invalid column' message, the real date "
          "column has a different name than 'issue_date' -- run --inspect "
          "first to confirm it.)")

    all_rows = []
    offset = 0
    while True:
        batch = client.get(
            DATASET_ID,
            where=where_clause,
            limit=PAGE_SIZE,
            offset=offset,
        )
        if not batch:
            break
        all_rows.extend(batch)
        print(f"  fetched {len(all_rows):,} rows so far...")
        offset += PAGE_SIZE

    if not all_rows:
        print("No rows returned. Nothing written.")
        return

    df = pd.DataFrame.from_records(all_rows)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "ladbs_permits_raw.csv"
    df.to_csv(out_path, index=False)

    # Metadata sidecar: documents exactly what we pulled, when, and how --
    # required by the project's own data-acquisition documentation standard.
    metadata = {
        "source_name": "LADBS Building Permits Issued from 2020 to Present",
        "source_url": f"https://data.lacity.org/d/{DATASET_ID}",
        "license": "Creative Commons Attribution 4.0 International",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "query_params": {"where": where_clause, "page_size": PAGE_SIZE},
        "row_count": len(df),
        "output_file": str(out_path.name),
    }
    meta_path = RAW_DIR / "ladbs_permits_raw.metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved {len(df):,} rows to {out_path}")
    print(f"Saved retrieval metadata to {meta_path}")

def explore_categories(client: Socrata) -> None:
    """
    Pull distinct values (with counts) for the fields that will drive our
    residential-permit filter, so we define that filter from real data
    instead of guessing. Uses Socrata's SoQL aggregation (group + count),
    which runs server-side -- fast, no need to download the whole dataset.
    """
    fields_to_explore = [
        "permit_type",
        "permit_sub_type",
        "use_desc",
        "permit_group",
        "business_unit",
    ]
    summary = {}
    for field in fields_to_explore:
        results = client.get(
            DATASET_ID,
            select=f"{field}, count(*) as permit_count",
            group=field,
            order="permit_count DESC",
            limit=200,
        )
        summary[field] = results
        print(f"\n=== {field} ({len(results)} distinct values) ===")
        for row in results:
            print(f"  {row.get(field, '(null)'):<40} {row['permit_count']}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "ladbs_category_exploration.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nFull results saved to: {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true",
                       help="Pull 5 sample rows and print real column names")
    mode.add_argument("--full", action="store_true",
                       help="Pull the full dataset from --start-date onward")
    mode.add_argument("--categories", action="store_true",
                       help="Show distinct values for the fields used to filter residential permits")
    parser.add_argument("--start-date", default="2020-01-01",
                         help="Earliest issue date to include (YYYY-MM-DD)")
    args = parser.parse_args()

    socrata_client = get_client()
    if args.inspect:
        inspect(socrata_client)
    elif args.categories:
        explore_categories(socrata_client)
    else:
        fetch_full(socrata_client, args.start_date)
