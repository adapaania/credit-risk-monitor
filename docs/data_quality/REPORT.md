# SEC shortlist completeness audit

Checked 50 companies and 573 selected reporting dates across 12 filing batches.

## Method and limits

- Source: downloaded 2023 Q1–2025 Q4 SEC Financial Statement Data Sets. No raw files were changed.
- Includes original 10-K/10-Q filings with reporting dates in calendar 2023–2025; chooses the latest original filing for each company/reporting date. Amendments are excluded.
- Uses USD, non-dimensional, non-co-registrant US-GAAP facts at the filing reporting date. Company extensions and net-interest concepts are not automatically mapped.
- Missing standard tags mean mapping or source review is needed; they do not prove the underlying financial information is unavailable.
- Instant metrics require qtrs=0; duration metrics accept standalone quarters or matching year-to-date periods, and annual values for FY. Presence does not establish comparable standalone-quarter ratios.
- Conflicting values for the same tag/duration are flagged ambiguous.
- Debt component availability is reported separately. Total debt and lease treatment still need an agreed definition; no total debt completeness claim is made.
- Fiscal coverage expects Q1/Q2/Q3/FY for fiscal 2023–2025. Fiscal-year labels can differ from calendar years. FY2025 filings made in 2026 are outside the downloaded batches.

## Metric summary

| Metric | Present | Missing standard mapping | Ambiguous |
| --- | ---: | ---: | ---: |
| assets | 572 | 1 | 0 |
| current_assets | 572 | 1 | 0 |
| current_liabilities | 572 | 1 | 0 |
| revenue | 571 | 2 | 0 |
| operating_income | 510 | 63 | 0 |
| interest_expense | 259 | 314 | 0 |

All six mapped metrics occur together on 227 of 573 reporting dates. This excludes total-debt readiness and duration normalization.

## Results

| Company | Reporting dates | Dates with all six mapped metrics | Missing fiscal periods |
| --- | ---: | ---: | --- |
| Apple | 11 | 0 | 2023Q1 |
| Microsoft | 11 | 0 | 2023Q1;2023Q2 |
| Alphabet | 11 | 0 | 2025FY |
| Meta Platforms | 11 | 0 | 2025FY |
| Oracle | 12 | 12 | 2023Q1;2023Q2 |
| Adobe | 11 | 6 | 2025FY |
| Salesforce | 12 | 0 | 2023Q1;2023Q2;2023Q3;2025FY |
| Intuit | 12 | 0 | 2023Q1 |
| ServiceNow | 11 | 0 | 2025FY |
| Cisco Systems | 12 | 6 | 2023Q1 |
| IBM | 11 | 0 | 2025FY |
| Automatic Data Processing | 11 | 0 | 2023Q1;2023Q2 |
| Intel | 11 | 0 | 2025FY |
| Advanced Micro Devices | 11 | 11 | 2025FY |
| NVIDIA | 12 | 6 | 2023Q1;2023Q2;2023Q3;2025FY |
| Qualcomm | 11 | 11 | 2023Q1 |
| Texas Instruments | 11 | 11 | 2025FY |
| Analog Devices | 12 | 6 | None |
| Applied Materials | 12 | 6 | None |
| Lam Research | 11 | 0 | 2023Q1;2023Q2 |
| Coca-Cola | 11 | 5 | 2025FY |
| PepsiCo | 11 | 11 | 2025FY |
| Procter & Gamble | 11 | 5 | 2023Q1;2023Q2 |
| Colgate-Palmolive | 11 | 0 | 2025FY |
| Kimberly-Clark | 11 | 11 | 2025FY |
| General Mills | 12 | 12 | 2023Q1;2023Q2 |
| Mondelez International | 11 | 0 | 2025FY |
| Hershey | 11 | 0 | 2025FY |
| Campbell | 12 | 12 | 2023Q1 |
| Conagra Brands | 12 | 0 | 2023Q1;2023Q2 |
| Kraft Heinz | 11 | 11 | 2023Q1;2025FY |
| Church & Dwight | 11 | 11 | 2025FY |
| Clorox | 11 | 0 | 2023Q1;2023Q2 |
| McCormick | 11 | 11 | 2025FY |
| Flowers Foods | 11 | 11 | 2025FY |
| Walmart | 12 | 0 | 2023Q1;2023Q2;2023Q3;2025FY |
| Target | 12 | 6 | 2025FY |
| Home Depot | 12 | 6 | 2025FY |
| Lowe's | 12 | 0 | 2025FY |
| Costco | 12 | 12 | 2023Q1 |
| TJX Companies | 12 | 0 | 2023Q1;2023Q2;2023Q3;2025FY |
| Ross Stores | 12 | 0 | 2025FY |
| Dollar General | 12 | 5 | 2025FY |
| Dollar Tree | 12 | 0 | 2025FY |
| Best Buy | 12 | 10 | 2023Q1;2023Q2;2023Q3;2025FY |
| Kroger | 12 | 7 | 2025FY |
| AutoZone | 12 | 0 | 2023Q1 |
| O'Reilly Automotive | 11 | 0 | 2023Q2;2025FY |
| Tractor Supply | 11 | 6 | 2025FY |
| Ulta Beauty | 12 | 0 | 2025FY |

## Follow-up

Review missing/ambiguous metrics in filing_completeness.csv and candidate_tag_inventory.csv before selecting the final sample. Resolve interest expense and debt mappings, normalize duration values, and obtain 2026 filing batches where FY2025 coverage is needed. Keep missing values distinct from zero.

Rerun: `python3 scripts/check_completeness.py`.
