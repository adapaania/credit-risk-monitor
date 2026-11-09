# Credit Risk Monitor

A team project using SEC financial statement data to monitor credit risk.

## Team

- Aania Adap: data foundation
- Halima Younus: risk monitoring
- Khush Mehta: reporting and access control

See [the implementation plan](docs/IMPLEMENTATION_PLAN.md) for proposal requirements and next steps.

## Data source and coverage

Source: [SEC Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets).

Coverage: 2023 Q1 through 2025 Q4 (three years, 12 quarters).

## Setup

1. Clone this repository to your computer.
2. Run `python3 scripts/download_sec_data.py` (requires Python 3.11+ and curl) to download, verify, and extract all 12 quarters into `data/raw/<quarter>/`, for example `data/raw/2023q1/`. The script keeps the original ZIPs and writes a local SHA-256 download manifest.
3. Install PostgreSQL 14 or later and start your local PostgreSQL service. Create a new empty database with `createdb credit_risk`.
4. Run `DATABASE_URL=postgresql:///credit_risk sh scripts/setup.sh` to create the core tables, SEC staging tables, and ratio view. For a remote database, supply your connection URL through the environment; do not commit credentials.
5. Optionally validate an empty initialized database with `psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/check_schema.sql` after exporting `DATABASE_URL` in your shell. Test records are rolled back.

The current setup creates database objects only. SEC loading, synthetic data generation, covenant functions/triggers, reports, and roles are the next milestones. Setup runs in a single transaction and fails safely if tables already exist; it does not drop or replace existing data.

Raw data stays on each teammate's computer and is excluded from Git by `.gitignore`.

## Shortlist data quality

Run `python3 scripts/check_completeness.py` after downloading the data to audit the 50-company shortlist. Read [the completeness report](docs/data_quality/REPORT.md) and its accompanying company/filing CSVs and JSON scan log. This checks selected standard-tag availability, not fully normalized ratio readiness; debt definitions, duration conversion, and company-specific tags still require review.

## Project structure

```text
data/raw/   Local SEC files (ignored by Git)
sql/        CREATE TABLE scripts, views, and triggers
docs/       ER diagram and change log
```
