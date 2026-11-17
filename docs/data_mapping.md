# Pilot data mapping

The importer reads `data/processed/pilot_10_financials.csv`. It loads the prepared 120-row pilot, not the raw SEC staging files.

| CSV field | Database field or use |
| --- | --- |
| `cik`, `company` | Borrower CIK and company name |
| `accession` | SEC filing reference |
| `period_end` | Actual reporting date |
| `source_quarter` | Batch in which the filing appeared |
| `source_fy` | Original fiscal-year label, kept as reported |
| `inferred_period` | Fiscal period; `FY` becomes `Q4` for the normalized quarter |
| `assets`, `current_assets`, `current_liabilities` | Balance-sheet values at the reporting date |
| `revenue_quarter`, `operating_income_quarter`, `interest_expense_quarter` | Standalone quarter amounts |
| `filed` | Earliest filing date used for monitoring |

All imported financial amounts are USD. `duration_months` is 3. `is_derived` is true if any quarter amount was calculated from year-to-date values.

Total liabilities and total debt stay null because they are not validated in this pilot. Debt candidates remain in the original source row. SIC, state, and ticker also stay null until checked reference data is supplied.

## Source records

`credit.financial_statement_sources` stores each complete CSV row as JSON, its filename and SHA-256 hash, filing date, fiscal start, and original duration in days. This keeps the tags, year-to-date amounts, interest scope, calculation methods, and previous filing references available for review. Original duration describes the source period, not the normalized quarter.

A filing batch can be in 2026 even when the financial reporting date is in 2025. Some source fiscal-year labels are inconsistent. Reports group by actual reporting dates instead of treating those labels as corrected fiscal years.

## Import checks

The importer checks company/date duplicates, headers, dates, source tags, quarter calculation references, and required numbers. Negative operating income is allowed. Missing, nonfinite, or nonpositive denominators are rejected for this prepared pilot.

A financial import runs in one transaction. Loading the same file again does not add duplicates. Conflicting values or source hashes cause an error instead of replacing existing data. The complete setup uses several steps; see the README for retry instructions.

`credit.loan_generation` records each synthetic loan's baseline statement, seed, policy version, and input hash. These details let the team reproduce the generated data. Import checks compare the database to the supplied CSV; they do not repeat the original SEC disclosure review.
