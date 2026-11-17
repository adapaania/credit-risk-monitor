# Pilot import checks

Historical check from November 16, 2026. The original 120-row pilot passed 14 checks for coverage, dates, source records, financial values, ratios, and generated terms.

Of 86 calculated quarter values, 83 could be checked against an earlier row in this CSV. The other three refer to filings outside the pilot; their references are kept for review. No financial values were changed.

Debt candidates, optional company reference fields, and source fiscal-year labels still need review. See the [data mapping guide](../../data_mapping.md) for details.

For a current check, set `DATABASE_URL` and run:

```sh
python3 scripts/check_pilot_quality.py --csv data/processed/pilot_10_financials.csv
```

The result is saved locally to `data/processed/data_quality.json`. Run `python3 scripts/project.py check` to also verify monitoring and reports.
