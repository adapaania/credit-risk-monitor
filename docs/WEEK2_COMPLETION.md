# Weeks 1 and 2 completion record

Historical milestone record. Week 3 has since been completed; see `WEEK3_COMPLETION.md` for current monitoring counts and verification. The Week 2-only counts and pending items below describe the state before that upgrade.

Completed locally on November 16, 2026, for the separately supplied 10-company, 120-observation pilot. The work extends Aania's reviewed foundation at commit `aed87ed` and follows the proposal's owner assignments. The several-hundred-company proposal target is not claimed as completed; this milestone uses the agreed development pilot and retains the documented debt deferral.

## Aania data foundation

The core tables, keys, constraints, staging schema and ER diagram are retained and extended with source and generation provenance. `scripts/load_pilot_data.py` now imports the pilot into PostgreSQL in one transaction, preserving all 48 original CSV fields alongside the normalized statement.

The local database contains 10 borrowers, 120 financial statements and 120 linked source records. Revenue, operating income and interest expense use standalone-quarter values with a 3-month duration. FY observations are represented as Q4. Original source fiscal labels, YTD amounts, tag/status fields, filing dates and derivation accessions remain traceable. Both current ratio and interest coverage were reconciled for every statement. Debt and absent total liabilities remain null.

The borrower source does not provide validated SIC/state/ticker reference values; these optional fields remain null. The pipeline loads the prepared CSV rather than claiming to populate raw SEC staging or independently revalidate source disclosures.

## Halima risk requirements and generation

`docs/risk_policy.md` defines current-ratio and interest-coverage covenants, baseline calibration, effective dates, denominator/missing-input rules, exact-threshold behavior, and all ten internal rating bands. The conservative combination rule selects the weaker of the two ratio grades. Ratings and loan terms are explicitly synthetic and do not assert observed defaults or actual market terms.

`scripts/generate_loan_data.py` uses seed `5132026` and each company's first available filing, originating the loan the following day. It generates 10 loans, 20 covenants and 10 initial ratings. `scripts/load_synthetic_data.py` checks hashes and regenerates expected seed-based records before importing. Stable keys and conflict checks make identical imports repeatable without silently changing history.

Only the two approved covenant types are present. There are zero debt covenants. Formal covenant testing and later rating changes are not fabricated in this milestone.

## Khush setup and reporting design

`scripts/setup_week2.sh` builds a new empty database from the prepared pilot through verification. `scripts/local_db.sh` manages a dedicated local PostgreSQL cluster without starting a system service.

`sql/reports/week2_reports.sql` provides executable read-only daily, weekly, monthly, quarterly and annual query drafts. Statements are filtered by filing availability and explicit as-of dates; exposure counts avoid multiplying loans by their many financial/covenant rows. Annual flow totals are labeled by actual calendar reporting dates rather than uncorrected source fiscal labels. `docs/report_queries.md` explains users, measures and limitations.

`docs/role_design.md` defines analyst, manager, executive, auditor and controlled owner/loader access for later implementation. This completes Week 2's role-design assignment; no claim is made that Week 4 permission grants exist.

## Verification performed

Environment: local PostgreSQL 16.15 (Homebrew). The populated database is `credit_risk_week2`, accessed through the owner-only Unix socket `/tmp/fe513-credit-501` on port 55432. No TCP listener or auto-starting system service is enabled. The helper derives the socket's user ID for other machines.

- Twelve automated unit/integration tests passed with no skips in the configured database environment.
- All 120 normalized financial rows and both ratios reconcile to the supplied CSV; all original source rows are preserved.
- Reimporting both financials and generated records leaves logical record counts and values unchanged.
- Conflicting source data is rejected atomically and leaves the original database unchanged.
- Generation is reproducible, insensitive to input row order and unaffected by later financial observations.
- Rating band boundaries, invalid/missing/nonfinite denominators, duplicate keys and tampered generated files were checked.
- Rollback-only SQL smoke checks verified ratio arithmetic, negative-principal rejection, zero/negative denominator handling and valid negative operating income.
- A clean temporary database was created and rebuilt using the single setup script; the result reconciled successfully. The temporary database was removed afterward.
- All five reporting drafts executed successfully at as-of dates March 1, 2023, December 31, 2025 and February 28, 2026.
- Re-running full schema setup against the populated database failed safely without replacing it.
- Python compilation, shell syntax checks and Git whitespace checks passed.

Final logical counts: 10 borrowers; 120 financial statements; 120 source records; 10 loans; 10 generation records; 20 covenants; 10 initial ratings. Covenant results, watchlist events and rating audit records remain empty because their Week 3 automation has not been implemented.

## Local deliverables and reproduction

From the repository directory:

```sh
sh scripts/local_db.sh start
export DATABASE_URL="$(sh scripts/local_db.sh url)"
python3 scripts/verify_week2.py --csv ../pilot_10_financials.csv
python3 -m unittest discover -s tests -v
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -v as_of_date=2025-12-31 \
  -f sql/reports/week2_reports.sql
```

For a new empty database, export its connection URL and run `sh scripts/setup_week2.sh /path/to/pilot_10_financials.csv`. For the populated project database, use the verification and repeatable loaders instead of re-running schema creation.

Ignored local files under `data/processed/` include:

- `synthetic_loans.csv`, `synthetic_covenants.csv`, `synthetic_ratings.csv` and `generation_manifest.json`.
- `week2_validation.json`, `week2_tests.log`, `clean_rebuild.log`, `repeated_setup.log` and reporting output files.
- `week2_database.sql`: PostgreSQL plain-SQL backup without ownership or privilege commands. Restore only into an empty separate database using `psql "$NEW_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f data/processed/week2_database.sql`.

The original pilot remains unchanged outside the repository. Its SHA-256 is `afc00b29cbb9461fd8e0df2f182048fa4f1378821d5b65e49e59fc242600c56e`. Local database files, generated data, reports containing financial values and the backup are excluded from Git. Source/documentation changes have not been committed or pushed to GitHub.

## Remaining work after Week 2

Week 3: covenant-testing function, breach/watchlist trigger, rating audit trigger, report views and later monitoring behavior. Week 4: role grants and verification, integration and baseline timings. Later: CTAS/materialized snapshot behavior, indexes, controlled benchmarks, end-to-end testing, final report and presentation. Debt-based covenants remain deferred until definitions and lease comparability are validated. Historical validation logs and audits in `docs/data_quality/` remain unchanged as Aania's original records.
