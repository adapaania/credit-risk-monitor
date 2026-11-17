# Pilot import mapping and provenance

The importer consumes the separately supplied 48-column `pilot_10_financials.csv`. It does not require downloading millions of raw SEC facts again and does not claim to populate the four optional raw SEC staging tables. The imported application data covers 10 companies and 120 actual reporting dates in 2023–2025. Raw data and generated files stay local.

## Application mapping

- `cik` identifies a borrower; `company` becomes `company_name`. Optional SIC, state and ticker are null because the pilot does not provide validated reference values.
- `accession` becomes `accession_number`; `period_end` and `source_quarter` retain their original meanings. A 2026q1 filing batch may support a 2025 reporting date.
- `source_fy` becomes the stored `fiscal_year` as reported. It is not replaced with `reporting_year`, which is a calendar year. Inconsistent original fiscal labels are preserved, not asserted to be corrected. Reporting drafts group actual reporting dates; future fiscal-year analysis must reconcile source discrepancies.
- `inferred_period` becomes `fiscal_period`, with `FY` mapped to `Q4` because imported income amounts are standalone quarters. `duration_months` is 3 for every imported row, including Q4.
- Assets, current assets and current liabilities use the unsuffixed instant values.
- Revenue, operating income and interest expense use the `_quarter` values. The unsuffixed duration amounts remain in source provenance and are never silently treated as quarterly income.
- `is_derived` is true if any of those three quarter metrics has status `derived`.
- Currency is USD, following the source selection policy.
- `liabilities` and `total_debt` remain null. `total_debt_candidate` is preserved in the source row without being promoted to validated application debt.

## Original source record

`credit.financial_statement_sources` links one source row to each imported statement. It retains the entire original CSV row as JSONB, the input CSV filename and SHA-256 hash, the filing date, fiscal start, source YTD duration in days and import timestamp. This preserves tags, mapping statuses, original YTD amounts, interest scope, source fiscal labels, derivation methods and previous accessions. Source duration in days describes the original YTD period; it is not the duration of the normalized quarter stored in the application table.

`filed_on` is the availability boundary for historical report drafts. Date-level SEC filing information is used without asserting intraday availability. Loan origination occurs the following day. Metadata preservation is verified against the supplied CSV; loading does not independently re-audit original SEC disclosures or resolve cross-filing restatement comparability.

## Validation and repeat loading

The importer rejects empty input, duplicate headers, incomplete rows, duplicate CIK/date keys, conflicting names, malformed accessions/dates, inconsistent durations, missing source mappings, incomplete quarter provenance, nonfinite amounts and invalid pilot denominators. Negative operating income is accepted. The loader requires complete inputs for this approved pilot; the ratio view itself preserves missing inputs for future/general use.

All inserts for one financial import occur in one transaction. A shared transaction advisory lock serializes the pilot and synthetic loaders. Reimporting identical input does not duplicate records. Existing conflicting statements or source hashes cause an error and rollback rather than silently replacing historical data. Different accessions for a previously imported borrower/date require an explicit future revision policy. Synthetic loading similarly checks file hashes, recomputes expected seed-based records, and refuses conflicting loans, thresholds or ratings.

## Data dictionary additions

- `financial_statement_sources.statement_id`: primary key and FK to the normalized statement.
- `financial_statement_sources.raw_record`: complete source CSV row, string values preserved.
- `financial_statement_sources.source_sha256`: immutable imported-file fingerprint.
- `financial_statement_sources.filed_on`: original SEC filing availability date.
- `loans.synthetic_key`: unique generated business key; nullable for old smoke fixtures.
- `loan_generation.loan_id`: one generation record per generated loan.
- `loan_generation.baseline_statement_id`: exact statement used at origination.
- `loan_generation.generation_seed`, `policy_version`, `input_sha256`, `manifest`: reproducibility and source traceability.
- `covenants` additionally has a unique loan/metric/effective-start index to support repeatable importing.

The two new tables and the loan key are created by `sql/02_pilot_support.sql`, which can also be applied additively to an existing starter schema. The original Week 2 build does not populate monitoring/snapshot tables. The Week 3 upgrade now populates them and adds business evaluation/closure dates, rating-source references and old/new audit row snapshots; see `week3_monitoring.md`.
