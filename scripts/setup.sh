#!/bin/sh
# Usage: DATABASE_URL=postgresql://localhost/credit_risk sh scripts/setup.sh
set -eu
: "${DATABASE_URL:?Set DATABASE_URL to an existing PostgreSQL database}"
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# All files run in one transaction. Existing tables cause a safe failure; nothing is dropped.
psql "$DATABASE_URL" -X --set=ON_ERROR_STOP=1 --single-transaction \
  --file="$project_dir/sql/01_schema.sql" \
  --file="$project_dir/sql/02_staging.sql" \
  --file="$project_dir/sql/03_ratio_views.sql"
