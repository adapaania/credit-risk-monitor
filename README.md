# Credit Risk Monitor

A team project using SEC financial statement data to monitor credit risk.

## Team

- Aania Adap: data foundation
- Halima Younus: risk monitoring
- Khush Mehta: reporting and access control

See [the implementation plan](docs/IMPLEMENTATION_PLAN.md) for proposal requirements and next steps.

## Week 3 completed pilot

The populated local database now includes the Week 3 data-quality audit, covenant-testing function, breach/watchlist trigger, quarterly rating assessments and rating-audit trigger, seven report views, and two CTAS report tables. See the [Week 3 completion record](docs/WEEK3_COMPLETION.md) and [monitoring interface guide](docs/week3_monitoring.md).

From this repository directory, verify and inspect the existing database:

```sh
sh scripts/local_db.sh start
export DATABASE_URL="$(sh scripts/local_db.sh url)"
python3 scripts/verify_week3.py --csv ../pilot_10_financials.csv
python3 -m unittest discover -s tests -v
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/reports/week3_reports.sql
```

The historical report cutoff defaults to February 28, 2026, including 2025 results filed in early 2026. Verification reconciles 240 tests (205 pass and 35 breach), 120 rating assessments and their audit coverage, 35 historical watchlist events across 7 borrowers, and the CTAS tables. All 32 regression tests pass. This is synthetic covenant monitoring against real pilot inputs; breach events are not observed defaults.

To upgrade/replay an existing Week 2 database, run `python3 scripts/run_week3.py --csv ../pilot_10_financials.csv`. For a new empty database, set `DATABASE_URL` and run `sh scripts/setup_week3.sh /path/to/pilot_10_financials.csv`. Identical replay does not duplicate results, ratings or watchlist events. Explicit report refresh and watchlist closure behavior is documented in the interface guide. The database retains the name `credit_risk_week2` for continuity.

Data-quality results, validation output, reports, test logs, a pre-upgrade backup and the Week 3 database dump remain local under ignored `data/processed/`. Debt-based covenants remain disabled. Week 4 role grants and performance baselines, and later optimization/final-report work, remain pending.

## Data source and coverage

Source: [SEC Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets).

Coverage: 2023 Q1 through 2025 Q4 (three years, 12 quarters).

## Week 2 pilot setup

The Week 1–2 implementation now loads the separately supplied pilot into PostgreSQL, generates reproducible synthetic loans/covenants and initial ratings, and provides executable report drafts and an access-control design. See [the completion record](docs/WEEK2_COMPLETION.md), [risk policy](docs/risk_policy.md), [data mapping](docs/data_mapping.md), [report definitions](docs/report_queries.md), and [role design](docs/role_design.md).

Requirements: Python 3.11+ and PostgreSQL 14+ with `psql` on `PATH`. New scripts use the Python standard library, with no pip packages required. The existing downloader additionally requires curl. For macOS/Homebrew, PostgreSQL can be installed with `brew install postgresql@16`. No system service is required.

For a dedicated local development database:

```sh
sh scripts/local_db.sh start
export DATABASE_URL="$(sh scripts/local_db.sh url)"
sh scripts/setup_week2.sh '/absolute/path/to/pilot_10_financials.csv'
```

Use `../pilot_10_financials.csv` when running from this clone in the shared FE 513 project folder. The local database is `credit_risk_week2` on a private Unix socket at port 55432, with no TCP listener. Its files are ignored under `data/local_postgres/`; no login password is needed for the local owner. `sh scripts/local_db.sh stop` stops only this project cluster; `start` restarts it without erasing records. `PG_BIN` can point to another PostgreSQL installation.

`setup_week2.sh` expects a new empty database. It creates the schema, imports financial statements and provenance, generates the fixed-seed synthetic files in `data/processed/`, imports them, and reconciles all financial amounts and ratios. It does not drop or replace existing tables. On another existing empty PostgreSQL database, export its URL and use the same setup script without the local-cluster helper. Set `PYTHON` or `PSQL` if their executables need explicit paths.

