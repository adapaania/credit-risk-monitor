# Proposal-aligned implementation plan

Based on the FE513 Fall 2026 project proposal, reviewed November 9, 2026.
This plan translates the proposal into implementation tasks; it is not a new course rubric.

## Current status

- Shared repository and basic structure exist.
- SEC Financial Statement Data Sets for 2023 Q1 through 2025 Q4 are downloaded locally, with archive validation and a SHA-256 manifest.
- Raw data is ignored by Git. Each teammate must download their own copy.
- Core schema, staging tables, ratio view, initial ER diagram, and schema setup entry point are implemented and validated on PostgreSQL 14. The importer, generated loan data, risk logic, reports, roles, benchmarks, and complete data rebuild remain pending.
- Teammate invitations still need their GitHub usernames.

## First decision

PostgreSQL was selected by Aania on November 9, 2026. Core DDL, staging DDL, a ratio view, a schema setup script, and an initial ER diagram are now implemented. The importer and remaining application logic are pending.

## Next milestone: schema and a one-quarter import

1. Agree on financial ratios, accounting inputs, and covenant definitions across all three workstreams.
2. Draw the ER diagram and define keys, constraints, and ownership for these proposed entities:
   - borrowers: company identity keyed by SEC CIK
   - loans: borrower, amount, rate, start date, and maturity
   - financial_statements: borrower, reporting date, fiscal period, and selected financial values
   - covenants: loan, metric, comparison operator, threshold, and effective dates
   - covenant_test_results: covenant, statement, observed value, outcome, and test time
   - risk_rating_history: borrower, rating, effective date, and reason
   - watchlist: borrower, breach reason, status, and open/close times
   - rating_audit: rating change, actor, and timestamp
   - portfolio_snapshots: reporting month and portfolio measures
3. Keep SEC staging tables separate from the application schema. Stage sub, num, tag, and pre with source-quarter provenance; preserve original accession numbers, tags, taxonomy versions, units, dimensions, and period fields.
4. Load one quarter and validate keys, duplicates, joins, dates, units, and required metric coverage before loading the remaining quarters.
5. Select several hundred companies with consistent coverage; record the inclusion/exclusion criteria and tag mappings.
6. Build ratio views before generating loans and thresholds, so synthetic records can be calibrated to actual financials.

## Data decisions to resolve explicitly

- SEC download quarters describe filing batches, not necessarily financial reporting quarters. Select observations by their reporting dates as well as filing dates.
- Define how amended filings and multiple filings for the same company/period are selected; retain source provenance.
- Distinguish instant balance-sheet values from duration income-statement values. Avoid treating year-to-date figures as individual quarters. Document any derived fourth-quarter values.
- Define total debt and each ratio consistently, including zero/missing denominator behavior and industry exclusions.
- Avoid double-counting dimensional facts. Match taxonomy version, units, periods, and dimensional context when mapping facts.
- Missing values stay missing unless a documented transformation justifies otherwise.
- Mark generated loans, covenants, and ratings as synthetic. Document the generation seed, assumptions, and calibration method.

## Workstreams from the proposal

| Owner | Immediate work | Later work |
| --- | --- | --- |
| Aania Adap | Core schema, statement importer, quality checks, ratio views | Integration testing and report drafting |
| Halima Younus | Covenant/rating definitions; generated loans and covenants | Covenant testing function, breach/watchlist trigger, rating audit trigger |
| Khush Mehta | Setup entry point, report query drafts, role design | Report views, CTAS/snapshots, roles, indexing, performance comparison |

The proposal scheduled schema/ER design for November 2–6 and data loading, generation, and ratio views for November 9–13. Finish the schema milestone first because all workstreams depend on it.

## Remaining deliverables and acceptance checks

- Rebuild: a documented setup entry point creates the database objects and loads prepared data in dependency order; explain raw-data prerequisites and privileged role setup.
- Risk monitoring: covenant function stores reproducible results; breaches create watchlist entries without duplicates; rating changes produce audit records.
- Reports: agree on daily, weekly, monthly, quarterly, and annual report queries and document their intended users.
- Access: analyst, manager, executive, and auditor roles have explicit permissions, verified with allowed and denied operations.
- Snapshots: CTAS tables or materialized views produce monthly portfolio snapshots with documented refresh behavior.
- Performance: save baseline and optimized query plans/timings using the same data, query definitions, and repeatable measurement method.
- Final report: explain design decisions, real versus generated data, limitations, and changes from the proposal; prepare presentation materials.

## Suggested repository additions

```text
sql/01_schema.sql
sql/02_staging.sql
sql/03_ratio_views.sql
sql/04_risk_monitoring.sql
sql/05_reports.sql
sql/06_roles.sql
sql/07_indexes_snapshots.sql
scripts/load_sec_data.py
scripts/generate_loan_data.py
scripts/setup.py
docs/er_diagram.md
docs/data_dictionary.md
docs/data_mapping.md
docs/performance.md
```

These filenames are proposed organization, not implemented components.
