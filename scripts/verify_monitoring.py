"""Independently reconcile monitoring results, rating history, watchlist and report CTAS."""
import argparse
import json
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from generate_loan_data import risk_rating
from pilot_common import ROOT, read_pilot, run_sql
from verify_data import verify as verify_base
from check_pilot_quality import check_generated_configuration


def verify(path,database_url=None):
    base=verify_base(path,database_url)
    data=json.loads(run_sql('''SELECT jsonb_build_object(
      'as_of',(SELECT as_of_date FROM reporting.report_context),
      'loans',(SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT l.*,b.cik FROM credit.loans l JOIN credit.borrowers b USING(borrower_id)) x),
      'covenants',(SELECT jsonb_agg(to_jsonb(c)) FROM credit.covenants c),
      'results',(SELECT jsonb_agg(to_jsonb(r)) FROM credit.covenant_test_results r),
      'ratings',(SELECT jsonb_agg(to_jsonb(h)) FROM credit.risk_rating_history h),
      'audits',(SELECT jsonb_agg(to_jsonb(a)) FROM credit.rating_audit a),
      'statements',(SELECT jsonb_agg(jsonb_build_object('statement_id',f.statement_id,'cik',b.cik,
                   'accession',f.accession_number)) FROM credit.financial_statements f JOIN credit.borrowers b USING(borrower_id)),
      'events',(SELECT jsonb_agg(to_jsonb(w)) FROM credit.watchlist w),
      'report_months',(SELECT count(*) FROM reporting.monthly_portfolio_ctas),
      'report_summary_rows',(SELECT count(*) FROM reporting.covenant_summary_ctas),
      'ctas_month_mismatches',(SELECT count(*) FROM (
        (SELECT * FROM reporting.monthly_portfolio_ctas EXCEPT SELECT * FROM reporting.v_monthly_portfolio)
        UNION ALL (SELECT * FROM reporting.v_monthly_portfolio EXCEPT SELECT * FROM reporting.monthly_portfolio_ctas)) x),
      'ctas_summary_mismatches',(SELECT count(*) FROM (
        (SELECT * FROM reporting.covenant_summary_ctas EXCEPT
         SELECT as_of_date,cik,company_name,metric,outcome,count(*) FROM reporting.v_quarterly_covenant_results GROUP BY 1,2,3,4,5)
        UNION ALL (SELECT as_of_date,cik,company_name,metric,outcome,count(*) FROM reporting.v_quarterly_covenant_results
          GROUP BY 1,2,3,4,5 EXCEPT SELECT * FROM reporting.covenant_summary_ctas)) x),
      'daily',(SELECT jsonb_agg(to_jsonb(d)) FROM reporting.v_daily_monitoring d),
      'snapshot_mismatches',(SELECT count(*) FROM reporting.monthly_portfolio_ctas c
        LEFT JOIN credit.portfolio_snapshots p ON p.snapshot_month=date_trunc('month',c.month_end)::date
        WHERE p.snapshot_month IS NULL OR ROW(p.loan_count,p.borrower_count,p.principal_usd,p.watchlist_borrower_count)
             IS DISTINCT FROM ROW(c.loan_count,c.borrower_count,c.principal_usd,c.watchlist_borrower_count)),
      'latest_quality',(SELECT passed FROM credit.data_quality_runs ORDER BY run_id DESC LIMIT 1));''',database_url))
    cutoff=date.fromisoformat(data['as_of'])
    rows=read_pilot(path)
    if check_generated_configuration(rows,database_url): raise AssertionError('Generated loan/covenant terms differ from the seed-based policy')
    statement_by_acc={s['accession']:s['statement_id'] for s in data['statements']}
    by_cik={str(l['cik']):l for l in data['loans']}
    by_borrower={l['borrower_id']:str(l['cik']) for l in data['loans']}
    all_results={(r['covenant_id'],r['statement_id']):r for r in data['results'] or []}
    expected={}; expected_ratings={}
    for row in rows:
        loan=by_cik[row['cik']]
        evaluated=max(datetime.strptime(row['filed'],'%Y%m%d').date(),date.fromisoformat(loan['originated_on']))
        if evaluated>cutoff or evaluated>=date.fromisoformat(loan['matures_on']): continue
        statement=statement_by_acc[row['accession']]
        cr=Decimal(row['current_assets'])/Decimal(row['current_liabilities'])
        ic=Decimal(row['operating_income_quarter'])/Decimal(row['interest_expense_quarter'])
        expected_ratings[(loan['borrower_id'],evaluated.isoformat())]=(risk_rating(cr,ic),statement)
        for covenant in data['covenants']:
            if covenant['loan_id']!=loan['loan_id'] or evaluated<date.fromisoformat(covenant['effective_from']): continue
            if covenant['effective_to'] and evaluated>date.fromisoformat(covenant['effective_to']): continue
            observed={'current_ratio':cr,'interest_coverage':ic}[covenant['metric']]
            threshold=Decimal(str(covenant['threshold']))
            passes=observed>=threshold if covenant['comparison']=='>=' else observed<=threshold
            expected[(covenant['covenant_id'],statement)]=(observed,threshold,'pass' if passes else 'breach',evaluated.isoformat())
    actual={key:r for key,r in all_results.items() if r['evaluated_on']<=cutoff.isoformat()}
    if set(actual)!=set(expected): raise AssertionError('Covenant/statement coverage differs from independent expectation')
    for key,(observed,threshold,outcome,evaluated) in expected.items():
        r=actual[key]
        if (r['outcome']!=outcome or r['evaluated_on']!=evaluated or
            abs(Decimal(str(r['observed_value']))-observed)>Decimal('1e-10') or Decimal(str(r['threshold']))!=threshold):
            raise AssertionError(f'Incorrect covenant result: {key}')
    ratings={(r['borrower_id'],r['effective_on']):r for r in data['ratings'] if r['effective_on']<=cutoff.isoformat()}
    if set(ratings)!=set(expected_ratings): raise AssertionError('Rating assessment dates differ')
    for key,(rating,statement) in expected_ratings.items():
        if ratings[key]['rating']!=rating or ratings[key]['source_statement_id']!=statement:
            raise AssertionError(f'Rating policy or evidence mismatch: {key}')
    events=data['events'] or []
    breach_ids={r['result_id'] for r in data['results'] or [] if r['outcome']=='breach'}
    if len(events)!=len(breach_ids) or {w['result_id'] for w in events}!=breach_ids:
        raise AssertionError('Watchlist events do not match breach results exactly')
    by_result={r['result_id']:r for r in data['results'] or []}
    cov_by_id={c['covenant_id']:c for c in data['covenants']}
    loans_by_id={l['loan_id']:l for l in data['loans']}
    for event in events:
        result=by_result[event['result_id']]
        loan=loans_by_id[cov_by_id[result['covenant_id']]['loan_id']]
        if event['borrower_id']!=loan['borrower_id'] or event['opened_on']!=result['evaluated_on']:
            raise AssertionError('Watchlist borrower/date mismatch')
    audited={a['rating_id'] for a in data['audits'] or []}
    if any(r['rating_id'] not in audited for r in data['ratings']): raise AssertionError('Rating missing audit coverage')
    for row in data['daily'] or []:
        cik=str(row['cik']); eligible=[r for r in rows if r['cik']==cik and r['filed']<=cutoff.strftime('%Y%m%d')]
        latest=max(eligible,key=lambda r:(r['period_end'],r['filed']))
        if row['statement_id']!=statement_by_acc[latest['accession']]: raise AssertionError('Daily report uses future/stale filing')
    if any(data[key] for key in ('ctas_month_mismatches','ctas_summary_mismatches','snapshot_mismatches')):
        raise AssertionError('Stored report tables differ from their source views/snapshots')
    if data['latest_quality'] is not True: raise AssertionError('Latest data-quality run is not passed')
    outcomes=Counter(r['outcome'] for r in actual.values())
    return {'status':'passed','as_of_date':cutoff.isoformat(),'counts':base['counts'],
            'independently_reconciled_tests':len(expected),'outcomes':dict(outcomes),
            'independently_reconciled_ratings':len(ratings),
            'watchlist_events':len(events),'watchlist_borrowers':len({w['borrower_id'] for w in events}),
            'audit_operations':dict(Counter(a['operation'] for a in data['audits'] or [])),
            'monthly_ctas_rows':data['report_months'],'covenant_summary_ctas_rows':data['report_summary_rows'],
            'source_sha256':base['source_sha256'],'financial_values_changed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',required=True,type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'data/processed/monitoring_validation.json')
    a=p.parse_args(); result=verify(a.csv)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
