"""Atomically load a normalized pilot CSV, preserving its complete original rows."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from pilot_common import QUARTER_METRICS, digest, json_copy, read_pilot, run_sql


def load(path, database_url=None):
    rows = read_pilot(path)
    sha = digest(path)
    records = []
    for row in rows:
        record = {key: row[key] for key in ('cik', 'company', 'period_end', 'source_quarter',
                   'accession', 'source_fy', 'fiscal_start', 'duration_days',
                   'assets', 'current_assets', 'current_liabilities')}
        record.update(filed_on=datetime.strptime(row['filed'], '%Y%m%d').date().isoformat(),
                      fiscal_period='Q4' if row['inferred_period'] == 'FY' else row['inferred_period'],
                      is_derived=any(row[m + '_quarter_status'] == 'derived' for m in QUARTER_METRICS),
                      source_file=Path(path).name, source_sha256=sha, raw_record=row)
        record.update({m: row[m + '_quarter'] for m in QUARTER_METRICS})
        records.append(record)
    sql = '''BEGIN;
SELECT pg_advisory_xact_lock(51302);
CREATE TEMP TABLE pilot_json (payload jsonb NOT NULL) ON COMMIT DROP;
'''
    sql += json_copy('pilot_json', records)
    sql += '''
CREATE TEMP TABLE incoming ON COMMIT DROP AS
SELECT x.* FROM pilot_json j CROSS JOIN LATERAL jsonb_to_record(j.payload) AS x(
    cik bigint, company text, period_end date, source_quarter text, accession text,
    source_fy integer, fiscal_start date, duration_days integer, filed_on date,
    fiscal_period text, is_derived boolean, source_file text, source_sha256 text,
    raw_record jsonb, assets numeric, current_assets numeric, current_liabilities numeric,
    revenue numeric, operating_income numeric, interest_expense numeric);
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM incoming i JOIN credit.borrowers b USING(cik)
               WHERE b.company_name IS DISTINCT FROM i.company) THEN
        RAISE EXCEPTION 'Existing borrower name conflicts with pilot';
    END IF;
    IF EXISTS (
        SELECT 1 FROM incoming i JOIN credit.borrowers b USING(cik)
        JOIN credit.financial_statements f ON f.borrower_id=b.borrower_id AND f.period_end=i.period_end
        LEFT JOIN credit.financial_statement_sources p ON p.statement_id=f.statement_id
        WHERE ROW(f.accession_number, f.duration_months, f.fiscal_year, f.fiscal_period,
                  f.source_quarter, f.currency, f.assets, f.current_assets, f.current_liabilities,
                  f.revenue, f.operating_income, f.interest_expense, f.is_derived, f.total_debt,
                  p.source_sha256, p.raw_record)
        IS DISTINCT FROM
              ROW(i.accession, 3, i.source_fy, i.fiscal_period, i.source_quarter, 'USD'::bpchar,
                  i.assets, i.current_assets, i.current_liabilities, i.revenue,
                  i.operating_income, i.interest_expense, i.is_derived, NULL::numeric,
                  i.source_sha256, i.raw_record)
    ) THEN RAISE EXCEPTION 'Existing statement/source conflicts with pilot; no records replaced'; END IF;
END $$;
INSERT INTO credit.borrowers(cik, company_name)
SELECT DISTINCT cik, company FROM incoming ORDER BY cik
ON CONFLICT(cik) DO NOTHING;
INSERT INTO credit.financial_statements
    (borrower_id, source_quarter, accession_number, period_end, fiscal_year, fiscal_period,
     duration_months, assets, current_assets, current_liabilities, revenue, operating_income,
     interest_expense, is_derived)
SELECT b.borrower_id, i.source_quarter, i.accession, i.period_end, i.source_fy, i.fiscal_period,
       3, i.assets, i.current_assets, i.current_liabilities, i.revenue, i.operating_income,
       i.interest_expense, i.is_derived
FROM incoming i JOIN credit.borrowers b USING(cik) ORDER BY i.cik, i.period_end
ON CONFLICT(borrower_id, accession_number, period_end, duration_months) DO NOTHING;
INSERT INTO credit.financial_statement_sources
    (statement_id, filed_on, fiscal_start, source_duration_days, source_file, source_sha256, raw_record)
SELECT f.statement_id, i.filed_on, i.fiscal_start, i.duration_days, i.source_file, i.source_sha256, i.raw_record
FROM incoming i JOIN credit.borrowers b USING(cik)
JOIN credit.financial_statements f ON f.borrower_id=b.borrower_id AND f.accession_number=i.accession
    AND f.period_end=i.period_end AND f.duration_months=3
ON CONFLICT(statement_id) DO NOTHING;
COMMIT;
'''
    run_sql(sql, database_url)
    return {'financial_statements': len(rows), 'borrowers': len({r['cik'] for r in rows}),
            'source_sha256': sha, 'debt_imported': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(load(args.csv), indent=2))
