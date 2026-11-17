# Change log

## 2026-11-16

- Completed Week 3 for the pilot: 14 data-quality checks, immutable covenant result snapshots, a breach/watchlist trigger, explicit reasoned closure, quarterly rating assessments and INSERT/UPDATE/DELETE audit triggers. Initial imported ratings receive honest upgrade-time BASELINE audit snapshots.
- Added seven report views and two CTAS tables with an explicit historical report cutoff, transactional refresh and distinct-borrower portfolio aggregation. Reconciled 240 tests (205 pass, 35 breach), 120 assessments/audits, 35 historical events across 7 borrowers, 37 monthly CTAS rows and 29 covenant-summary rows.
- All 32 Week 2–3 tests and a clean full rebuild pass. Preserved the original financial values and debt deferral. Current completion and reproduction details are in `WEEK3_COMPLETION.md`; local financial outputs and database dumps remain ignored.
- Completed the Week 1–2 implementation for the supplied 10-company pilot, preserving Aania's source scripts and core schema.
- Added a transactional prepared-pilot importer and provenance storage for complete original CSV rows, filing availability dates, source hashes and per-metric derivations. Imported 120 normalized 3-month statements and 10 borrowers; unvalidated debt and absent total liabilities remain null.
- Added the `pilot-v1` covenant/rating policy and fixed-seed generator, producing and importing 10 synthetic loans, 20 current-ratio/interest-coverage covenants and 10 initial ratings. Baselines use the first available filing only; generated outputs remain ignored by Git.
- Added executable daily/weekly/monthly/quarterly/annual report drafts, report definitions, role design, data mapping and a single Week 2 build entry point.
- Added an isolated local PostgreSQL helper and automated policy/input/integration checks. See `WEEK2_COMPLETION.md` for the final verification record.
- The original Week 2 milestone stopped before covenant functions and triggers; the subsequent Week 3 extension above implements them. Week 4 permission grants remain pending. Data and local edits have not been pushed to GitHub.

## 2026-11-09

- Added the starter README, SQL folder, and documentation folder.
- Excluded local SEC raw data from Git.
- Added PostgreSQL core/staging schemas, ratio view, initial ER diagram, and transactional schema setup script.
- Validated setup, ratio calculations, zero-denominator handling, and negative-principal rejection in an isolated PostgreSQL 14 database.
- Importer, covenant logic, generated data, roles, and reports are pending.
- Audited 50 shortlisted companies across 12 SEC filing batches (42,797,577 numeric rows): 573 selected reporting dates; all six mapped metrics present together on 227 dates. Interest expense needs mapping review on 314 dates; total-debt definition and duration normalization remain pending.
- Saved reproducible completeness script, company/filing coverage CSVs, candidate-tag inventory, and JSON scan log under docs/data_quality/.
- Resolved audit tag capitalization, supplemented compact data with official SEC companyfacts, and added boundary filing batches. Revised scope uses actual reporting dates in 2023–2025: 599 dates, with 28 companies passing six core metrics and quarter normalization on all 12 dates.
- Prepared a local 120-row pilot for ten companies. Preserved unavailable facts and unvalidated debt/lease scope as explicit exclusions; added provenance, source hashes, metadata discrepancy log, and sample decisions in docs/data_quality/resolved/.
