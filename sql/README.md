# SQL files

Use the [project setup command](../README.md) to build an empty PostgreSQL 14+ database.

| File | Purpose |
| --- | --- |
| `01_schema.sql` | Borrowers, financials, loans, covenants, ratings, and watchlist tables |
| `02_staging.sql` | Raw SEC staging tables; not populated by the pilot loader |
| `02_pilot_support.sql` | Original CSV rows and loan-generation details |
| `03_ratio_views.sql` | Current ratio and interest coverage |
| `04_risk_monitoring.sql` | Covenant tests, watchlist handling, and rating audits |
| `05_reporting.sql` | Report views and stored summaries |
| `reports/run_reports.sql` | Display the reports |
| `check_schema.sql` | Optional checks whose fixtures are rolled back |

`scripts/setup.sh` creates only the starter schema. Role grants and performance-tuning scripts are still pending.
