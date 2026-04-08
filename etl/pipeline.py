"""
Manufacturing ETL Pipeline
Extracts production data from ERP systems, transforms for analytics,
and loads into the data warehouse for Power BI dashboards.
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the ETL pipeline."""
    source_type: str  # "csv", "database", "api"
    source_path: str
    output_path: str = "output"
    date_range_days: int = 30


class ManufacturingETL:
    """ETL pipeline for manufacturing production data."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.output_dir = Path(config.output_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract(self) -> dict[str, pd.DataFrame]:
        """Extract raw data from source systems."""
        logger.info(f"Extracting data from {self.config.source_type}: {self.config.source_path}")

        source = Path(self.config.source_path)
        tables = {}

        for csv_file in source.glob("*.csv"):
            table_name = csv_file.stem
            df = pd.read_csv(csv_file, parse_dates=True)
            tables[table_name] = df
            logger.info(f"  Extracted {table_name}: {len(df)} rows")

        return tables

    def transform(self, tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """Transform raw data into analytics-ready format."""
        logger.info("Transforming data...")
        results = {}

        if "production_runs" in tables:
            results["fact_production"] = self._transform_production(tables["production_runs"])

        if "downtime_events" in tables:
            results["fact_downtime"] = self._transform_downtime(tables["downtime_events"])

        if "quality_inspections" in tables:
            results["fact_quality"] = self._transform_quality(tables["quality_inspections"])

        return results

    def _transform_production(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate OEE components from production run data."""
        df = df.copy()

        df["availability"] = df["actual_run_time"] / df["planned_production_time"]
        df["performance"] = (
            df["ideal_cycle_time"] * df["total_units"]
        ) / (df["actual_run_time"] * 60)
        df["quality"] = df["good_units"] / df["total_units"]
        df["oee"] = df["availability"] * df["performance"] * df["quality"]

        df["oee_class"] = pd.cut(
            df["oee"],
            bins=[0, 0.40, 0.65, 0.85, 1.0],
            labels=["Critical", "Below Average", "Typical", "World Class"],
        )

        logger.info(f"  Production: avg OEE = {df['oee'].mean():.1%}")
        return df

    def _transform_downtime(self, df: pd.DataFrame) -> pd.DataFrame:
        """Categorize and aggregate downtime events."""
        df = df.copy()
        df["duration_hours"] = df["duration_minutes"] / 60

        # Pareto ranking
        category_totals = df.groupby("reason_category")["duration_hours"].sum()
        category_totals = category_totals.sort_values(ascending=False)
        cumulative = category_totals.cumsum() / category_totals.sum() * 100

        df["is_top_80_pct"] = df["reason_category"].isin(
            cumulative[cumulative <= 80].index
        )

        logger.info(f"  Downtime: {len(df)} events, {df['duration_hours'].sum():.0f} total hours")
        return df

    def _transform_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process quality inspection results."""
        df = df.copy()
        df["first_pass_yield"] = df["passed_first"] / df["total_inspected"]
        df["defect_rate"] = 1 - df["first_pass_yield"]

        logger.info(f"  Quality: avg FPY = {df['first_pass_yield'].mean():.1%}")
        return df

    def load(self, tables: dict[str, pd.DataFrame]) -> None:
        """Load transformed data to output."""
        logger.info(f"Loading {len(tables)} tables to {self.output_dir}")

        for name, df in tables.items():
            output_file = self.output_dir / f"{name}.parquet"
            df.to_parquet(output_file, index=False)
            logger.info(f"  Saved {name}: {len(df)} rows → {output_file}")

    def run(self) -> None:
        """Execute the full ETL pipeline."""
        start = datetime.now()
        logger.info(f"Pipeline started at {start}")

        raw = self.extract()
        transformed = self.transform(raw)
        self.load(transformed)

        elapsed = datetime.now() - start
        logger.info(f"Pipeline completed in {elapsed.total_seconds():.1f}s")


if __name__ == "__main__":
    config = PipelineConfig(
        source_type="csv",
        source_path="data/sample",
        output_path="output",
    )
    pipeline = ManufacturingETL(config)
    pipeline.run()
