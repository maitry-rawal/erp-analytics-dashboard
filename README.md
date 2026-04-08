# ERP Analytics Dashboard

Manufacturing analytics dashboard for real-time production monitoring, OEE tracking, and quality metrics visualization.

Built to demonstrate how data-driven dashboards can transform manufacturing operations — inspired by real-world ERP implementations across Epicor, Oracle Cloud, CMS, and SAP environments.

## Overview

This project implements a complete analytics pipeline for manufacturing KPIs:

- **OEE (Overall Equipment Effectiveness)** — Availability x Performance x Quality tracking
- **Machine Downtime Analysis** — Root cause categorization and trend visualization
- **Production Quality Metrics** — Defect rates, scrap tracking, first-pass yield
- **Financial Integration** — Cost per unit, variance analysis, budget vs. actual

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  ERP System  │───→│  ETL Pipeline │───→│  Power BI   │
│  (CMS/SAP)   │    │  (SQL + Python)│    │  Dashboard  │
└─────────────┘    └──────────────┘    └─────────────┘
       │                  │                    │
  Production Data    Data Warehouse      Interactive
  Shop Floor Logs    Fact/Dim Tables     Visualizations
  Financial Records  Aggregations        KPI Scorecards
```

## Key Metrics Tracked

| KPI | Description | Target |
|-----|-------------|--------|
| OEE | Overall Equipment Effectiveness | > 85% |
| Downtime % | Unplanned machine downtime | < 5% |
| First Pass Yield | Units passing QC on first attempt | > 95% |
| Scrap Rate | Material waste percentage | < 2% |
| MTBF | Mean Time Between Failures | > 500 hrs |
| MTTR | Mean Time To Repair | < 2 hrs |

## SQL Queries

The `/sql` directory contains optimized queries for:

- `oee_calculation.sql` — OEE computation from production logs
- `downtime_analysis.sql` — Downtime categorization and Pareto analysis
- `production_summary.sql` — Daily/weekly/monthly production rollups
- `cost_variance.sql` — Budget vs. actual manufacturing costs
- `inventory_aging.sql` — Inventory turnover and aging analysis

## Data Model

```
Production_Runs (Fact)
├── dim_machine
├── dim_product
├── dim_shift
├── dim_operator
└── dim_date

Quality_Events (Fact)
├── dim_defect_type
├── dim_inspection_point
└── dim_corrective_action

Downtime_Events (Fact)
├── dim_downtime_reason
├── dim_machine
└── dim_maintenance_type
```

## Tech Stack

- **BI Tool:** Power BI (DAX measures, Power Query M)
- **Database:** SQL Server / Oracle
- **ETL:** Python (pandas), SQL stored procedures
- **ERP Systems:** CMS, Epicor, Oracle Cloud, SAP
- **Scheduling:** Windows Task Scheduler / cron

## Results

In a real manufacturing environment, this dashboard approach delivered:
- **+20% OEE improvement** through visibility into bottlenecks
- **-30% machine downtime** via predictive maintenance triggers
- **Real-time visibility** for 50+ end users across executive and operations teams

## Getting Started

```bash
# Clone the repository
git clone https://github.com/Maitry-R/erp-analytics-dashboard.git

# Set up the sample database
cd sql && ./setup_sample_db.sh

# Run the ETL pipeline
python etl/pipeline.py --config config/sample.yml
```

## License

MIT
