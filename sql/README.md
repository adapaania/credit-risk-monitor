# SQL

Database engine: PostgreSQL 14+.

Run `scripts/setup.sh` from the repository instructions. It executes `01_schema.sql`, `02_staging.sql`, `02_pilot_support.sql`, and `03_ratio_views.sql` in one transaction. `check_schema.sql` is a rollback-only smoke check. `scripts/setup_week2.sh` additionally imports the prepared pilot and synthetic data and verifies the result.

`02_pilot_support.sql` is additive for an existing starter schema. It retains the original CSV rows as provenance, records generation baselines and adds repeat-import keys. `03_ratio_views.sql` can be reapplied with CREATE OR REPLACE VIEW.

`reports/week2_reports.sql` retains the original executable query drafts. Week 3 adds `04_risk_monitoring.sql` (testing, watchlist, rating assessments and audit guards/triggers) and `05_reporting.sql` (seven report views, two CTAS tables, explicit-date refresh and monthly snapshots). Use `scripts/run_week3.py` for an additive upgrade, or `scripts/setup_week3.sh` for a clean Weeks 1–3 build. `reports/week3_reports.sql` displays current report outputs.

Permission grants and optimization benchmarks remain later milestones. Role design is documented in `docs/role_design.md`. Security/owner permissions are not established by the monitoring guard triggers alone.
