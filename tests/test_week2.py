"""Run with: python3 -m unittest discover -s tests -v.

Set DATABASE_URL to the populated isolated pilot database for integration checks.
"""
import copy
import csv
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generate_loan_data import CR_BANDS, IC_BANDS, build_records, generate, risk_rating
from load_pilot_data import load as load_pilot
from load_synthetic_data import load as load_synthetic
from pilot_common import ROOT, read_pilot, run_sql
from verify_week2 import verify

PILOT = Path(os.environ.get('PILOT_CSV', ROOT.parent / 'pilot_10_financials.csv'))


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class InputAndPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_pilot(PILOT)

    def test_duplicate_company_date_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'duplicate.csv'
            write_csv(path, self.rows + [self.rows[0]])
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                read_pilot(path)

    def test_zero_missing_and_nonfinite_denominators_are_rejected(self):
        for bad_value in ('0', '', 'NaN', '-1'):
            with self.subTest(value=bad_value), tempfile.TemporaryDirectory() as temp:
                rows = copy.deepcopy(self.rows)
                rows[0]['interest_expense_quarter'] = bad_value
                path = Path(temp) / 'invalid.csv'
                write_csv(path, rows)
                with self.assertRaises(ValueError):
                    read_pilot(path)

    def test_negative_operating_income_remains_negative(self):
        losses = [r for r in self.rows if Decimal(r['operating_income_quarter']) < 0]
        self.assertTrue(losses)
        self.assertTrue(all(Decimal(r['operating_income_quarter']) /
                            Decimal(r['interest_expense_quarter']) < 0 for r in losses))

    def test_rating_band_boundaries(self):
        for expected, (cr, ic) in enumerate(zip(CR_BANDS, IC_BANDS), 1):
            with self.subTest(expected=expected):
                self.assertEqual(risk_rating(cr, ic), expected)
        self.assertEqual(risk_rating(Decimal('4'), Decimal('-0.01')), 10)
        self.assertEqual(risk_rating(Decimal('.59'), Decimal('100')), 10)

    def test_generation_is_order_independent_and_seeded(self):
        first = build_records(self.rows)
        self.assertEqual(first, build_records(list(reversed(self.rows))))
        self.assertNotEqual(first['synthetic_loans.csv'], build_records(self.rows, seed=1)['synthetic_loans.csv'])
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            a, b = generate(PILOT, left), generate(PILOT, right)
            self.assertEqual(a, b)
            for name in a['files']:
                self.assertEqual((Path(left)/name).read_bytes(), (Path(right)/name).read_bytes())

    def test_later_financials_cannot_change_baseline_decisions(self):
        revised = copy.deepcopy(self.rows)
        baseline_keys = {(r['cik'], r['accession']) for r in self.rows
                         if r == min([s for s in self.rows if s['cik'] == r['cik']],
                                     key=lambda s: (s['filed'], s['period_end'], s['accession']))}
        for row in revised:
            if (row['cik'], row['accession']) not in baseline_keys:
                row['assets'] = '999999999999999'
                row['operating_income_quarter'] = '-999999999999'
        self.assertEqual(build_records(self.rows), build_records(revised))

    def test_loans_and_covenants_have_valid_dates_and_only_approved_metrics(self):
        generated = build_records(self.rows)
        by_key = {r['synthetic_key']: r for r in generated['synthetic_loans.csv']}
        for loan in by_key.values():
            baseline = next(r for r in self.rows if r['accession'] == loan['baseline_accession'])
            self.assertLess(datetime.strptime(baseline['filed'], '%Y%m%d').date(),
                            date.fromisoformat(loan['originated_on']))
            self.assertLess(loan['originated_on'], loan['matures_on'])
            self.assertGreater(Decimal(loan['principal']), 0)
        for covenant in generated['synthetic_covenants.csv']:
            loan = by_key[covenant['synthetic_key']]
            self.assertIn(covenant['metric'], ('current_ratio', 'interest_coverage'))
            self.assertEqual(covenant['comparison'], '>=')
            self.assertEqual(covenant['effective_from'], loan['originated_on'])
            self.assertEqual(covenant['effective_to'], loan['matures_on'])

    def test_tampered_generated_file_is_rejected_before_database_access(self):
        with tempfile.TemporaryDirectory() as temp:
            generate(PILOT, temp)
            target = Path(temp) / 'synthetic_covenants.csv'
            target.write_text(target.read_text().replace('current_ratio', 'debt_to_assets', 1))
            with self.assertRaisesRegex(ValueError, 'differs'):
                load_synthetic(PILOT, temp, database_url='postgresql:///must_not_be_used')


@unittest.skipUnless(os.environ.get('DATABASE_URL'), 'Set DATABASE_URL for PostgreSQL checks')
class PostgreSQLTests(unittest.TestCase):
    def test_all_imported_values_and_ratios_match_original_csv(self):
        self.assertEqual(verify(PILOT)['status'], 'passed')

    def test_reimport_does_not_duplicate_records(self):
        before = verify(PILOT)
        load_pilot(PILOT)
        load_synthetic(PILOT, ROOT/'data/processed')
        self.assertEqual(verify(PILOT), before)

    def test_conflicting_source_is_rejected_atomically(self):
        before = verify(PILOT)
        with tempfile.TemporaryDirectory() as temp:
            rows = read_pilot(PILOT)
            rows[0]['operating_income_quarter'] = '12345'
            path = Path(temp)/'conflict.csv'
            write_csv(path, rows)
            with self.assertRaisesRegex(RuntimeError, 'conflicts with pilot'):
                load_pilot(path)
        self.assertEqual(verify(PILOT), before)

    def test_filing_date_cutoff_and_quarter_normalization(self):
        sql = '''SELECT jsonb_build_object(
        'available', (SELECT count(*) FROM credit.financial_statement_sources WHERE filed_on<='2025-12-31'),
        'msft_oi',(SELECT operating_income::text FROM credit.financial_statements f
           JOIN credit.borrowers b USING(borrower_id) WHERE b.cik=789019 AND period_end='2023-03-31'),
        'msft_q4',(SELECT fiscal_period FROM credit.financial_statements f
           JOIN credit.borrowers b USING(borrower_id) WHERE b.cik=789019 AND period_end='2023-06-30'))'''
        result = json.loads(run_sql(sql))
        rows = read_pilot(PILOT)
        self.assertEqual(result['available'], sum(r['filed'] <= '20251231' for r in rows))
        self.assertEqual(Decimal(result['msft_oi']), Decimal('22352000000'))
        self.assertEqual(result['msft_q4'], 'Q4')


if __name__ == '__main__':
    unittest.main()
