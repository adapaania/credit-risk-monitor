"""Set up, check, or report on the credit-risk pilot."""
import argparse
import json
import os
import subprocess
from pathlib import Path

from generate_loan_data import generate
from load_pilot_data import load as load_financials
from load_synthetic_data import load as load_loans
from pilot_common import DEFAULT_PILOT, ROOT, read_pilot
from run_monitoring import run as monitor
from verify_monitoring import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'check', 'monitor', 'reports'])
    parser.add_argument('--csv', type=Path, default=DEFAULT_PILOT)
    args = parser.parse_args()
    if not os.environ.get('DATABASE_URL'):
        parser.error('Set DATABASE_URL to your PostgreSQL database first.')

    if args.command == 'setup':
        # Catch a missing or invalid CSV before creating database tables.
        try:
            read_pilot(args.csv)
        except (OSError, ValueError, KeyError) as error:
            parser.error(str(error))

    if args.command == 'setup':
        subprocess.run(['sh', str(ROOT / 'scripts/setup.sh')], check=True)
        load_financials(args.csv)
        generate(args.csv, ROOT / 'data/processed')
        load_loans(args.csv, ROOT / 'data/processed')
        monitor(args.csv)
        result = verify(args.csv)
    elif args.command == 'monitor':
        monitor(args.csv)
        result = verify(args.csv)
    elif args.command == 'check':
        result = verify(args.csv)
    else:
        # Keep psql column names and formatting for readable reports.
        subprocess.run([
            os.environ.get('PSQL', 'psql'), os.environ['DATABASE_URL'],
            '-X', '-v', 'ON_ERROR_STOP=1', '-f',
            str(ROOT / 'sql/reports/run_reports.sql'),
        ], check=True)
        return
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
