# Week 2 reporting query drafts

This document records the original Week 2 drafts. Week 3 has since implemented persisted report views, CTAS tables and monitoring history; see `week3_monitoring.md` and `sql/reports/week3_reports.sql` for the current interfaces. Descriptions of absent monitoring below refer to the Week 2 milestone.

`sql/reports/week2_reports.sql` contains five executable, read-only drafts for Khush's Week 2 assignment. They use an explicit `as_of_date`, defaulting to December 31, 2025. The queries are drafts, not Week 3 persisted report views, CTAS tables or materialized snapshots.

- Daily analyst/manager review: one row per active loan with principal, terms, the latest financial statement available by the selected date, its two ratios and the initial/latest recorded rating. Later filings are excluded even when their reporting dates precede the cutoff.
- Weekly manager planning: maturities in the next 90 days grouped by maturity week, with loan count, distinct borrowers and principal. Loan activity uses a maturity-exclusive end date.
- Monthly executive portfolio review: month-end active loans, distinct borrowers, bullet-loan outstanding principal and principal-weighted annual rates for completed months in the selected calendar year. It does not include partial future month ends or multiply exposure by joining many statements/covenants.
- Quarterly analyst review: normalized 3-month statements, source fiscal labels, filing dates, derivation status, liquidity, coverage and operating margin. It retains off-calendar fiscal reporting dates rather than relabeling them as calendar quarter ends.
- Annual manager/executive review: sums quarterly flow amounts by the year of the actual reporting-end date and divides total operating income by total interest for aggregate coverage. The available-quarter count exposes partial coverage. It does not sum balance-sheet assets or average ratios, and does not claim these calendar-date buckets equal audited fiscal-year totals.

There are no persisted covenant test results or watchlist events yet. These drafts do not report a zero breach rate or imply that all loans have passed testing. Initial ratings are synthetic origination ratings and are not a later monitoring history. Default principal reporting assumes USD bullet loans; supporting other currencies or amortization requires additional inputs and logic.

Run with `psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -v as_of_date=2025-12-31 -f sql/reports/week2_reports.sql`. Week 3 can turn agreed queries into report views after risk processing is implemented; Week 4 will restrict their access.
