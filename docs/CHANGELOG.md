# Change log

## 2026-11-09

- Added the starter README, SQL folder, and documentation folder.
- Excluded local SEC raw data from Git.
- Added PostgreSQL core/staging schemas, ratio view, initial ER diagram, and transactional schema setup script.
- Validated setup, ratio calculations, zero-denominator handling, and negative-principal rejection in an isolated PostgreSQL 14 database.
- Importer, covenant logic, generated data, roles, and reports are pending.
- Audited 50 shortlisted companies across 12 SEC filing batches (42,797,577 numeric rows): 573 selected reporting dates; all six mapped metrics present together on 227 dates. Interest expense needs mapping review on 314 dates; total-debt definition and duration normalization remain pending.
- Saved reproducible completeness script, company/filing coverage CSVs, candidate-tag inventory, and JSON scan log under docs/data_quality/.
- Resolved audit tag capitalization, supplemented compact data with official SEC companyfacts, and added boundary filing batches. Revised scope uses actual reporting dates in 2023–2025: 599 dates, with 28 companies passing six core metrics and quarter normalization on all 12 dates.
- Prepared a local 120-row pilot for ten companies. Preserved unavailable facts and unvalidated debt/lease scope as explicit exclusions; added provenance, source hashes, metadata discrepancy log, and sample decisions in docs/data_quality/resolved/.
