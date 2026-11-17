"""Check the pilot CSV, imported financials, and generated loan terms."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from pilot_common import ROOT, QUARTER_METRICS, digest, read_pilot, run_sql
from verify_data import verify
from generate_loan_data import build_records


def check_generated_configuration(rows,database_url=None):
    data=json.loads(run_sql('''SELECT jsonb_build_object(
        'loans',(SELECT jsonb_agg(to_jsonb(x)) FROM (
          SELECT l.*,b.cik,g.generation_seed,g.policy_version,g.input_sha256,f.accession_number AS baseline_accession
          FROM credit.loans l JOIN credit.borrowers b USING(borrower_id)
          JOIN credit.loan_generation g USING(loan_id)
          JOIN credit.financial_statements f ON f.statement_id=g.baseline_statement_id) x),
        'covenants',(SELECT jsonb_agg(to_jsonb(c)) FROM credit.covenants c));''',database_url))
    mismatches=[]
    expected_by_seed={seed:build_records(rows,seed) for seed in {l['generation_seed'] for l in data['loans'] or []}}
    for loan in data['loans'] or []:
        records=expected_by_seed[loan['generation_seed']]
        expected=next((r for r in records['synthetic_loans.csv'] if r['synthetic_key']==loan['synthetic_key']),None)
        if expected is None or loan['policy_version']!='pilot-v1':
            mismatches.append({'loan_id':loan['loan_id'],'field':'identity/policy'}); continue
        for field in ('principal','annual_interest_rate'):
            if Decimal(str(loan[field]))!=Decimal(expected[field]): mismatches.append({'loan_id':loan['loan_id'],'field':field})
        for field in ('originated_on','matures_on','currency','baseline_accession'):
            if loan[field]!=expected[field]: mismatches.append({'loan_id':loan['loan_id'],'field':field})
        covenants=[c for c in data['covenants'] if c['loan_id']==loan['loan_id']]
        if len(covenants)!=2: mismatches.append({'loan_id':loan['loan_id'],'field':'covenant_count'})
        for exp in (c for c in records['synthetic_covenants.csv'] if c['synthetic_key']==loan['synthetic_key']):
            actual=next((c for c in covenants if c['metric']==exp['metric']),None)
            if actual is None or any(actual[k]!=exp[k] for k in ('comparison','effective_from','effective_to')) or Decimal(str(actual['threshold']))!=Decimal(exp['threshold']):
                mismatches.append({'loan_id':loan['loan_id'],'field':exp['metric']})
    return mismatches


def audit(path, database_url=None):
    rows = read_pilot(path)
    checks, warnings = [], []
    def check(name, passed, details):
        checks.append({'check': name, 'passed': bool(passed), 'details': details})
    counts = Counter(r['cik'] for r in rows)
    check('pilot_coverage', len(counts)==10 and len(rows)==120 and all(n==12 for n in counts.values()),
          {'companies':len(counts),'rows':len(rows),'observations_per_company':dict(counts)})
    check('calendar_reporting_window', all('2023-01-01'<=r['period_end']<='2025-12-31' for r in rows),
          'Actual reporting dates; fiscal calendars may differ')
    check('reporting_year_labels', all(int(r['reporting_year'])==int(r['period_end'][:4]) for r in rows),
          'Calendar year label agrees with reporting-end date')
    check('source_batch_dates', all(r['source_quarter']==f'{r["filed"][:4]}q{(int(r["filed"][4:6])-1)//3+1}' for r in rows),
          'Filing batch agrees with filing date, not the financial reporting quarter')
    by_accession={r['accession']:r for r in rows}
    in_pilot=outside=0; errors=[]
    for r in rows:
        for metric in QUARTER_METRICS:
            if r[metric+'_quarter_status']!='derived': continue
            previous=by_accession.get(r[metric+'_previous_accession'])
            if previous is None:
                outside+=1; continue
            in_pilot+=1
            if (previous['cik']!=r['cik'] or previous['fiscal_start']!=r['fiscal_start'] or
                previous[metric+'_tag']!=r[metric+'_tag'] or previous['period_end']>=r['period_end'] or
                previous['inferred_period']!={'Q2':'Q1','Q3':'Q2','FY':'Q3'}.get(r['inferred_period']) or
                Decimal(r[metric])-Decimal(previous[metric])!=Decimal(r[metric+'_quarter'])):
                errors.append({'cik':r['cik'],'period_end':r['period_end'],'metric':metric})
    check('derived_quarter_arithmetic', not errors, {'verified_values':in_pilot,'errors':errors})
    if outside: warnings.append({'code':'prior_filing_outside_pilot','values':outside,
        'meaning':'Previous accessions are recorded, but their source values are absent from the supplied CSV; no independent arithmetic verification claimed.'})
    warnings.extend([
        {'code':'debt_definition_deferred','candidate_rows':sum(bool(r['total_debt_candidate']) for r in rows)},
        {'code':'optional_reference_fields_unavailable','fields':['sic','state','ticker']},
        {'code':'source_fiscal_labels_preserved','meaning':'Fiscal labels are retained as reported; calendar reporting dates are used for annual grouping.'},
        {'code':'source_disclosures_not_reaudited','meaning':'This audit reconciles the supplied pilot and database, not fresh SEC downloads or accounting restatement comparability.'}])
    reconciliation=verify(path,database_url)
    check('database_financial_and_ratio_reconciliation', reconciliation['status']=='passed',
          {'rows_reconciled':reconciliation['financial_values_and_ratios_reconciled'],
           'original_rows_preserved':reconciliation['original_rows_preserved']})
    mismatches=check_generated_configuration(rows,database_url)
    check('seeded_loan_and_covenant_configuration',not mismatches,{'mismatches':mismatches})
    sql='''SELECT jsonb_build_object(
    'borrower_statement_duplicates',(SELECT count(*) FROM (SELECT borrower_id,period_end FROM credit.financial_statements
        GROUP BY borrower_id,period_end HAVING count(*)>1) x),
    'non_quarter_statements',(SELECT count(*) FROM credit.financial_statements WHERE duration_months<>3),
    'invalid_denominators',(SELECT count(*) FROM credit.financial_statements WHERE current_liabilities<=0 OR interest_expense<=0),
    'missing_ratios',(SELECT count(*) FROM credit.financial_ratios WHERE current_ratio IS NULL OR interest_coverage IS NULL),
    'debt_covenants',(SELECT count(*) FROM credit.covenants WHERE metric='debt_to_assets'),
    'loan_currency_or_date_errors',(SELECT count(*) FROM credit.loans WHERE currency<>'USD' OR originated_on>=matures_on),
    'covenant_date_errors',(SELECT count(*) FROM credit.covenants c JOIN credit.loans l USING(loan_id)
         WHERE c.effective_from<l.originated_on OR c.effective_from>=l.matures_on OR c.effective_to>l.matures_on));'''
    db=json.loads(run_sql(sql,database_url))
    for key,value in db.items(): check(key,value==0,{'violations':value})
    return {'status':'passed' if all(c['passed'] for c in checks) else 'failed',
            'checked_at_utc':datetime.now(timezone.utc).isoformat(),'input_sha256':digest(path),
            'checks':checks,'warnings':warnings,'financial_values_changed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',required=True,type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'data/processed/data_quality.json')
    a=p.parse_args(); report=audit(a.csv)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if report['status']!='passed': raise SystemExit(1)
