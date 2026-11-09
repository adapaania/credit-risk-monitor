# SQL

Database engine: PostgreSQL 14+.

Run `scripts/setup.sh` from the repository instructions. It executes `01_schema.sql`, `02_staging.sql`, and `03_ratio_views.sql` in one transaction. `check_schema.sql` is an optional rollback-only smoke check.

Functions, triggers, reporting queries, roles, and optimization scripts are pending.
