CREATE OR REPLACE VIEW credit.financial_ratios AS
SELECT statement_id, borrower_id, accession_number, period_end, fiscal_period,
       duration_months,
       CASE WHEN assets > 0 AND assets NOT IN ('NaN'::numeric,'Infinity'::numeric)
                 AND total_debt NOT IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
            THEN total_debt / assets END AS debt_to_assets,
       CASE WHEN current_liabilities > 0 AND current_liabilities NOT IN ('NaN'::numeric,'Infinity'::numeric)
                 AND current_assets NOT IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
            THEN current_assets / current_liabilities END AS current_ratio,
       CASE WHEN interest_expense > 0 AND interest_expense NOT IN ('NaN'::numeric,'Infinity'::numeric)
                 AND operating_income NOT IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
            THEN operating_income / interest_expense END AS interest_coverage
FROM credit.financial_statements;
COMMENT ON VIEW credit.financial_ratios IS
'Ratios preserve missing inputs and require positive denominators. Pilot income values are standalone fiscal quarters (duration_months=3). Debt is unavailable until validated. Select filing and duration explicitly.';
