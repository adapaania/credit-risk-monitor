# Credit Risk Monitor

FE513 team project by Aania Adap, Halima Younus, and Khush Mehta.

We use SEC financial statements and generated loan data to demonstrate borrower monitoring. The pilot has 10 companies and 120 quarterly records with reporting dates in 2023–2025. Loans, covenants, and ratings are synthetic.

## First-time setup

You need Python 3.11+, PostgreSQL 14+, and `psql` on your PATH. Run these commands from the repository folder.

1. Get `pilot_10_financials.csv` from Aania and place it in `data/processed/`. Create that folder if needed. The CSV and database files are kept off GitHub.
2. Start your PostgreSQL server. Create a new, empty database named `credit_risk` in pgAdmin, or run:

   ```sh
   createdb credit_risk
   ```

3. Connect to that database and build the pilot:

   ```sh
   export DATABASE_URL=postgresql:///credit_risk
   python3 scripts/project.py setup
   ```

   If your server uses another connection address, replace `DATABASE_URL` with that address. For a CSV in another folder, add `--csv /path/to/pilot_10_financials.csv`.

Setup creates the tables, imports financials, generates loans and covenants, and runs monitoring. It checks the results before reporting success. Pulling the code alone does not create or populate your database. Run setup only on an empty database; it does not erase existing tables. A failed build may leave earlier completed steps, so use a new empty database when retrying a failed setup.

## Check and use the database

Keep `DATABASE_URL` set in each terminal session.

```sh
python3 scripts/project.py check
python3 -m unittest discover -s tests -v
python3 scripts/project.py reports
```

The tests use `data/processed/pilot_10_financials.csv` by default. Set `PILOT_CSV` if you keep it elsewhere. Database tests are skipped when `DATABASE_URL` is not set.

For an existing pilot database, `python3 scripts/project.py monitor` installs or reruns monitoring. Repeated runs keep the same results rather than duplicating them. It also upgrades a loaded pilot that has the source and loan-generation tables. It does not import a missing CSV or load missing loans.

## Team and project notes

- [Tasks and remaining work](docs/IMPLEMENTATION_PLAN.md)
- [CSV fields and source records](docs/data_mapping.md)
- [Covenants and rating rules](docs/risk_policy.md) — proposed rules for Halima and the team to review
- [Monitoring, reports, and optional local server](docs/monitoring.md)
- [Planned database permissions](docs/role_design.md)
- [ER diagram](docs/er_diagram.md) and [change log](docs/CHANGELOG.md)
- [SEC data checks and download steps](docs/data_quality/resolved/REPORT.md)

Debt-based covenants are disabled until debt amounts and lease treatment are checked. Role permissions and performance comparisons are still pending. This is a small pilot, not the several-hundred-company sample in the original proposal.
