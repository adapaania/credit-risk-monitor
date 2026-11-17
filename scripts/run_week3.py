"""Upgrade an existing Week 2 pilot, replay historical monitoring and refresh reports."""
import argparse
import calendar
import json
from datetime import date, datetime
from pathlib import Path
from check_pilot_quality import audit
from pilot_common import ROOT, json_copy, read_pilot, run_sql


def run(path, as_of=None, database_url=None):
    rows=read_pilot(path)
    last_filed=max(datetime.strptime(r['filed'],'%Y%m%d').date() for r in rows)
    cutoff=as_of or last_filed.replace(day=calendar.monthrange(last_filed.year,last_filed.month)[1])
    if cutoff>date.today(): raise ValueError('Report date cannot be in the future')
    quality=audit(path,database_url)
    if quality['status']!='passed': raise ValueError('Data-quality failures; monitoring was not run')
    migration='BEGIN; SELECT pg_advisory_xact_lock(51303);\n'
    for file in ('03_ratio_views.sql','04_risk_monitoring.sql','05_reporting.sql'):
        migration+=(ROOT/'sql'/file).read_text()+'\n'
    migration+='COMMIT;'
    run_sql(migration,database_url)
    sql='''BEGIN;
SELECT pg_advisory_xact_lock(51302);
SELECT pg_advisory_xact_lock(51303);
CREATE TEMP TABLE quality_json(payload jsonb) ON COMMIT DROP;
CREATE TEMP TABLE run_date(payload jsonb) ON COMMIT DROP;
'''
    sql+=json_copy('quality_json',[quality])+json_copy('run_date',[{'as_of':cutoff.isoformat()}])
    sql+='''
DO $$ DECLARE r record; BEGIN
    -- Baseline is assessed at origination; later statements at filing availability.
    FOR r IN
        SELECT l.loan_id,f.statement_id,greatest(p.filed_on,l.originated_on) AS evaluation_date
        FROM credit.loans l JOIN credit.financial_statements f USING(borrower_id)
        JOIN credit.financial_statement_sources p USING(statement_id)
        WHERE f.duration_months=3 AND greatest(p.filed_on,l.originated_on)<l.matures_on
          AND greatest(p.filed_on,l.originated_on)<=(SELECT (payload->>'as_of')::date FROM run_date)
          AND NOT EXISTS (SELECT 1 FROM credit.financial_statements newer
              JOIN credit.financial_statement_sources np ON np.statement_id=newer.statement_id
              WHERE newer.borrower_id=f.borrower_id AND newer.period_end=f.period_end AND newer.duration_months=3
              AND np.filed_on<=greatest(p.filed_on,l.originated_on)
              AND (np.filed_on,newer.accession_number,newer.statement_id)>(p.filed_on,f.accession_number,f.statement_id))
        ORDER BY evaluation_date,l.loan_id,f.period_end
    LOOP
        PERFORM credit.test_loan_covenants(r.loan_id,r.statement_id,r.evaluation_date);
        PERFORM credit.record_financial_rating(r.loan_id,r.statement_id,r.evaluation_date);
    END LOOP;
END $$;
SELECT reporting.refresh_reports((SELECT (payload->>'as_of')::date FROM run_date));
INSERT INTO credit.data_quality_runs(input_sha256,passed,report)
SELECT payload->>'input_sha256',true,payload FROM quality_json;
COMMIT;
'''
    run_sql(sql,database_url)
    out=ROOT/'data/processed'
    out.mkdir(parents=True,exist_ok=True)
    (out/'week3_data_quality.json').write_text(json.dumps(quality,indent=2)+'\n')
    return {'status':'completed','as_of_date':cutoff.isoformat(),'quality_checks':len(quality['checks'])}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',required=True,type=Path)
    p.add_argument('--as-of',type=date.fromisoformat)
    a=p.parse_args(); print(json.dumps(run(a.csv,a.as_of),indent=2))
