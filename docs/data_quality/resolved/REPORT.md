# Resolved SEC completeness audit

This report supersedes the initial audit in ../REPORT.md. Original results remain as a historical baseline. No database schema was changed.

## Scope and fixes

- Target: actual reporting dates from January 1, 2023 through December 31, 2025, rather than unverified fiscal-year labels. There are 599 dates: 12 for 49 companies and 11 for Flowers Foods. Its next annual reporting date is in January 2026, outside this calendar-date window; this is a boundary effect, not a fabricated missing quarter.
- Added 2022 filing batches for prior-period context and 2026 Q1 for late-filed 2025 results. The target analysis window remains 2023–2025.
- Corrected InterestExpenseNonOperating to the actual case-sensitive tag InterestExpenseNonoperating.
- Supplemented compact quarterly face-statement files with official SEC companyfacts. Matching requires the exact original accession, USD, actual reporting end date, and fiscal-duration start. Later-accession comparative/restated values are not substituted.
- InterestExpenseDebt is a documented fallback for gross debt interest. Its narrower scope is labeled; net interest, tax penalties, and cash interest paid are never substituted.
- Fiscal metadata discrepancies are preserved in metadata_discrepancies.csv. Fiscal period is inferred from duration and form; calendar-date grouping avoids asserting that inconsistent source fiscal-year labels are corrected.
- Standalone-quarter facts are preferred; otherwise current YTD minus previous YTD requires the identical tag and fiscal start. Q4 uses annual minus Q3. Cross-filing derivations retain previous accession and need review for accounting/restatement changes.
- Debt uses the explicitly reported combined short/long-term total, or explicit ShortTermBorrowings plus total LongTermDebt (or current/noncurrent components). Never add a total and its components; never infer absent components as zero. Lease treatment still requires confirmation from the company disclosures before comparing debt ratios across issuers.

## Results

| Metric | Present | Unavailable |
| --- | ---: | ---: |
| assets | 599 | 0 |
| current_assets | 599 | 0 |
| current_liabilities | 599 | 0 |
| revenue | 599 | 0 |
| operating_income | 543 | 56 |
| interest_expense | 469 | 130 |

28 companies have six core metrics on all 12 normalized dates. Across all 50 companies, 415 dates pass core normalization; 74 additionally have an explicit debt amount. These are distinct readiness levels.

## Prepared 10-company pilot

Microsoft, Alphabet, Adobe, Intel, NVIDIA, PepsiCo, Kimberly-Clark, General Mills, Campbell, McCormick.

The pilot has 120 rows with assets, current assets, current liabilities, revenue, operating income, and interest expense, including standalone duration values. It is ready for current-ratio and interest-coverage development. It is not a fully validated total-debt sample; debt gaps and lease-basis differences remain flagged.

Local files: data/processed/pilot_10_financials.csv, resolved_financials.csv, and metric_provenance.csv. These financial data artifacts remain ignored by Git.

## Disposition of remaining gaps

sample_decisions.csv explicitly excludes incomplete companies from the complete-core sample. Missing standard gross interest or operating income is classified as unavailable under the approved mappings, not zero. Company-specific disclosures may support future manual mappings; the script makes no unsupported inference.

Use current ratio and interest coverage for the complete-core pilot. Enable debt-to-assets only where an explicit debt amount and comparable lease treatment are validated; do not generate covenant pass/fail results from missing inputs.

## Reproduce

```sh
python3 scripts/download_sec_data.py --quarters 2022q1 2022q2 2022q3 2022q4 2026q1
python3 scripts/fetch_companyfacts.py
python3 scripts/resolve_completeness.py
```

Source definitions: [SEC Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets) and [SEC XBRL API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces). API response SHA-256 hashes are in resolution_log.json; tag definitions are in mapping_definitions.csv.
