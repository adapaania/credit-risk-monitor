#!/bin/sh
# Full Weeks 1-3 build into a new empty database. Existing pilot: use run_week3.py.
set -eu
: "${DATABASE_URL:?Set DATABASE_URL to an existing empty PostgreSQL database}"
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
pilot_csv=${1:?Usage: sh scripts/setup_week3.sh /path/to/pilot_10_financials.csv}
python_bin=${PYTHON:-python3}
sh "$project_dir/scripts/setup_week2.sh" "$pilot_csv"
"$python_bin" "$project_dir/scripts/run_week3.py" --csv "$pilot_csv"
"$python_bin" "$project_dir/scripts/verify_week3.py" --csv "$pilot_csv"
