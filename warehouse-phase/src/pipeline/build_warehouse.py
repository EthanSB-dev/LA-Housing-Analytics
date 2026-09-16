"""
Build the DuckDB analytical warehouse from the raw CSVs pulled by the
ingestion scripts, then run a data-quality report so every exclusion is
counted and visible instead of silently dropped.

WHY THE RAW LOAD USES ALL_VARCHAR:
The raw layer's job is to preserve exactly what we pulled from the source,
with zero type-guessing -- DuckDB's automatic type inference on messy
government CSVs can misfire (e.g. treating a permit number as an integer
and losing leading structure). All real casting happens deliberately in
the staging SQL, where we can see and handle cast failures explicitly.

Usage:
    python src/pipeline/build_warehouse.py
"""

import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "processed" / "warehouse.duckdb"
RAW_DIR = ROOT / "data" / "raw"
SQL_STAGING_DIR = ROOT / "sql" / "staging"
SQL_MARTS_DIR = ROOT / "sql" / "marts"


def run_sql_dir(con: duckdb.DuckDBPyConnection, directory: Path) -> None:
    """Execute every .sql file in a directory, in filename order (hence the
    numeric prefixes like 01_, 02_ -- that ordering IS the dependency
    order, e.g. staging must exist before marts reference it)."""
    for sql_file in sorted(directory.glob("*.sql")):
        print(f"  running {sql_file.relative_to(ROOT)} ...")
        sql_text = sql_file.read_text()
        con.execute(sql_text)


def load_raw(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")
    con.execute("CREATE SCHEMA IF NOT EXISTS staging;")
    con.execute("CREATE SCHEMA IF NOT EXISTS marts;")

    permits_csv = RAW_DIR / "ladbs_permits_raw.csv"
    acs_csv = sorted(RAW_DIR.glob("acs_tract_la_county_*.csv"))
    if not permits_csv.exists():
        raise SystemExit(f"Missing {permits_csv} -- run the LADBS ingestion "
                          f"script first.")
    if not acs_csv:
        raise SystemExit("No acs_tract_la_county_*.csv found in data/raw -- "
                          "run the Census ingestion script first.")
    acs_csv = acs_csv[-1]  # most recent year if more than one exists

    print(f"Loading raw permits from {permits_csv.name} ...")
    con.execute(f"""
        CREATE OR REPLACE TABLE raw.ladbs_permits AS
        SELECT * FROM read_csv_auto('{permits_csv.as_posix()}', ALL_VARCHAR=TRUE);
    """)

    print(f"Loading raw ACS data from {acs_csv.name} ...")
    con.execute(f"""
        CREATE OR REPLACE TABLE raw.acs_tract AS
        SELECT * FROM read_csv_auto('{acs_csv.as_posix()}', ALL_VARCHAR=TRUE);
    """)

    n_permits = con.execute("SELECT COUNT(*) FROM raw.ladbs_permits").fetchone()[0]
    n_acs = con.execute("SELECT COUNT(*) FROM raw.acs_tract").fetchone()[0]
    print(f"  raw.ladbs_permits: {n_permits:,} rows")
    print(f"  raw.acs_tract:     {n_acs:,} rows")


def data_quality_report(con: duckdb.DuckDBPyConnection) -> None:
    print("\n=== DATA QUALITY REPORT ===")

    total = con.execute("SELECT COUNT(*) FROM staging.stg_permits").fetchone()[0]
    print(f"Total permit records (staging): {total:,}")

    null_date = con.execute(
        "SELECT COUNT(*) FROM staging.stg_permits WHERE issue_date IS NULL"
    ).fetchone()[0]
    print(f"  Excluded from fact table (unparseable/missing issue_date): {null_date:,}")

    dupes = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT permit_nbr, COUNT(*) c FROM staging.stg_permits
            GROUP BY permit_nbr HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    print(f"  Permit numbers appearing more than once (supplements/amendments, not deduplicated): {dupes:,}")

    missing_tract = con.execute("""
        SELECT COUNT(*) FROM staging.stg_permits
        WHERE tract_code IS NULL OR tract_raw IS NULL OR tract_raw = ''
    """).fetchone()[0]
    print(f"  Missing/blank tract number: {missing_tract:,}")

    failed_geo_join = con.execute("""
        SELECT COUNT(*) FROM marts.fact_building_permits
        WHERE tract_geoid IS NULL
    """).fetchone()[0]
    print(f"  Permits that didn't match any ACS tract (failed geographic join): {failed_geo_join:,}")

    residential_counts = con.execute("""
        SELECT is_residential, COUNT(*) FROM staging.stg_permits
        GROUP BY is_residential
    """).fetchall()
    print("  Residential filter split:")
    for is_res, cnt in residential_counts:
        label = "residential" if is_res else "non-residential"
        print(f"    {label}: {cnt:,}")

    bad_valuation = con.execute("""
        SELECT COUNT(*) FROM staging.stg_permits
        WHERE valuation IS NULL OR valuation < 0
    """).fetchone()[0]
    print(f"  Null or negative valuation: {bad_valuation:,}")

    print("\n=== MART ROW COUNTS ===")
    for table in ["dim_geography", "dim_date", "dim_permit_type",
                  "fact_building_permits", "fact_housing_indicators"]:
        n = con.execute(f"SELECT COUNT(*) FROM marts.{table}").fetchone()[0]
        print(f"  marts.{table}: {n:,} rows")


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))

    load_raw(con)

    print("\nRunning staging models...")
    run_sql_dir(con, SQL_STAGING_DIR)

    print("\nRunning marts models...")
    run_sql_dir(con, SQL_MARTS_DIR)

    data_quality_report(con)

    con.close()
    print(f"\nWarehouse built at: {DB_PATH}")


if __name__ == "__main__":
    main()
