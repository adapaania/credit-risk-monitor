# Change log

## 2026-11-09

- Added the starter README, SQL folder, and documentation folder.
- Excluded local SEC raw data from Git.
- Added PostgreSQL core/staging schemas, ratio view, initial ER diagram, and transactional schema setup script.
- Validated setup, ratio calculations, zero-denominator handling, and negative-principal rejection in an isolated PostgreSQL 14 database.
- Importer, covenant logic, generated data, roles, and reports are pending.
- Audited 50 shortlisted companies across 12 SEC filing batches (42,797,577 numeric rows): 573 selected reporting dates; all six mapped metrics present together on 227 dates. Interest expense needs mapping review on 314 dates; total-debt definition and duration normalization remain pending.
- Saved reproducible completeness script, company/filing coverage CSVs, candidate-tag inventory, and JSON scan log under docs/data_quality/.
