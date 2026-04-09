"""ETL pipeline: read raw CSVs, compute metrics, load into SQLite."""

from __future__ import annotations

import os
import sqlite3
import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "manufacturing.db")

SKIP_FILES = {"ai4i2020.csv"}

IDEAL_CYCLE_TIME = 2.0  # minutes per unit


def extract() -> dict[str, pd.DataFrame]:
    tables = {}
    for fname in sorted(os.listdir(RAW_DIR)):
        if not fname.endswith(".csv") or fname in SKIP_FILES:
            continue
        name = fname.replace(".csv", "")
        tables[name] = pd.read_csv(os.path.join(RAW_DIR, fname))
        print(f"  extracted {name}: {len(tables[name])} rows")
    return tables


def transform(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    # production runs: compute OEE components
    pr = tables["production_runs"].copy()
    pr["availability"] = pr["actual_run_min"] / pr["planned_time_min"]
    pr["performance"] = ((pr["total_units"] * IDEAL_CYCLE_TIME) / pr["actual_run_min"]).clip(0, 1)
    pr["quality"] = pr["good_units"] / pr["total_units"]
    pr["oee"] = pr["availability"] * pr["performance"] * pr["quality"]
    tables["production_runs"] = pr

    # downtime events: add hours column
    dt = tables["downtime_events"].copy()
    dt["duration_hrs"] = (dt["duration_min"] / 60).round(3)
    tables["downtime_events"] = dt

    # quality inspections: first-pass yield and defect rate
    qi = tables["quality_inspections"].copy()
    qi["fpy"] = qi["passed_first"] / qi["total_inspected"]
    qi["defect_rate"] = qi["defects"] / qi["total_inspected"]
    tables["quality_inspections"] = qi

    return tables


def load(tables: dict[str, pd.DataFrame]):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    for name, df in tables.items():
        df.to_sql(name, conn, index=False, if_exists="replace")
        print(f"  loaded {name}: {len(df)} rows")
    conn.close()


def main():
    print("Extract...")
    tables = extract()
    print("Transform...")
    tables = transform(tables)
    print("Load...")
    load(tables)
    print(f"Pipeline complete -> {DB_PATH}")


if __name__ == "__main__":
    main()
