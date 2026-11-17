"""Shared validation and psql transport for the local Week 2 pilot (stdlib only)."""
import csv
import hashlib
import io
import json
import os
import re
import subprocess
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PILOT = Path(os.environ.get('PILOT_CSV', ROOT / 'data/processed/pilot_10_financials.csv'))
POLICY_VERSION = 'pilot-v1'
QUARTER_METRICS = ('revenue', 'operating_income', 'interest_expense')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value, label):
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{label}: required finite number') from exc
    if not result.is_finite():
        raise ValueError(f'{label}: required finite number')
    return result


def read_pilot(path):
    path = Path(path)
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        required = {'cik', 'company', 'period_end', 'source_fy', 'source_fp',
                    'inferred_period', 'fiscal_start', 'duration_days', 'accession',
                    'filed', 'source_quarter', 'interest_scope',
                    'assets', 'current_assets', 'current_liabilities',
                    'six_metrics_ready', 'quarter_metrics_ready'}
        for metric in ('assets', 'current_assets', 'current_liabilities') + QUARTER_METRICS:
            required.update((metric, metric + '_tag', metric + '_status'))
        for metric in QUARTER_METRICS:
            required.update(metric + suffix for suffix in
                            ('_quarter', '_quarter_status', '_quarter_method', '_previous_accession'))
        if len(fields) != len(set(fields)) or not required.issubset(fields):
            raise ValueError('Pilot CSV has duplicate headers or missing required columns')
        rows = list(reader)
    if not rows:
        raise ValueError('Pilot CSV is empty')
    keys, names = set(), {}
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError('CSV row width does not match its header')
        cik = int(row['cik'])
        if cik <= 0 or not row['company'].strip():
            raise ValueError('Invalid company identity')
        if cik in names and names[cik] != row['company']:
            raise ValueError(f'Conflicting company names for CIK {cik}')
        names[cik] = row['company']
        end = date.fromisoformat(row['period_end'])
        start = date.fromisoformat(row['fiscal_start'])
        filed = datetime.strptime(row['filed'], '%Y%m%d').date()
        key = (cik, end)
        if key in keys:
            raise ValueError(f'Duplicate company/reporting date: {key}')
        keys.add(key)
        if filed < end or (end - start).days + 1 != int(row['duration_days']):
            raise ValueError(f'Invalid dates/duration: {key}')
        if not 60 <= int(row['duration_days']) <= 380:
            raise ValueError(f'Unsupported source duration: {key}')
        if not 1900 <= int(row['source_fy']) <= 2100:
            raise ValueError(f'Invalid source fiscal year: {key}')
        if row['inferred_period'] not in ('Q1', 'Q2', 'Q3', 'FY'):
            raise ValueError(f'Unsupported fiscal period: {key}')
        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', row['accession']):
            raise ValueError(f'Invalid SEC accession: {key}')
        if not re.fullmatch(r'20\d{2}q[1-4]', row['source_quarter']):
            raise ValueError(f'Invalid source filing batch: {key}')
        if any(row[flag] != 'True' for flag in ('six_metrics_ready', 'quarter_metrics_ready')):
            raise ValueError(f'Pilot core inputs are not ready: {key}')
        for metric in ('assets', 'current_assets', 'current_liabilities') + QUARTER_METRICS:
            number(row[metric], f'{key} {metric}')
            if row[metric + '_status'] != 'present' or not row[metric + '_tag']:
                raise ValueError(f'Missing source mapping: {key} {metric}')
        for metric in QUARTER_METRICS:
            number(row[metric + '_quarter'], f'{key} {metric}_quarter')
            status = row[metric + '_quarter_status']
            if status not in ('reported', 'derived') or not row[metric + '_quarter_method']:
                raise ValueError(f'Invalid quarter provenance: {key} {metric}')
            if status == 'derived' and not row[metric + '_previous_accession']:
                raise ValueError(f'Derived metric lacks prior accession: {key} {metric}')
        if (number(row['assets'], 'assets') <= 0 or
                number(row['current_assets'], 'current_assets') < 0 or
                number(row['current_liabilities'], 'current_liabilities') <= 0 or
                number(row['interest_expense_quarter'], 'interest_expense_quarter') <= 0):
            raise ValueError(f'Invalid pilot balance or denominator: {key}')
    return sorted(rows, key=lambda row: (int(row['cik']), row['period_end']))


def json_copy(table, records):
    """Data uses CSV COPY, never SQL string interpolation; quote every field."""
    buf = io.StringIO(newline='')
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator='\n')
    for record in records:
        writer.writerow([json.dumps(record, sort_keys=True, separators=(',', ':'))])
    return f'COPY {table} (payload) FROM STDIN WITH (FORMAT csv);\n{buf.getvalue()}\\.\n'


def run_sql(sql, database_url=None):
    env = os.environ.copy()
    target = database_url or env.get('DATABASE_URL')
    if not target:
        raise ValueError('Set DATABASE_URL to the project PostgreSQL database')
    try:
        result = subprocess.run(
            [env.get('PSQL', 'psql'), '--dbname', target, '-X', '-q', '-v', 'ON_ERROR_STOP=1', '-A', '-t'],
            input=sql, text=True, capture_output=True, env=env, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError('psql not found; install PostgreSQL and add its bin directory to PATH') from exc
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def apply_sql_files(filenames, database_url=None):
    """Apply SQL files together; a failure rolls back the whole group."""
    statements = [(ROOT / 'sql' / name).read_text() for name in filenames]
    run_sql('BEGIN;\nSELECT pg_advisory_xact_lock(51303);\n' + '\n'.join(statements) + '\nCOMMIT;', database_url)
