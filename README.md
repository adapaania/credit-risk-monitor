# Credit Risk Monitor

A team project using SEC financial statement data to monitor credit risk.

## Team

- adapaania
- Halima
- Khush

## Data source and coverage

Source: [SEC Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets).

Planned coverage: two years (eight quarters). Confirm the exact quarter range before downloading; `2026q2` is the quarter used in the initial folder example.

## Setup

1. Clone this repository to your computer.
2. Download the agreed SEC quarterly data sets and extract each into `data/raw/<quarter>/`, for example `data/raw/2026q2/`.
3. Run the database setup script once it is added. No setup script is available yet.

Raw data stays on each teammate's computer and is excluded from Git by `.gitignore`.

## Project structure

```text
data/raw/   Local SEC files (ignored by Git)
sql/        CREATE TABLE scripts, views, and triggers
docs/       ER diagram and change log
```
