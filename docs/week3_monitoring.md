# Week 3 monitoring and reporting interfaces

Apply the additive `sql/04_risk_monitoring.sql` and `sql/05_reporting.sql` through `scripts/run_week3.py`, which first checks the supplied financial and generated configuration. A new empty database can use `scripts/setup_week3.sh`. Full build and migration scripts deliberately do not drop populated application tables.

## Covenant and rating calls

`SELECT * FROM credit.test_loan_covenants(loan_id, statement_id, DATE '2025-10-30');` evaluates active covenants using a specified borrower-matching, currency-matching, normalized 3-month statement available by that date. Loan dates are start-inclusive and maturity-exclusive; covenant dates are inclusive. Debt testing is disabled. A repeated covenant/statement pair returns its retained first result and original evidence rather than replacing timestamps or producing another event.

`SELECT credit.record_financial_rating(loan_id, statement_id, DATE '2025-10-30');` records the documented synthetic assessment, returning its rating ID. An unavailable ratio returns null and must be reviewed; its covenant test remains visible as unavailable. An existing same-date assessment with different evidence raises a conflict rather than overwriting it. The batch replays baseline assessments on origination and subsequent assessments on filing availability. Original and later assessments are distinguished by source references and reasons, even if the numeric grade stays unchanged.

Result reasons, policy thresholds and observed values are persisted. Tested financial/source records and used covenant/loan terms cannot be edited with ordinary DML. This is a fixed-policy pilot; changing used terms or correcting source evidence requires a future controlled version/revision process. Audit triggers are not a substitute for the role privileges still scheduled for Week 4; a database owner can administer or disable objects.

## Watchlist lifecycle

Each breached result creates one event. Multiple breaches for one borrower are distinct events; portfolio reports count distinct borrowers. `opened_on` is the business evaluation date while `opened_at` is the actual record creation timestamp. A later passing test does not erase an earlier event.

`SELECT * FROM credit.close_watchlist_event(event_id, DATE '2026-02-20', 'Reviewed and approved closure');` closes one event with a required explanation, actor and execution timestamp. The date cannot precede opening or be in the future. Repeating the identical closure is safe; conflicting closure edits are rejected. Re-running old tests does not reopen the event. The pilot retains all 35 original events open; closure tests roll back their fixtures.

## Rating audit

Every actual INSERT, changed UPDATE or DELETE produces an audit row containing old/new scalar ratings and JSON row snapshots. Delete operations retain evidence without foreign keys to the deleted rating row. The 10 imported initial ratings receive upgrade-time BASELINE snapshots because their original INSERTs occurred before installation. No invented UPDATE/DELETE demonstrations remain in actual data. Unchanged-row updates are ignored. Audit UPDATE/DELETE operations are blocked through an append-only guard.

## Report cutoff and stored aggregates

`SELECT reporting.refresh_reports(DATE '2026-02-28');` sets the shared report date and atomically refreshes both CTAS tables. The default replay cutoff is the month end containing the most recent supplied filing. Use `scripts/run_week3.py --as-of YYYY-MM-DD` to process available evidence up to another date; previously recorded later evidence stays in history but report views filter it out. Views are business-date historical reconstructions; they do not provide full bitemporal reconstruction of later manual corrections.

The seven report views cover daily monitoring, weekly maturities, monthly portfolio exposure, quarterly test evidence, annual flow summaries, watchlist events and rating history. `reporting.monthly_portfolio_ctas` and `reporting.covenant_summary_ctas` are stored reports; they do not update automatically after arbitrary source or closure changes. Call the explicit refresh function after such changes. The refresh log records timing and row counts.

`credit.portfolio_snapshots` retains aggregates for all previously refreshed months. For a specific earlier cutoff, query the scoped monthly view or current CTAS table; do not assume that an unfiltered historical snapshot table contains only months before the selected date. Snapshots are recalculable business-month aggregates, not immutable sealed historical exports.

Historical unresolved watchlist events may belong to loans that have since matured. The event-history view preserves them; monthly portfolio exposure counts only borrowers with active loans on each month end. Annual financial totals group reporting-end dates by calendar year and expose available-quarter counts; they are not asserted to equal companies' fiscal-year annual reports. Rates and principal remain educational synthetic bullet-loan assumptions.
