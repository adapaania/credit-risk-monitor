# Monitoring and reports

Use `python3 scripts/project.py monitor` to check loaded pilot data, install monitoring functions, process available filings, and refresh reports. Setup runs this automatically.

## Test covenants and record ratings

```sql
SELECT * FROM credit.test_loan_covenants(loan_id, statement_id, DATE '2025-10-30');
SELECT credit.record_financial_rating(loan_id, statement_id, DATE '2025-10-30');
```

Replace the example IDs and date with real values. The statement must belong to the loan's borrower and be available by the selected date. The loan must be active: origination is included and maturity is excluded. The latest filing for that reporting date is used.

Tests store the ratio, threshold, comparison, result, and evaluation date. Missing inputs produce `unavailable`, not a pass. Repeating a covenant/statement test returns the first stored result. Tested evidence and terms cannot be edited; a controlled correction process is future work.

## Watchlist and audit history

Each breach opens one watchlist event. Later passing tests do not close it automatically.

```sql
SELECT * FROM credit.close_watchlist_event(event_id, DATE '2026-02-20', 'Reviewed and approved closure');
```

Closing requires a reason and valid date. Repeating the same closure is allowed; changing a completed closure is rejected. Business dates are stored separately from the time the database processed the event.

Rating inserts, updates, and deletions are audited with old/new values, user, and time. Initial ratings loaded before auditing get `BASELINE` records. Unchanged updates do not create another audit row. Audit rows cannot be updated or deleted through normal table operations. Role permissions still need to be implemented.

## Report date

```sql
SELECT reporting.refresh_reports(DATE '2026-02-28');
```

This sets a shared report date for the database and refreshes the two stored report tables. Refresh after changing inputs or closing events. The default is the month end containing the last filing in the pilot. To process another cutoff, run `python3 scripts/run_monitoring.py --csv data/processed/pilot_10_financials.csv --as-of YYYY-MM-DD`.

The [report guide](report_queries.md) lists the views. Historical views filter business dates; they do not reconstruct later manual corrections. `credit.portfolio_snapshots` keeps previously refreshed months, so use the scoped view or current stored report for an earlier cutoff.

## Optional separate local server

If you want a project-only PostgreSQL server instead of your existing service:

```sh
sh scripts/local_db.sh start
export DATABASE_URL="$(sh scripts/local_db.sh url)"
python3 scripts/project.py setup
```

This uses a private Unix socket on port 55432, not localhost TCP. Its database is named `credit_risk_week2` for compatibility with existing copies. Database files stay in ignored `data/local_postgres/`. Stop it with `sh scripts/local_db.sh stop`. Set `PG_BIN` if the PostgreSQL tools are not on PATH. Do not run setup again on a populated database; use `check` or `monitor`.
