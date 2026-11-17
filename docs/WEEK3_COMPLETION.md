# Week 3 completion record

Completed locally November 16, 2026, for the supplied 10-company pilot. The proposal assigns Aania data-quality checks and fixes, Halima the covenant function and triggers, and Khush report views and CTAS tables. All three workstreams are implemented and tested in the existing project PostgreSQL database. The database keeps its original name, `credit_risk_week2`, and now contains Week 3 objects and results.

## Aania data quality checks and fixes

`scripts/check_pilot_quality.py` produces a structured local report and the upgrade records it in `credit.data_quality_runs`. Fourteen checks pass: pilot coverage, reporting window, calendar-year labels, filing-batch dates, derived-quarter arithmetic, database/source reconciliation, seed-based loan and covenant terms, debt exclusion, available ratios, covenant dates, denominators, quarter durations, loan currency/dates and duplicate borrower/reporting dates.

All 120 financial values and both ratios reconcile with the supplied CSV. All 83 derived values whose prior filing is present in the pilot reconcile using the same CIK, fiscal start and tag and the immediately preceding fiscal period. Three derived values refer to prior filings outside this CSV; their accessions remain preserved, but this milestone does not claim fresh source arithmetic verification for those three values.

Quality fixes strengthen the implementation rather than alter validated financials: nonfinite ratio inputs now remain unavailable, typed filing/fiscal metadata is reconciled against original source records, seeded loan/covenant terms are independently checked, and the Week 2 validator continues to validate base data after genuine monitoring history is added. Source fiscal labels remain as reported; unavailable SIC/state/ticker data remains null. Debt scope and independent SEC disclosure/restatement review remain explicit limitations.

The original pilot CSV and Aania's historical audit artifacts were not modified. No financial values were imputed or changed to force covenant outcomes.

## Halima covenant testing and triggers

`sql/04_risk_monitoring.sql` adds the following working interfaces:

- `credit.test_loan_covenants(loan_id, statement_id, evaluated_on)`: tests applicable covenants against an explicit normalized statement, storing the unrounded observed value, threshold/comparator snapshot, outcome, business evaluation date, execution timestamp and reason.
- Borrower, loan activity, filing availability, currency, quarter duration and canonical-filing checks. Equality passes. Missing/nonfinite inputs and nonpositive denominators produce `unavailable`; valid negative operating income produces negative numeric coverage.
- A breach trigger creates one watchlist event per breached result, with matching borrower and evaluation date. Identical reruns retain results and do not duplicate or reopen events.
- `credit.close_watchlist_event(event_id, closed_on, reason)`: records explicit closure date, reason, database actor and execution time. A later passing result does not silently close an earlier event. Manager permissions remain Week 4 work.
- A rating-source guard and INSERT/UPDATE/DELETE audit trigger preserve old/new ratings and complete row snapshots, actor and timestamp. No-op updates do not create audit noise. Audit rows survive rating deletion and ordinary UPDATE/DELETE against audit history is rejected.
- `credit.rating_from_ratios` implements the documented 1–10 scale. `credit.record_financial_rating` adds a synthetic assessment for each available quarterly statement; unchanged grades are still documented assessments. Unavailable ratios produce no invented rating and remain visible through unavailable covenant results for analyst review.
- Guards reject overlapping covenant windows, new debt covenants, forged results and changes to tested loan/covenant/financial evidence. Revisions to used inputs require an explicit future version/revision workflow.

The 10 initial Week 2 ratings predate installation of the audit trigger. Their upgrade audit entries are labeled `BASELINE`, captured at migration time. They are not falsely described as historical INSERT audits. The remaining 110 quarterly assessments produce genuine INSERT audit records. UPDATE and DELETE audits were exercised with rollback-only fixtures, so fabricated changes are not left in the pilot.

The historical replay evaluates each baseline at loan origination and each later filing when available, within the active loan term. Business evaluation dates are separate from actual execution/audit timestamps. The supplied pilot has one canonical accession per borrower/reporting date; the function also rejects an earlier accession once a later same-period filing is available.

## Khush report views and CTAS tables

`sql/05_reporting.sql` creates seven persisted views:

- `reporting.v_daily_monitoring`: active loan exposure, latest available financials, ratios, rating and pass/breach/unavailable/untested status.
- `reporting.v_weekly_maturities`: upcoming 90-day maturities grouped by week.
- `reporting.v_monthly_portfolio`: month-end active loans, distinct borrowers, principal, weighted rate and distinct active watchlist borrowers.
- `reporting.v_quarterly_covenant_results`: statement-level test evidence and outcomes.
- `reporting.v_annual_financials`: calendar-reporting-year quarterly flow totals and aggregate coverage, with available-quarter counts.
- `reporting.v_watchlist`: event history and open/closed state at the selected date; future closure details are masked.
- `reporting.v_rating_history`: dated assessments, previous grades and source references.

