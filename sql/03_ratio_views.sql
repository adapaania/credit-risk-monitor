CREATE VIEW credit.financial_ratios AS
SELECT statement_id, borrower_id, accession_number, period_end, fiscal_period,
       duration_months,
       total_debt / NULLIF(assets, 0) AS debt_to_assets,
       current_assets / NULLIF(current_liabilities, 0) AS current_ratio,
       CASE WHEN interest_expense > 0
            THEN operating_income / interest_expense END AS interest_coverage
FROM credit.financial_statements;
COMMENT ON VIEW credit.financial_ratios IS
'Ratios preserve missing inputs. Interest coverage requires positive expense; select duration and filing explicitly before comparing periods.';
