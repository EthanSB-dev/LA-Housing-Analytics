"""
Export clean, Tableau-ready CSV extracts from the DuckDB warehouse into
dashboard/data/.

WHY CSVs INSTEAD OF CONNECTING TABLEAU DIRECTLY TO DUCKDB:
Tableau Public's connector list doesn't include DuckDB, and even if it
did, a live database connection isn't how Tableau Public dashboards get
distributed anyway -- Tableau Public embeds the data INTO the published
workbook. CSVs are simple, inspectable, and exactly what Tableau Public
expects. These CSVs are small, aggregated extracts (not the raw 412K-row
permit dump), so they're also fine to commit to git for reproducibility.

WHY EACH FILE IS SHAPED THE WAY IT IS:
Tableau works best with either a single flat table per chart, or a small
number of tables joined inside Tableau itself. Rather than making you
recreate joins across dim/fact tables inside Tableau on your first ever
session with it, each export below is pre-joined and shaped for one
specific dashboard page, so you can drag fields straight onto a chart.

Usage:
    python src/pipeline/export_for_tableau.py
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "processed" / "warehouse.duckdb"
OUT_DIR = ROOT / "dashboard" / "data"


def export(con, out_dir: Path, name: str, sql: str) -> None:
    df = con.execute(sql).df()
    out_path = out_dir / f"{name}.csv"
    df.to_csv(out_path, index=False)
    print(f"  {name}.csv: {len(df):,} rows -> {out_path}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    run_exports(con, OUT_DIR)
    con.close()
    print(f"\nAll extracts written to: {OUT_DIR}")


def run_exports(con, out_dir: Path) -> None:
    print("Exporting Tableau-ready extracts...")

    # --- Executive Overview page: citywide trend line ---
    export(con, out_dir, "citywide_permit_trend", """
        WITH monthly AS (
            SELECT
                d.year_month,
                MIN(d.date_key) AS month_start,
                COUNT(*) AS residential_permit_count,
                SUM(f.valuation) AS total_valuation
            FROM marts.fact_building_permits f
            JOIN marts.dim_date d ON d.date_key = f.issue_date_key
            WHERE f.is_residential = TRUE
            GROUP BY d.year_month
        )
        SELECT
            year_month,
            month_start,
            residential_permit_count,
            total_valuation,
            SUM(residential_permit_count) OVER (
                ORDER BY month_start ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
            ) AS rolling_12mo_total
        FROM monthly
        ORDER BY month_start;
    """)

    # --- Development Activity page: growth by tract/year, with geography labels ---
    export(con, out_dir, "tract_growth_yearly", """
        WITH yearly_counts AS (
            SELECT f.tract_geoid, d.year, COUNT(*) AS residential_permit_count
            FROM marts.fact_building_permits f
            JOIN marts.dim_date d ON d.date_key = f.issue_date_key
            WHERE f.is_residential = TRUE AND f.tract_geoid IS NOT NULL
            GROUP BY f.tract_geoid, d.year
        ),
        with_growth AS (
            SELECT
                tract_geoid, year, residential_permit_count,
                LAG(residential_permit_count) OVER (PARTITION BY tract_geoid ORDER BY year) AS prior_year_count
            FROM yearly_counts
        )
        SELECT
            g.tract_geoid, g.community_plan_area, g.council_district,
            w.year, w.residential_permit_count, w.prior_year_count,
            ROUND(100.0 * (w.residential_permit_count - w.prior_year_count)
                  / NULLIF(w.prior_year_count, 0), 1) AS pct_change_yoy
        FROM with_growth w
        JOIN marts.dim_geography g ON g.tract_geoid = w.tract_geoid
        ORDER BY w.year, g.tract_geoid;
    """)

    # --- Development Activity page: permit-type mix by year (new/addition/alter/demolition) ---
    export(con, out_dir, "permit_type_breakdown_by_year", """
        SELECT
            d.year,
            f.development_category,
            f.is_residential,
            COUNT(*) AS permit_count,
            SUM(f.valuation) AS total_valuation
        FROM marts.fact_building_permits f
        JOIN marts.dim_date d ON d.date_key = f.issue_date_key
        GROUP BY d.year, f.development_category, f.is_residential
        ORDER BY d.year, f.development_category;
    """)

    # --- Development Activity page: point-level map (lat/lon needs no geocoding in Tableau) ---
    export(con, out_dir, "residential_permit_points", """
        SELECT
            p.permit_nbr, p.issue_date, p.latitude, p.longitude,
            p.development_category, p.valuation,
            p.community_plan_area, p.council_district
        FROM staging.stg_permits p
        WHERE p.is_residential = TRUE
          AND p.latitude IS NOT NULL AND p.longitude IS NOT NULL
          AND p.issue_date IS NOT NULL;
    """)

    # --- Affordability Pressure page: pressure index + geography labels ---
    export(con, out_dir, "affordability_pressure_by_tract", """
        WITH normalized AS (
            SELECT
                tract_geoid, pct_severely_rent_burdened, pct_renter_occupied,
                median_household_income, median_gross_rent,
                ROUND(100.0 * (pct_severely_rent_burdened - MIN(pct_severely_rent_burdened) OVER ())
                    / NULLIF(MAX(pct_severely_rent_burdened) OVER () - MIN(pct_severely_rent_burdened) OVER (), 0), 1)
                    AS rent_burden_norm,
                ROUND(100.0 * (pct_renter_occupied - MIN(pct_renter_occupied) OVER ())
                    / NULLIF(MAX(pct_renter_occupied) OVER () - MIN(pct_renter_occupied) OVER (), 0), 1)
                    AS renter_share_norm,
                ROUND(100.0 - 100.0 * (median_household_income - MIN(median_household_income) OVER ())
                    / NULLIF(MAX(median_household_income) OVER () - MIN(median_household_income) OVER (), 0), 1)
                    AS low_income_norm
            FROM marts.fact_housing_indicators
            WHERE pct_severely_rent_burdened IS NOT NULL
              AND pct_renter_occupied IS NOT NULL
              AND median_household_income IS NOT NULL
              AND tenure_total_occupied_units >= 100
        )
        SELECT
            g.tract_geoid, g.community_plan_area, g.council_district,
            n.pct_severely_rent_burdened, n.pct_renter_occupied,
            n.median_household_income, n.median_gross_rent,
            ROUND((n.rent_burden_norm + n.renter_share_norm + n.low_income_norm) / 3.0, 1)
                AS pressure_score_equal_weight,
            ROUND(n.rent_burden_norm * 0.5 + n.renter_share_norm * 0.25 + n.low_income_norm * 0.25, 1)
                AS pressure_score_burden_weighted
        FROM normalized n
        JOIN marts.dim_geography g ON g.tract_geoid = n.tract_geoid
        ORDER BY pressure_score_equal_weight DESC;
    """)

    # --- Need-vs-Development Gap page: quadrant scatter (no map needed --
    # this is a plain X/Y scatter, works in Tableau with zero geocoding) ---
    export(con, out_dir, "need_vs_development_gap", (ROOT / "sql" / "analysis" / "04_need_vs_development_gap.sql").read_text())


if __name__ == "__main__":
    main()
