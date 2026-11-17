# Week 3 pilot data quality review

Reviewed November 16, 2026. This adds verification of the locally imported and generated pilot to Aania's earlier SEC preparation audits; it does not replace their historical records.

Run `python3 scripts/check_pilot_quality.py --csv ../pilot_10_financials.csv` from the repository with `DATABASE_URL` configured. The JSON output is saved locally under `data/processed/week3_data_quality.json`. The Week 3 replay also records passed audit reports in `credit.data_quality_runs`.

All 14 checks pass on the supplied pilot. Coverage is 10 companies with 12 observations each, 120 unique reporting dates/CIK pairs, all required quarterly inputs and positive denominators. Original CSV rows, typed fiscal/source metadata, financial amounts and both ratios reconcile with PostgreSQL. Loan terms and covenant thresholds reconcile with the recorded seed and policy. No unvalidated debt covenants, duplicate company/date observations, non-quarter application records, invalid loan/covenant dates or unavailable pilot ratios were found.

There are 86 derived values across revenue, operating income and interest expense. The 83 values whose preceding filing is in this CSV all reconcile to current YTD minus previous YTD with matching CIK, fiscal start, tag and adjacent fiscal period. The remaining three refer to accessions outside the pilot; their recorded provenance is preserved, and this review makes no independent arithmetic claim for those three values.

No underlying financial amounts were changed. Implementation fixes add nonfinite-number handling, original-versus-typed metadata validation, seed/configuration validation and compatibility of base validation with later monitoring history.

Remaining limitations are explicit: 25 candidate debt observations are still unvalidated; optional SIC/state/ticker references are missing; original fiscal labels are retained; source disclosure/restatement comparability was not newly audited against downloaded SEC caches. Negative operating income remains valid numeric evidence, not a missing-data error. These limitations do not justify filling absent amounts with zero.
