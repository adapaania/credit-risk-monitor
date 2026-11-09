# Credit Risk Monitor

A team project using SEC financial statement data to monitor credit risk.

## Team

- adapaania
- Halima
- Khush

## Data source and coverage

Source: [SEC Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets).

Coverage: 2023 Q1 through 2025 Q4 (three years, 12 quarters).

## Setup

1. Clone this repository to your computer.
2. Run `python3 scripts/download_sec_data.py` (requires Python 3.11+ and curl) to download, verify, and extract all 12 quarters into `data/raw/<quarter>/`, for example `data/raw/2023q1/`. The script keeps the original ZIPs and writes a local SHA-256 download manifest.
3. Run the database setup script once it is added. No setup script is available yet.

Raw data stays on each teammate's computer and is excluded from Git by `.gitignore`.

## Project structure

```text
data/raw/   Local SEC files (ignored by Git)
sql/        CREATE TABLE scripts, views, and triggers
docs/       ER diagram and change log
```