For an existing **starter schema** created by the original setup, apply the additive support before importing:

```sh
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 --single-transaction \
  -f sql/02_pilot_support.sql -f sql/03_ratio_views.sql
python3 scripts/load_pilot_data.py --csv ../pilot_10_financials.csv
python3 scripts/generate_loan_data.py --csv ../pilot_10_financials.csv
python3 scripts/load_synthetic_data.py --csv ../pilot_10_financials.csv
python3 scripts/verify_week2.py --csv ../pilot_10_financials.csv
```

The two data loaders are repeatable for identical input. Conflicting source data, loan terms, covenants or ratings cause rollback instead of overwriting history. The complete setup intentionally fails on an already populated schema; use the loaders individually to re-check the existing pilot.

Run the Week 2 checks and reports:

```sh
export DATABASE_URL="$(sh scripts/local_db.sh url)"
python3 -m unittest discover -s tests -v
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/check_schema.sql
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -v as_of_date=2025-12-31 \
  -f sql/reports/week2_reports.sql
```

Tests use the pilot at `../pilot_10_financials.csv` by default; set `PILOT_CSV` for another location. PostgreSQL integration tests are skipped if `DATABASE_URL` is absent. The financial validator targets the exact pilot dataset, not a database mixed with unrelated fixtures. The schema smoke check rolls its fixtures back. Report outputs and database dumps should be saved under ignored `data/processed/`.

Debt-based covenants remain disabled. Only current ratio and standalone-quarter operating-income interest coverage are generated. The original Week 2 build stops before monitoring. Its empty workflow tables do not mean zero actual breaches. The Week 3 upgrade above now implements the functions, triggers and persisted reports; Week 4 permission grants remain pending.

## Optional raw SEC acquisition and schema-only setup

1. Clone this repository to your computer.
2. Run `python3 scripts/download_sec_data.py` (requires Python 3.11+ and curl) to download, verify, and extract all 12 quarters into `data/raw/<quarter>/`, for example `data/raw/2023q1/`. The script keeps the original ZIPs and writes a local SHA-256 download manifest.
3. Install PostgreSQL 14 or later and start your local PostgreSQL service. Create a new empty database with `createdb credit_risk`.
4. Run `DATABASE_URL=postgresql:///credit_risk sh scripts/setup.sh` to create the core tables, SEC staging tables, and ratio view. For a remote database, supply your connection URL through the environment; do not commit credentials.
5. Optionally validate an empty initialized database with `psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/check_schema.sql` after exporting `DATABASE_URL` in your shell. Test records are rolled back.

`scripts/setup.sh` creates database objects only; `scripts/setup_week2.sh` also loads the prepared pilot and synthetic data. The raw SEC-to-staging importer remains outside this pilot path. Schema setup runs in a single transaction and fails safely if tables already exist; it does not drop or replace existing data.

Raw data stays on each teammate's computer and is excluded from Git by `.gitignore`.

## Shortlist data quality

Run `python3 scripts/check_completeness.py` after downloading the data to audit the 50-company shortlist. Read [the completeness report](docs/data_quality/REPORT.md) and its accompanying company/filing CSVs and JSON scan log. This checks selected standard-tag availability, not fully normalized ratio readiness; debt definitions, duration conversion, and company-specific tags still require review.

The [resolved audit](docs/data_quality/resolved/REPORT.md) supersedes the initial results: it adds SEC company-facts supplements, boundary filing batches, exact reporting dates, quarter normalization, and explicit sample decisions. Follow its reproduction instructions to create the local 120-row, 10-company pilot for current-ratio and interest-coverage work. Debt candidates remain subject to disclosure and lease-basis validation. Both raw and processed financial data stay local.

## Project structure

```text
data/raw/   Local SEC files (ignored by Git)
sql/        CREATE TABLE scripts, views, and triggers
docs/       ER diagram and change log
tests/      Pilot policy and PostgreSQL integration checks
```
