"""Week 3 integration tests. Fixtures and report refreshes are always rolled back."""
import json
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pilot_common import ROOT,run_sql
from verify_week3 import verify

PILOT=Path(os.environ.get('PILOT_CSV',ROOT.parent/'pilot_10_financials.csv'))

FIXTURE='''
BEGIN;
DO $test$
DECLARE b bigint; other_b bigint; l bigint; s bigint; other_s bigint; c bigint;
        w bigint; rid bigint; v integer; n integer; r record; original_time timestamptz;
BEGIN
INSERT INTO credit.borrowers(cik,company_name) VALUES(999991513,'Week3 test') RETURNING borrower_id INTO b;
INSERT INTO credit.borrowers(cik,company_name) VALUES(999992513,'Other borrower') RETURNING borrower_id INTO other_b;
INSERT INTO credit.loans(borrower_id,principal,annual_interest_rate,originated_on,matures_on)
VALUES(b,1000,.06,'2023-04-02','2024-04-02') RETURNING loan_id INTO l;
INSERT INTO credit.financial_statements(borrower_id,source_quarter,accession_number,period_end,fiscal_year,fiscal_period,
duration_months,assets,current_assets,current_liabilities,revenue,operating_income,interest_expense)
VALUES(b,'2023q2','week3-test','2023-03-31',2023,'Q1',3,100,20,10,30,12,3) RETURNING statement_id INTO s;
INSERT INTO credit.financial_statement_sources(statement_id,filed_on,fiscal_start,source_duration_days,source_file,source_sha256,raw_record)
VALUES(s,'2023-04-01','2023-01-01',90,'fixture',repeat('0',64),'{}');
INSERT INTO credit.financial_statements(borrower_id,source_quarter,accession_number,period_end,fiscal_year,fiscal_period,duration_months)
VALUES(other_b,'2023q2','other-test','2023-03-31',2023,'Q1',3) RETURNING statement_id INTO other_s;
INSERT INTO credit.financial_statement_sources(statement_id,filed_on,fiscal_start,source_duration_days,source_file,source_sha256,raw_record)
VALUES(other_s,'2023-04-01','2023-01-01',90,'fixture',repeat('0',64),'{}');
INSERT INTO credit.covenants(loan_id,metric,comparison,threshold,effective_from,effective_to)
VALUES(l,'current_ratio','>=',2,'2023-04-02','2024-04-02'),
      (l,'interest_coverage','>=',4,'2023-04-02','2024-04-02');
'''


def fixture(body):
    return run_sql(FIXTURE+body+'\nEND $test$;\nROLLBACK;')


def rejects(sql,pattern):
    return f'''BEGIN
    {sql};
    RAISE EXCEPTION 'Expected rejection did not occur';
    EXCEPTION WHEN OTHERS THEN IF SQLERRM NOT LIKE '%{pattern}%' THEN RAISE; END IF;
    END;'''


