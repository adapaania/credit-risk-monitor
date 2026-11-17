# Reports

Run `python3 scripts/project.py reports` after setup. Reports use the date stored in `reporting.report_context`.

| View | Purpose |
| --- | --- |
| `v_daily_monitoring` | Active loans, latest available financials, ratings, and test status |
| `v_weekly_maturities` | Loans maturing within 90 days, grouped by week |
| `v_monthly_portfolio` | Month-end loan amounts, rates, and watchlist borrower counts |
| `v_quarterly_covenant_results` | Recorded covenant tests and their evidence |
| `v_annual_financials` | Quarterly income totals grouped by calendar reporting year |
| `v_watchlist` | Open and closed breach events at the selected date |
| `v_rating_history` | Rating assessments and previous grades |

All views are in the `reporting` schema. Annual totals use the latest available filing for each reporting date. The quarter count shows partial years; calendar-year totals can differ from a company's fiscal-year report. Balance-sheet assets are not summed across quarters.

`monthly_portfolio_ctas` and `covenant_summary_ctas` store report results. Refresh them after changing inputs or closing events; see [monitoring](monitoring.md). Portfolio totals count each active loan once and each watchlist borrower once, even when that borrower has several events.
