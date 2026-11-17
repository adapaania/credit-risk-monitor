# Change log

## 2026-11-16

- Added the pilot importer, source records, generated loans and covenants, monitoring functions, and audit triggers.
- Added report views, stored monthly/covenant summaries, and tests.
- Replaced separate weekly setup commands with `scripts/project.py`.
- Combined repeated completion notes and simplified the project guides.
- Fixed annual reports so a revised filing replaces the earlier filing for that date instead of adding another quarter.
- Checked a fresh build, an existing-pilot upgrade, report output, and all 33 tests in a temporary PostgreSQL database.
- Risk rules need team review. Role permissions and performance comparisons remain pending.

## 2026-11-09

- Created the repository structure, PostgreSQL schema, and initial ER diagram.
- Downloaded and checked SEC data, then prepared the 10-company pilot.
- Saved completeness reports and source details under `docs/data_quality/`.
- Kept raw and processed financial data out of Git.