Two real tables are defined using CREATE TABLE AS: `reporting.monthly_portfolio_ctas` and `reporting.covenant_summary_ctas`. `reporting.refresh_reports(date)` atomically selects an explicit report date and refreshes both stored tables without dropping them. It also upserts month-level aggregates into `credit.portfolio_snapshots` and records the refresh. Views use the shared date in `reporting.report_context`; changing it changes all these report views for that database.

Default report date is February 28, 2026, the month end containing the latest filing in the pilot. This includes 2025 results filed in early 2026. It is a historical demonstration date, not a claim that financials cover the current calendar quarter. Actual reporting dates, fiscal labels, filing dates and execution times retain their separate meanings.

## Verified results

The independent Python verifier reconciles the policy, ratios, outcomes, rating dates/grades, watchlist links and CTAS/source-view equality. At the default cutoff:

- 10 borrowers and 120 original financial statements/source records remain intact.
- 10 synthetic loans and 20 covenants remain intact; zero debt covenants.
- 240 persisted covenant tests: 205 pass, 35 breach, zero unavailable in this complete pilot.
- 35 historical watchlist events across 7 distinct borrowers. These are event-history counts, not a count of active loans or a default count. Closure and unavailable-input behavior are tested separately without changing the pilot.
- 120 synthetic rating assessments and 120 audit records: 10 BASELINE and 110 INSERT.
- 37 monthly CTAS rows and 29 covenant-summary CTAS rows; both stored tables reconcile with their source views.

All 32 unit/integration tests pass, including the 12 Week 2 regressions. Tests cover equality and maximum comparisons, missing/zero/negative/NaN inputs, negative operating income, wrong borrowers, inactive dates, filing cutoffs and revisions, debt rejection, overlapping covenants, repeated calls, immutable evidence, direct forged writes, closure timing, rating INSERT/UPDATE/DELETE audits and retention, report date cutoffs, and exposure/borrower aggregation without multiplication by events. Fixtures and report-date changes are rolled back.

A clean temporary database was rebuilt through Weeks 1–3 using `scripts/setup_week3.sh`; all 32 tests passed there, and the temporary database was removed. Reapplying the migration/replay preserves every result, rating, audit and watchlist row exactly, verified by before/after fingerprints. The final SQL backup was restored to another temporary database and independently reconciled successfully; that restore was removed afterward. Python compilation, shell syntax checks, schema smoke checks and Git whitespace checks pass.

## Check the completed work

From the repository directory:

```sh
sh scripts/local_db.sh start
export DATABASE_URL="$(sh scripts/local_db.sh url)"
python3 scripts/verify_week3.py --csv ../pilot_10_financials.csv
python3 -m unittest discover -s tests -v
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/reports/week3_reports.sql
```

To rerun the upgrade/replay for this already populated database:

```sh
python3 scripts/run_week3.py --csv ../pilot_10_financials.csv
```

For a new empty PostgreSQL database, export its URL and run `sh scripts/setup_week3.sh /path/to/pilot_10_financials.csv`. This creates base schema/data before installing monitoring and reports. The original Week 2 setup remains usable for its own milestone.

Saved local artifacts under ignored `data/processed/` include `week3_validation.json`, `week3_data_quality.json`, `week3_tests.log`, `week3_reports.txt`, clean rebuild logs, `pre_week3_database.sql` and `week3_database.sql`. Database dumps contain real financial data and remain local, along with generated datasets and report outputs. Source/documentation changes have not been committed or pushed to GitHub.

## Remaining after Week 3

Week 4 role/permission grants, separate role-operation tests, integration permissions and baseline performance measurement remain. Later work includes optimization/index benchmarking and the final report/presentation. Existing constraints and uniqueness indexes support correctness; this milestone does not claim a performance benchmark or production access-control system. Debt-based covenants remain deferred until definitions and lease comparability are validated. The project still uses the 10-company pilot, not the proposal's original several-hundred-company target.

PostgreSQL implementation references: [trigger functions](https://www.postgresql.org/docs/16/plpgsql-trigger.html), [CREATE FUNCTION](https://www.postgresql.org/docs/16/sql-createfunction.html), and [CREATE TABLE AS](https://www.postgresql.org/docs/16/sql-createtableas.html).
