"""Download UCI AI4I 2020 dataset and reshape into manufacturing CSVs."""

import os
import numpy as np
import pandas as pd
from ucimlrepo import fetch_ucirepo

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

MACHINES = [f"CNC-{i:02d}" for i in range(1, 11)]
SHIFTS = ["Morning", "Afternoon", "Night"]
LINES = ["Line-A", "Line-B", "Line-C"]

# per-machine performance bias so some machines are better than others
MACHINE_EFFICIENCY = {
    "CNC-01": 0.92, "CNC-02": 0.88, "CNC-03": 0.85, "CNC-04": 0.78,
    "CNC-05": 0.90, "CNC-06": 0.82, "CNC-07": 0.75, "CNC-08": 0.87,
    "CNC-09": 0.80, "CNC-10": 0.70,
}

FAILURE_CATEGORIES = {
    "TWF": "Tool Wear",
    "HDF": "Heat Dissipation",
    "PWF": "Power",
    "OSF": "Overstrain",
    "RNF": "Random",
}

DOWNTIME_DETAILS = {
    "Tool Wear":        ["Excessive flank wear", "Chip buildup", "Tool breakage", "Insert crack"],
    "Heat Dissipation": ["Coolant flow low", "Ambient temp spike", "Spindle overheat"],
    "Power":            ["Voltage sag", "Phase imbalance", "Breaker trip"],
    "Overstrain":       ["Torque overload", "Feed rate exceeded", "Depth of cut error"],
    "Random":           ["Sensor glitch", "PLC fault", "Material jam", "Operator stop"],
}


def fetch_dataset():
    dataset = fetch_ucirepo(id=601)
    df = dataset.data.features.copy()
    df["Machine failure"] = dataset.data.targets["Machine failure"]
    for col in ["TWF", "HDF", "PWF", "OSF", "RNF"]:
        df[col] = dataset.data.targets[col]
    return df


def build_production_runs(df: pd.DataFrame, rng: np.random.RandomState) -> pd.DataFrame:
    n = len(df)
    start = pd.Timestamp("2025-07-01")
    dates = pd.date_range(start, periods=180, freq="D")

    # spread rows across 180 days
    date_idx = rng.choice(len(dates), size=n)
    date_col = dates[np.sort(date_idx)]

    machines = rng.choice(MACHINES, size=n)
    efficiencies = np.array([MACHINE_EFFICIENCY[m] for m in machines])

    planned = 480.0
    # tool wear reduces actual run time (mild effect)
    wear_penalty = (df["Tool wear"].values / 300.0).clip(0, 0.15)
    shift_noise = rng.uniform(-0.02, 0.02, size=n)
    actual_run = (planned * (1 - wear_penalty) * (efficiencies * 0.5 + 0.5) + shift_noise * planned).round(1)
    actual_run = np.clip(actual_run, 300, planned)

    # units from rpm; ideal cycle time in ETL is 2.0 min/unit
    rpm = df["Rotational speed"].values
    max_theoretical = actual_run / 2.0
    perf_noise = rng.uniform(0.78, 0.98, size=n) * (efficiencies * 0.3 + 0.7)
    total_units = (max_theoretical * perf_noise).astype(int)
    total_units = np.maximum(total_units, 1)

    # good units: subtract defects from failures and random quality loss
    failure = df["Machine failure"].values
    quality_loss = rng.uniform(0.01, 0.05, size=n)
    quality_loss = np.where(failure == 1, quality_loss + 0.06, quality_loss)
    good_units = (total_units * (1 - quality_loss)).astype(int)

    failure_type = []
    for _, row in df.iterrows():
        types = [k for k in ["TWF", "HDF", "PWF", "OSF", "RNF"] if row[k] == 1]
        failure_type.append(types[0] if types else "None")

    runs = pd.DataFrame({
        "run_id": [f"R{i+1:05d}" for i in range(n)],
        "date": date_col,
        "shift": rng.choice(SHIFTS, size=n),
        "machine": machines,
        "line": rng.choice(LINES, size=n),
        "product_type": df["Type"].values,
        "planned_time_min": planned,
        "actual_run_min": actual_run,
        "total_units": total_units,
        "good_units": good_units,
        "failure": failure,
        "failure_type": failure_type,
        "air_temp_k": df["Air temperature"].values,
        "process_temp_k": df["Process temperature"].values,
        "rpm": rpm,
        "torque_nm": df["Torque"].values,
        "tool_wear_min": df["Tool wear"].values,
    })
    return runs


def build_downtime_events(runs: pd.DataFrame, rng: np.random.RandomState) -> pd.DataFrame:
    failed = runs[runs["failure"] == 1].copy()
    events = []

    for i, (_, row) in enumerate(failed.iterrows()):
        cat = FAILURE_CATEGORIES.get(row["failure_type"], "Random")
        detail = rng.choice(DOWNTIME_DETAILS[cat])

        # duration scales with tool wear and torque
        base_dur = rng.uniform(15, 90)
        wear_mult = 1 + (row["tool_wear_min"] / 250)
        duration = round(base_dur * wear_mult, 1)

        dtype = "Unplanned" if cat != "Tool Wear" else rng.choice(
            ["Planned", "Unplanned"], p=[0.3, 0.7]
        )

        events.append({
            "event_id": f"D{i+1:04d}",
            "date": row["date"],
            "machine": row["machine"],
            "category": cat,
            "detail": detail,
            "duration_min": duration,
            "downtime_type": dtype,
        })

    return pd.DataFrame(events)


def build_quality_inspections(runs: pd.DataFrame, rng: np.random.RandomState) -> pd.DataFrame:
    # aggregate per date-machine-line-product
    grouped = runs.groupby(["date", "machine", "line", "product_type"]).agg(
        total_inspected=("total_units", "sum"),
        passed_first=("good_units", "sum"),
    ).reset_index()

    grouped["defects"] = grouped["total_inspected"] - grouped["passed_first"]
    grouped.insert(0, "inspection_id", [f"Q{i+1:05d}" for i in range(len(grouped))])

    return grouped


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    rng = np.random.RandomState(42)

    print("Downloading UCI dataset 601...")
    df = fetch_dataset()
    print(f"  {len(df)} records fetched")

    # save original for reference
    df.to_csv(os.path.join(RAW_DIR, "ai4i2020.csv"), index=False)

    print("Building production_runs...")
    runs = build_production_runs(df, rng)
    runs.to_csv(os.path.join(RAW_DIR, "production_runs.csv"), index=False)
    print(f"  {len(runs)} rows")

    print("Building downtime_events...")
    downtime = build_downtime_events(runs, rng)
    downtime.to_csv(os.path.join(RAW_DIR, "downtime_events.csv"), index=False)
    print(f"  {len(downtime)} rows")

    print("Building quality_inspections...")
    quality = build_quality_inspections(runs, rng)
    quality.to_csv(os.path.join(RAW_DIR, "quality_inspections.csv"), index=False)
    print(f"  {len(quality)} rows")

    print("Done. CSVs saved to", RAW_DIR)


if __name__ == "__main__":
    main()
