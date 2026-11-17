#!/bin/sh
# Reproducible schema + pilot + synthetic data build for a new empty database.
set -eu
: "${DATABASE_URL:?Set DATABASE_URL to an existing empty PostgreSQL database}"
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
pilot_csv=${1:?Usage: sh scripts/setup_week2.sh /path/to/pilot_10_financials.csv}
python_bin=${PYTHON:-python3}
sh "$project_dir/scripts/setup.sh"
"$python_bin" "$project_dir/scripts/load_pilot_data.py" --csv "$pilot_csv"
"$python_bin" "$project_dir/scripts/generate_loan_data.py" --csv "$pilot_csv"
"$python_bin" "$project_dir/scripts/load_synthetic_data.py" --csv "$pilot_csv"
"$python_bin" "$project_dir/scripts/verify_week2.py" --csv "$pilot_csv"
