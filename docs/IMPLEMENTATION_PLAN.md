# Proposal-aligned implementation plan

Based on the FE513 Fall 2026 project proposal, updated November 16, 2026.
This plan translates the proposal into implementation tasks; it is not a new course rubric.

## Current status

- Shared repository and basic structure exist.
- Aania prepared and audited SEC data on her machine; the clone does not include raw SEC archives or companyfacts caches. The separately shared 120-row pilot is the input for this milestone.
- Raw/processed financials, generated records and the dedicated local database are ignored by Git. Teammates need the separately shared pilot or their own prepared source data.
- Weeks 1–2 are implemented for the 10-company pilot: schema and relationships, quarterly import with original-row provenance, ratio view, covenant/rating policy, deterministic loans/covenants and initial ratings, query drafts and role design. See `WEEK2_COMPLETION.md` for verification and scope.
- A dedicated PostgreSQL 16 project database is populated and reconciled. `scripts/setup_week2.sh` rebuilds a new empty database from the supplied pilot. This is a prepared-pilot path, not a general raw SEC importer.
- Week 3 is also implemented for the pilot: 14 data-quality checks, covenant processing and watchlist trigger, rating assessments/audit, seven report views, two CTAS tables and monthly snapshots. See `WEEK3_COMPLETION.md`; 32 tests and a clean Weeks 1–3 rebuild pass.
- Week 4 role grants and performance baselines, and later controlled optimization/final-report work remain pending. GitHub collaborator invitations and pushing local changes remain separate repository administration tasks.

## First decision

PostgreSQL was selected by Aania on November 9, 2026. The November 16 extension preserves her core DDL and adds a prepared-pilot importer, provenance and generation metadata. Original source fiscal labels remain available; reporting-date and filing-date semantics are explicit.

## Original foundation checklist and pilot disposition

The original checklist below remains for traceability. The supplied pilot is now imported across all 120 observations. Raw SEC staging and expansion beyond the selected 10-company pilot remain future scope; the several-hundred-company proposal target has not been claimed as completed.

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

The proposal scheduled schema/ER design for November 2–6 and data loading, generation, and ratio views for November 9–13. The Week 3 extension implements the monitoring function/triggers and persisted report views/CTAS specified for November 16–20. Week 2 report drafts remain as historical deliverables; current reporting interfaces are documented in `week3_monitoring.md`. The role document is still a design, matching the Week 4 implementation schedule.

## Deliverables and acceptance checks

- Rebuild: a documented setup entry point creates the database objects and loads prepared data in dependency order; explain raw-data prerequisites and privileged role setup.
- Risk monitoring: implemented and verified in Week 3; covenant results are reproducible, breaches create distinct linked events without rerun duplicates, and rating mutations retain audits.
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
