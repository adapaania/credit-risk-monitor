-- Smoke checks on an empty initialized database; fixtures are rolled back.
BEGIN;
INSERT INTO credit.borrowers (cik, company_name) VALUES (999999999, 'Schema test');
INSERT INTO credit.financial_statements
    (borrower_id, source_quarter, accession_number, period_end, fiscal_year,
     fiscal_period, duration_months, assets, total_debt, current_assets,
     current_liabilities, operating_income, interest_expense)
SELECT borrower_id, '2023q1', 'test', '2023-03-31', 2023, 'Q1', 3,
       100, 40, 20, 10, 12, 3 FROM credit.borrowers WHERE cik = 999999999;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM credit.financial_ratios
                   WHERE accession_number = 'test' AND debt_to_assets = 0.4
                     AND current_ratio = 2 AND interest_coverage = 4) THEN
        RAISE EXCEPTION 'Incorrect ratio arithmetic';
    END IF;
    BEGIN
        INSERT INTO credit.loans (borrower_id, principal, annual_interest_rate, originated_on, matures_on)
        SELECT borrower_id, -1, 0.05, '2023-01-01', '2024-01-01'
        FROM credit.borrowers WHERE cik = 999999999;
        RAISE EXCEPTION 'Negative principal accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END $$;
UPDATE credit.financial_statements
SET assets = 0, current_liabilities = 0, interest_expense = 0
WHERE accession_number = 'test';
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM credit.financial_ratios
               WHERE accession_number = 'test'
                 AND (debt_to_assets IS NOT NULL OR current_ratio IS NOT NULL
                      OR interest_coverage IS NOT NULL)) THEN
        RAISE EXCEPTION 'Zero denominator handling failed';
    END IF;
END $$;
ROLLBACK;
