"""Reconcile loaded financial values, provenance, ratios and generated counts to CSV."""
import argparse
import json
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from pilot_common import QUARTER_METRICS, ROOT, digest, read_pilot, run_sql


def verify(path, database_url=None):
    rows = read_pilot(path)
    output = run_sql('''
SELECT jsonb_build_object(
 'server_version', current_setting('server_version'),
 'monitoring_installed', to_regprocedure('credit.test_loan_covenants(bigint,bigint,date)') IS NOT NULL,
 'statements', (SELECT jsonb_agg(jsonb_build_object(
    'cik',b.cik, 'period_end',f.period_end, 'accession',f.accession_number,
    'duration_months',f.duration_months, 'fiscal_period',f.fiscal_period, 'is_derived',f.is_derived,
    'fiscal_year',f.fiscal_year, 'currency',f.currency, 'source_quarter',f.source_quarter,
    'filed_on',p.filed_on, 'fiscal_start',p.fiscal_start, 'source_duration_days',p.source_duration_days,
    'assets',f.assets::text, 'current_assets',f.current_assets::text,
    'current_liabilities',f.current_liabilities::text, 'revenue',f.revenue::text,
    'operating_income',f.operating_income::text, 'interest_expense',f.interest_expense::text,
    'total_debt',f.total_debt, 'current_ratio',r.current_ratio::text,
    'interest_coverage',r.interest_coverage::text, 'raw_record',p.raw_record,
    'source_sha256',p.source_sha256))
 FROM credit.financial_statements f JOIN credit.borrowers b USING(borrower_id)
 JOIN credit.financial_statement_sources p USING(statement_id)
 JOIN credit.financial_ratios r USING(statement_id)),
 'counts', (SELECT jsonb_build_object(
    'borrowers',(SELECT count(*) FROM credit.borrowers),
    'financial_statements',(SELECT count(*) FROM credit.financial_statements),
    'statement_sources',(SELECT count(*) FROM credit.financial_statement_sources),
    'loans',(SELECT count(*) FROM credit.loans),
    'loan_generation',(SELECT count(*) FROM credit.loan_generation),
    'covenants',(SELECT count(*) FROM credit.covenants),
    'ratings',(SELECT count(*) FROM credit.risk_rating_history),
    'debt_covenants',(SELECT count(*) FROM credit.covenants WHERE metric='debt_to_assets'),
    'covenant_results',(SELECT count(*) FROM credit.covenant_test_results),
    'watchlist_events',(SELECT count(*) FROM credit.watchlist),
    'rating_audits',(SELECT count(*) FROM credit.rating_audit))),
 'invalid_synthetic_links', (SELECT count(*) FROM credit.loan_generation g
    JOIN credit.loans l USING(loan_id)
    JOIN credit.financial_statements f ON f.statement_id=g.baseline_statement_id
    JOIN credit.financial_statement_sources p ON p.statement_id=f.statement_id
    WHERE f.borrower_id<>l.borrower_id OR p.filed_on>=l.originated_on),
 'non_synthetic_loans', (SELECT count(*) FROM credit.loans WHERE NOT is_synthetic));
''', database_url)
    snapshot = json.loads(output)
    actual = {(str(r['cik']), r['period_end']): r for r in snapshot['statements'] or []}
    expected_keys = {(r['cik'], r['period_end']) for r in rows}
    if set(actual) != expected_keys:
        raise AssertionError('Imported statement keys do not match the CSV exactly')
    sha = digest(path)
    for row in rows:
        observed = actual[(row['cik'], row['period_end'])]
        for metric in ('assets', 'current_assets', 'current_liabilities'):
            if Decimal(observed[metric]) != Decimal(row[metric]):
                raise AssertionError(f'{row["cik"]}: {metric} differs')
        for metric in QUARTER_METRICS:
            if Decimal(observed[metric]) != Decimal(row[metric + '_quarter']):
                raise AssertionError(f'{row["cik"]}: normalized {metric} differs')
        cr = Decimal(row['current_assets']) / Decimal(row['current_liabilities'])
        ic = Decimal(row['operating_income_quarter']) / Decimal(row['interest_expense_quarter'])
        if abs(Decimal(observed['current_ratio']) - cr) > Decimal('1e-12'):
            raise AssertionError('Current-ratio reconciliation failed')
        if abs(Decimal(observed['interest_coverage']) - ic) > Decimal('1e-12'):
            raise AssertionError('Interest-coverage reconciliation failed')
        if (observed['raw_record'] != row or observed['source_sha256'] != sha or
                observed['accession'] != row['accession'] or observed['duration_months'] != 3 or
                observed['filed_on'] != datetime.strptime(row['filed'],'%Y%m%d').date().isoformat() or
                observed['fiscal_start'] != row['fiscal_start'] or observed['source_duration_days'] != int(row['duration_days']) or
                observed['fiscal_year'] != int(row['source_fy']) or observed['currency'] != 'USD' or
                observed['source_quarter'] != row['source_quarter'] or
                observed['fiscal_period'] != ('Q4' if row['inferred_period'] == 'FY' else row['inferred_period']) or
                observed['is_derived'] != any(row[m + '_quarter_status'] == 'derived' for m in QUARTER_METRICS) or
                observed['total_debt'] is not None):
            raise AssertionError('Provenance, fiscal period, derivation or deferred debt mismatch')
    companies = len({r['cik'] for r in rows})
    expected_counts = dict(borrowers=companies, financial_statements=len(rows), statement_sources=len(rows),
                           loans=companies, loan_generation=companies, covenants=companies*2,
                           ratings=companies, debt_covenants=0, covenant_results=0, watchlist_events=0,
                           rating_audits=0)
    if snapshot['monitoring_installed']:
        # Later stages add genuine monitoring history. Keep the original data checks useful.
        for key in ('ratings', 'covenant_results', 'watchlist_events', 'rating_audits'):
            if snapshot['counts'][key] < expected_counts[key]:
                raise AssertionError(f'Missing base records: {key}')
            expected_counts[key] = snapshot['counts'][key]
    if snapshot['counts'] != expected_counts:
        raise AssertionError(f'Unexpected counts: {snapshot["counts"]}')
    if snapshot['invalid_synthetic_links'] or snapshot['non_synthetic_loans']:
        raise AssertionError('Synthetic data has invalid borrower or availability links')
    return {'status': 'passed', 'server_version': snapshot['server_version'],
            'source_sha256': sha, 'counts': snapshot['counts'],
            'financial_values_and_ratios_reconciled': len(rows),
            'original_rows_preserved': len(rows), 'future_information_in_baselines': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.csv)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
