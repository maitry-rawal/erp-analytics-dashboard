"""One-command setup: install deps, prepare data, run dashboard."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd, cwd=ROOT):
    print(f"  $ {cmd}")
    subprocess.check_call(cmd, shell=True, cwd=cwd)


def main():
    print("\n=== 1. Install dependencies ===")
    run(f"{sys.executable} -m pip install -r requirements.txt -q")

    csv_path = os.path.join(ROOT, "data", "raw", "production_runs.csv")
    if not os.path.exists(csv_path):
        print("\n=== 2. Download & prepare raw data ===")
        run(f"{sys.executable} etl/prepare_data.py")
    else:
        print("\n=== 2. Raw data already exists, skipping download ===")

    print("\n=== 3. Run ETL pipeline ===")
    run(f"{sys.executable} etl/pipeline.py")

    print("\n=== 4. Launch dashboard ===")
    run(f"{sys.executable} -m streamlit run app.py")


if __name__ == "__main__":
    main()
