"""Validate deterministic generated files and import them in one transaction."""
import argparse
import csv
import json
from pathlib import Path
from generate_loan_data import build_records
from pilot_common import POLICY_VERSION, ROOT, digest, json_copy, read_pilot, run_sql


def load(path, directory, database_url=None):
    directory = Path(directory)
    manifest = json.loads((directory / 'generation_manifest.json').read_text())
    if manifest['input_sha256'] != digest(path) or manifest['policy_version'] != POLICY_VERSION:
        raise ValueError('Manifest input hash/policy does not match the supplied pilot')
    expected = build_records(read_pilot(path), manifest['seed'])
    for filename, records in expected.items():
        with (directory / filename).open(newline='') as stream:
            actual = list(csv.DictReader(stream))
        canonical = [{k: str(v) for k, v in row.items()} for row in records]
        if (actual != canonical or len(actual) != manifest['files'][filename]['rows'] or
                digest(directory / filename) != manifest['files'][filename]['sha256']):
            raise ValueError(f'Generated data differs from its seed/input or hash: {filename}')
    sql = '''BEGIN;
SELECT pg_advisory_xact_lock(51302);
CREATE TEMP TABLE loan_json(payload jsonb) ON COMMIT DROP;
CREATE TEMP TABLE covenant_json(payload jsonb) ON COMMIT DROP;
CREATE TEMP TABLE rating_json(payload jsonb) ON COMMIT DROP;
CREATE TEMP TABLE manifest_json(payload jsonb) ON COMMIT DROP;
'''
    for table, filename in (('loan_json', 'synthetic_loans.csv'),
                            ('covenant_json', 'synthetic_covenants.csv'),
                            ('rating_json', 'synthetic_ratings.csv')):
        sql += json_copy(table, expected[filename])
    sql += json_copy('manifest_json', [manifest])
    sql += '''
CREATE TEMP TABLE incoming_loans ON COMMIT DROP AS
SELECT x.*, b.borrower_id, f.statement_id AS baseline_statement_id, p.filed_on, p.source_sha256
FROM loan_json j CROSS JOIN LATERAL jsonb_to_record(j.payload) AS x(
    synthetic_key text, cik bigint, principal numeric, currency char(3), annual_interest_rate numeric,
    originated_on date, matures_on date, baseline_accession text, baseline_period_end date)
JOIN credit.borrowers b ON b.cik=x.cik
JOIN credit.financial_statements f ON f.borrower_id=b.borrower_id AND f.accession_number=x.baseline_accession
    AND f.period_end=x.baseline_period_end AND f.duration_months=3
JOIN credit.financial_statement_sources p ON p.statement_id=f.statement_id;
CREATE TEMP TABLE incoming_covenants ON COMMIT DROP AS
SELECT x.* FROM covenant_json j CROSS JOIN LATERAL jsonb_to_record(j.payload) AS x(
    synthetic_key text, metric text, comparison text, threshold numeric,
    effective_from date, effective_to date);
CREATE TEMP TABLE incoming_ratings ON COMMIT DROP AS
SELECT x.*, b.borrower_id FROM rating_json j CROSS JOIN LATERAL jsonb_to_record(j.payload) AS x(
    cik bigint, rating integer, effective_on date, reason text)
JOIN credit.borrowers b ON b.cik=x.cik;
DO $$ BEGIN
    IF (SELECT count(*) FROM incoming_loans) <> (SELECT count(*) FROM loan_json)
       OR (SELECT count(*) FROM incoming_ratings) <> (SELECT count(*) FROM rating_json)
    THEN RAISE EXCEPTION 'Missing or ambiguous baseline statements/borrowers; load financials first'; END IF;
    IF EXISTS (SELECT 1 FROM incoming_loans i CROSS JOIN manifest_json m
               WHERE i.filed_on >= i.originated_on
                  OR i.source_sha256 <> m.payload->>'input_sha256') THEN
        RAISE EXCEPTION 'Baseline was unavailable at origination or source hash differs'; END IF;
    IF EXISTS (
        SELECT 1 FROM incoming_loans i JOIN credit.loans l USING(synthetic_key)
        LEFT JOIN credit.loan_generation g ON g.loan_id=l.loan_id CROSS JOIN manifest_json m
        WHERE ROW(l.borrower_id,l.principal,l.currency,l.annual_interest_rate,l.originated_on,l.matures_on,
                  g.baseline_statement_id,g.generation_seed,g.policy_version,g.input_sha256)
        IS DISTINCT FROM ROW(i.borrower_id,i.principal,i.currency,i.annual_interest_rate,
                             i.originated_on,i.matures_on,i.baseline_statement_id,
                             (m.payload->>'seed')::bigint,m.payload->>'policy_version',m.payload->>'input_sha256')
    ) THEN RAISE EXCEPTION 'Existing synthetic loan differs; no records replaced'; END IF;
    IF EXISTS (
        SELECT 1 FROM incoming_covenants i JOIN credit.loans l USING(synthetic_key)
        JOIN credit.covenants c ON c.loan_id=l.loan_id AND c.metric=i.metric AND c.effective_from=i.effective_from
        WHERE ROW(c.comparison,c.threshold,c.effective_to) IS DISTINCT FROM ROW(i.comparison,i.threshold,i.effective_to)
    ) THEN RAISE EXCEPTION 'Existing covenant differs; no records replaced'; END IF;
    IF EXISTS (
        SELECT 1 FROM incoming_ratings i JOIN credit.risk_rating_history r
            ON r.borrower_id=i.borrower_id AND r.effective_on=i.effective_on
        WHERE ROW(r.rating,r.reason,r.is_synthetic) IS DISTINCT FROM ROW(i.rating,i.reason,true)
    ) THEN RAISE EXCEPTION 'Existing rating differs; no records replaced'; END IF;
END $$;
INSERT INTO credit.loans (borrower_id,principal,currency,annual_interest_rate,originated_on,matures_on,synthetic_key)
SELECT borrower_id,principal,currency,annual_interest_rate,originated_on,matures_on,synthetic_key
FROM incoming_loans ORDER BY cik ON CONFLICT(synthetic_key) DO NOTHING;
INSERT INTO credit.loan_generation (loan_id,baseline_statement_id,generation_seed,policy_version,input_sha256,manifest)
SELECT l.loan_id,i.baseline_statement_id,(m.payload->>'seed')::bigint,
       m.payload->>'policy_version',m.payload->>'input_sha256',m.payload
FROM incoming_loans i JOIN credit.loans l USING(synthetic_key) CROSS JOIN manifest_json m
ON CONFLICT(loan_id) DO NOTHING;
INSERT INTO credit.covenants (loan_id,metric,comparison,threshold,effective_from,effective_to)
SELECT l.loan_id,i.metric,i.comparison,i.threshold,i.effective_from,i.effective_to
FROM incoming_covenants i JOIN credit.loans l USING(synthetic_key)
ORDER BY l.loan_id,i.metric ON CONFLICT(loan_id,metric,effective_from) DO NOTHING;
INSERT INTO credit.risk_rating_history (borrower_id,rating,effective_on,reason)
SELECT borrower_id,rating,effective_on,reason FROM incoming_ratings ORDER BY cik
ON CONFLICT(borrower_id,effective_on) DO NOTHING;
COMMIT;
'''
    run_sql(sql, database_url)
    return {filename: len(records) for filename, records in expected.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True, type=Path)
    parser.add_argument('--directory', type=Path, default=ROOT / 'data/processed')
    args = parser.parse_args()
    print(json.dumps(load(args.csv, args.directory), indent=2))