@unittest.skipUnless(os.environ.get('DATABASE_URL'),'Set DATABASE_URL for PostgreSQL Week 3 tests')
class Week3MonitoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        enabled=run_sql("SELECT to_regprocedure('credit.test_loan_covenants(bigint,bigint,date)') IS NOT NULL;")
        if enabled!='t': raise unittest.SkipTest('Install Week 3 with scripts/run_week3.py first')

    def test_pilot_independent_reconciliation(self):
        self.assertEqual(verify(PILOT)['status'],'passed')

    def test_exact_threshold_passes_and_no_watchlist_event(self):
        fixture('''PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
        SELECT count(*) INTO n FROM credit.covenant_test_results r JOIN credit.covenants c USING(covenant_id)
        WHERE c.loan_id=l AND outcome='pass';
        IF n<>2 OR EXISTS(SELECT 1 FROM credit.watchlist WHERE borrower_id=b) THEN
            RAISE EXCEPTION 'Threshold equality must pass without a watchlist event'; END IF;''')

    def test_maximum_comparison_is_supported(self):
        fixture('''UPDATE credit.covenants SET comparison='<=' WHERE loan_id=l;
        UPDATE credit.financial_statements SET operating_income=15 WHERE statement_id=s;
        PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
        SELECT count(*) INTO n FROM credit.covenant_test_results r JOIN credit.covenants c USING(covenant_id)
        WHERE c.loan_id=l AND outcome='breach';
        IF n<>1 THEN RAISE EXCEPTION 'Maximum comparison failed'; END IF;''')

    def test_missing_zero_negative_and_nonfinite_inputs_are_unavailable(self):
        for change in ('interest_expense=NULL','interest_expense=0','interest_expense=-1',
                       "interest_expense='NaN'", "operating_income='NaN'",'operating_income=NULL',
                       'current_liabilities=0'):
            with self.subTest(change=change):
                fixture(f'''UPDATE credit.financial_statements SET {change} WHERE statement_id=s;
                PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
                SELECT count(*) INTO n FROM credit.covenant_test_results r JOIN credit.covenants c USING(covenant_id)
                WHERE c.loan_id=l AND outcome='unavailable' AND observed_value IS NULL;
                IF n<>1 OR EXISTS(SELECT 1 FROM credit.watchlist WHERE borrower_id=b) THEN
                    RAISE EXCEPTION 'Unavailable input was not preserved'; END IF;
                IF credit.record_financial_rating(l,s,'2023-04-02') IS NOT NULL THEN
                    RAISE EXCEPTION 'Unavailable inputs must not generate a rating'; END IF;''')

    def test_negative_operating_income_is_breach_and_grade_ten(self):
        fixture('''UPDATE credit.financial_statements SET operating_income=-12 WHERE statement_id=s;
        PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
        SELECT count(*) INTO n FROM credit.watchlist WHERE borrower_id=b;
        rid=credit.record_financial_rating(l,s,'2023-04-02');
        IF n<>1 OR (SELECT rating FROM credit.risk_rating_history WHERE rating_id=rid)<>10 THEN
            RAISE EXCEPTION 'Negative operating income should be a numeric breach and grade 10'; END IF;''')

    def test_wrong_borrower_and_inactive_loan_rejected(self):
        fixture(rejects("PERFORM credit.test_loan_covenants(l,other_s,'2023-04-02')",'borrower')+
                rejects("PERFORM credit.test_loan_covenants(l,s,'2023-04-01')",'inactive')+
                rejects("PERFORM credit.test_loan_covenants(l,s,'2024-04-02')",'inactive'))

    def test_future_filing_wrong_duration_and_currency_rejected(self):
        for change,pattern in (("UPDATE credit.financial_statement_sources SET filed_on='2023-04-03' WHERE statement_id=s",'available'),
                               ('UPDATE credit.financial_statements SET duration_months=6 WHERE statement_id=s','duration'),
                               ("UPDATE credit.financial_statements SET currency='EUR' WHERE statement_id=s",'currency')):
            with self.subTest(pattern=pattern):
                fixture(change+';'+rejects("PERFORM credit.test_loan_covenants(l,s,'2023-04-02')",pattern))

    def test_inactive_covenant_is_not_tested(self):
        fixture('''UPDATE credit.covenants SET effective_from='2023-04-03' WHERE loan_id=l AND metric='current_ratio';
        PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
        SELECT count(*) INTO n FROM credit.covenant_test_results r JOIN credit.covenants c USING(covenant_id) WHERE c.loan_id=l;
        IF n<>1 THEN RAISE EXCEPTION 'Inactive covenant was tested'; END IF;''')

    def test_canonical_filing_changes_only_when_later_filing_is_available(self):
        fixture('''INSERT INTO credit.financial_statements(borrower_id,source_quarter,accession_number,period_end,
            fiscal_year,fiscal_period,duration_months,assets,current_assets,current_liabilities,revenue,operating_income,interest_expense)
        VALUES(b,'2023q2','later-test','2023-03-31',2023,'Q1',3,100,20,10,30,12,3) RETURNING statement_id INTO rid;
        INSERT INTO credit.financial_statement_sources(statement_id,filed_on,fiscal_start,source_duration_days,source_file,source_sha256,raw_record)
        VALUES(rid,'2023-04-03','2023-01-01',90,'fixture',repeat('0',64),'{}');
        PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
        '''+rejects("PERFORM credit.test_loan_covenants(l,s,'2023-04-03')",'canonical')+'''
        PERFORM credit.test_loan_covenants(l,rid,'2023-04-03');
        SELECT count(*) INTO n FROM credit.covenant_test_results r JOIN credit.covenants c USING(covenant_id) WHERE c.loan_id=l;
        IF n<>4 THEN RAISE EXCEPTION 'Filing-specific evidence was not retained'; END IF;''')

    def test_debt_and_overlapping_covenants_rejected(self):
        fixture(rejects("INSERT INTO credit.covenants(loan_id,metric,comparison,threshold,effective_from) VALUES(l,'debt_to_assets','<=',.5,'2023-04-02')",'Debt')+
                rejects("INSERT INTO credit.covenants(loan_id,metric,comparison,threshold,effective_from) VALUES(l,'current_ratio','>=',1,'2023-04-03')",'Overlapping'))

    def test_repeat_calls_preserve_results_audits_and_watchlist(self):
        fixture('''UPDATE credit.financial_statements SET operating_income=-12 WHERE statement_id=s;
        PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
        rid=credit.record_financial_rating(l,s,'2023-04-02');
        SELECT min(tested_at) INTO original_time FROM credit.covenant_test_results WHERE statement_id=s;
        PERFORM credit.test_loan_covenants(l,s,'2023-04-03');
        PERFORM credit.record_financial_rating(l,s,'2023-04-02');
        IF (SELECT count(*) FROM credit.covenant_test_results WHERE statement_id=s)<>2
           OR (SELECT count(*) FROM credit.watchlist WHERE borrower_id=b)<>1
           OR (SELECT count(*) FROM credit.rating_audit WHERE rating_id=rid)<>1
           OR (SELECT min(tested_at) FROM credit.covenant_test_results WHERE statement_id=s)<>original_time THEN
            RAISE EXCEPTION 'Repeated calls changed history or duplicated events'; END IF;''')

    def test_tested_evidence_and_results_are_immutable(self):
        fixture("PERFORM credit.test_loan_covenants(l,s,'2023-04-02');"+
            rejects("UPDATE credit.financial_statements SET operating_income=0 WHERE statement_id=s",'immutable')+
            rejects("UPDATE credit.financial_statement_sources SET filed_on='2023-04-02' WHERE statement_id=s",'immutable')+
            rejects("UPDATE credit.covenants SET threshold=0 WHERE loan_id=l",'immutable')+
            rejects("UPDATE credit.loans SET matures_on='2025-04-02' WHERE loan_id=l",'immutable')+
            rejects("UPDATE credit.covenant_test_results SET outcome_reason='altered' WHERE statement_id=s",'immutable'))

    def test_direct_forged_result_is_rejected(self):
        fixture('''SELECT covenant_id INTO c FROM credit.covenants WHERE loan_id=l AND metric='current_ratio';'''+
            rejects("INSERT INTO credit.covenant_test_results(covenant_id,statement_id,observed_value,comparison,threshold,outcome,evaluated_on,outcome_reason) VALUES(c,s,2,'>=',999,'pass','2023-04-02','forged')",'does not match'))

    def test_watchlist_closure_is_reasoned_and_does_not_reopen(self):
        fixture('''UPDATE credit.financial_statements SET operating_income=-12 WHERE statement_id=s;
        PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
        SELECT watchlist_id INTO w FROM credit.watchlist WHERE borrower_id=b;
        '''+rejects("PERFORM credit.close_watchlist_event(w,'2023-04-09','')",'reason')+'''
        PERFORM credit.close_watchlist_event(w,'2023-04-09','Manager reviewed and approved closure');
        PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
        IF (SELECT count(*) FROM credit.watchlist WHERE borrower_id=b)<>1
           OR (SELECT closed_on FROM credit.watchlist WHERE watchlist_id=w) IS NULL THEN
            RAISE EXCEPTION 'Rerun reopened a closed historical event'; END IF;
        PERFORM reporting.refresh_reports('2023-04-08');
        IF NOT EXISTS(SELECT 1 FROM reporting.v_watchlist WHERE watchlist_id=w AND is_open AND closed_on IS NULL) THEN
            RAISE EXCEPTION 'Historical watchlist leaked a future closure'; END IF;
        PERFORM reporting.refresh_reports('2023-04-09');
        IF NOT EXISTS(SELECT 1 FROM reporting.v_watchlist WHERE watchlist_id=w AND NOT is_open) THEN
            RAISE EXCEPTION 'Closure date was not applied'; END IF;''')

    def test_rating_insert_update_delete_audits_survive_delete(self):
        fixture('''rid=credit.record_financial_rating(l,s,'2023-04-02');
        UPDATE credit.risk_rating_history SET rating=9,reason='Manual test correction' WHERE rating_id=rid;
        DELETE FROM credit.risk_rating_history WHERE rating_id=rid;
        IF (SELECT count(*) FROM credit.rating_audit WHERE rating_id=rid)<>3
           OR NOT EXISTS(SELECT 1 FROM credit.rating_audit WHERE rating_id=rid AND operation='UPDATE' AND old_rating=5 AND new_rating=9)
           OR NOT EXISTS(SELECT 1 FROM credit.rating_audit WHERE rating_id=rid AND operation='DELETE' AND old_rating=9 AND new_rating IS NULL)
           OR EXISTS(SELECT 1 FROM credit.rating_audit WHERE rating_id=rid AND (changed_by<>session_user OR changed_at IS NULL)) THEN
            RAISE EXCEPTION 'Rating audit INSERT/UPDATE/DELETE evidence is incomplete'; END IF;
        '''+rejects("DELETE FROM credit.rating_audit WHERE rating_id=rid",'append-only'))

    def test_no_op_rating_update_has_no_duplicate_audit(self):
        fixture('''rid=credit.record_financial_rating(l,s,'2023-04-02');
        UPDATE credit.risk_rating_history SET rating=rating WHERE rating_id=rid;
        IF (SELECT count(*) FROM credit.rating_audit WHERE rating_id=rid)<>1 THEN
            RAISE EXCEPTION 'No-op rating update should not create an audit'; END IF;''')

    def test_infinite_financial_values_are_rejected_by_numeric_schema(self):
        fixture(rejects("UPDATE credit.financial_statements SET operating_income='Infinity' WHERE statement_id=s",'overflow'))
        self.assertEqual(run_sql("SELECT credit.rating_from_ratios('Infinity',4) IS NULL;"),'t')

    def test_report_refresh_removes_stale_ctas_rows_and_respects_cutoff(self):
        run_sql('''BEGIN;
        SELECT reporting.refresh_reports('2023-03-01');
        DO $$ BEGIN
            IF EXISTS(SELECT 1 FROM reporting.v_daily_monitoring WHERE filed_on>'2023-03-01')
               OR EXISTS(SELECT 1 FROM reporting.monthly_portfolio_ctas WHERE month_end>'2023-03-01')
               OR (SELECT sum(test_count) FROM reporting.covenant_summary_ctas)<>
                  (SELECT count(*) FROM reporting.v_quarterly_covenant_results) THEN
                RAISE EXCEPTION 'Report cutoff or CTAS refresh failed'; END IF;
        END $$;
        ROLLBACK;''')

    def test_monthly_exposure_and_watchlist_counts_are_not_multiplied_by_events(self):
        fixture('''UPDATE credit.financial_statements SET current_assets=5,operating_income=-12 WHERE statement_id=s;
        PERFORM credit.test_loan_covenants(l,s,'2023-04-02');
        PERFORM reporting.refresh_reports('2023-04-30');
        IF (SELECT count(*) FROM credit.watchlist WHERE borrower_id=b)<>2 THEN
            RAISE EXCEPTION 'Fixture requires two events for the same borrower'; END IF;
        IF (SELECT principal_usd FROM reporting.monthly_portfolio_ctas WHERE month_end='2023-04-30')<>
           (SELECT sum(principal) FROM credit.loans WHERE originated_on<='2023-04-30' AND matures_on>'2023-04-30')
           OR (SELECT watchlist_borrower_count FROM reporting.monthly_portfolio_ctas WHERE month_end='2023-04-30')<>
              (SELECT count(DISTINCT w.borrower_id) FROM credit.watchlist w JOIN credit.loans l USING(borrower_id)
               WHERE w.opened_on<='2023-04-30' AND (w.closed_on IS NULL OR w.closed_on>'2023-04-30')
                 AND l.originated_on<='2023-04-30' AND l.matures_on>'2023-04-30') THEN
            RAISE EXCEPTION 'Report multiplied exposure or borrower counts by breach events'; END IF;''')

    def test_sql_rating_bands_match_python_boundaries(self):
        from generate_loan_data import CR_BANDS,IC_BANDS,risk_rating
        for cr,ic in zip(CR_BANDS,IC_BANDS):
            result=run_sql(f'SELECT credit.rating_from_ratios({cr},{ic});')
            self.assertEqual(int(result),risk_rating(cr,ic))


if __name__=='__main__': unittest.main()
