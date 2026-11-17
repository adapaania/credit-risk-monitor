-- Week 2 query drafts, not persisted report views or covenant test results.
-- psql -X -v ON_ERROR_STOP=1 -v as_of_date=2025-12-31 -f sql/reports/week2_reports.sql
\if :{?as_of_date}
\else
\set as_of_date 2025-12-31
\endif
BEGIN READ ONLY;

\echo 'DAILY: active loans and most recent financials available by the as-of date'
SELECT b.cik, b.company_name, l.synthetic_key, l.principal, l.currency,
       l.annual_interest_rate, l.matures_on, latest.period_end, latest.filed_on,
       latest.current_ratio, latest.interest_coverage, rating.rating AS initial_or_latest_rating
FROM credit.loans l JOIN credit.borrowers b USING (borrower_id)
LEFT JOIN LATERAL (
    SELECT r.period_end, p.filed_on, r.current_ratio, r.interest_coverage
    FROM credit.financial_ratios r
    JOIN credit.financial_statement_sources p USING (statement_id)
    WHERE r.borrower_id = b.borrower_id AND r.duration_months = 3
      AND p.filed_on <= :'as_of_date'::date AND r.period_end <= :'as_of_date'::date
    ORDER BY r.period_end DESC, p.filed_on DESC, r.statement_id DESC LIMIT 1
) latest ON true
LEFT JOIN LATERAL (
    SELECT h.rating FROM credit.risk_rating_history h
    WHERE h.borrower_id=b.borrower_id AND h.effective_on <= :'as_of_date'::date
    ORDER BY h.effective_on DESC LIMIT 1
) rating ON true
WHERE l.originated_on <= :'as_of_date'::date AND l.matures_on > :'as_of_date'::date
ORDER BY b.cik, l.loan_id;

\echo 'WEEKLY: principal maturing in the next 90 days by maturity week'
SELECT date_trunc('week', l.matures_on)::date AS maturity_week,
       count(*) AS loan_count, count(DISTINCT borrower_id) AS borrower_count,
       sum(principal) AS maturing_principal_usd
FROM credit.loans l
WHERE originated_on <= :'as_of_date'::date
  AND matures_on > :'as_of_date'::date AND matures_on <= :'as_of_date'::date + 90
GROUP BY 1 ORDER BY 1;

\echo 'MONTHLY: month-end bullet-loan exposure for the current calendar reporting year'
-- Outstanding principal stays at original principal through the day before maturity.
WITH months AS (
    SELECT (d + interval '1 month - 1 day')::date AS month_end
    FROM generate_series(date_trunc('year', :'as_of_date'::date),
                         date_trunc('month', :'as_of_date'::date), interval '1 month') d
)
SELECT m.month_end, count(l.loan_id) AS active_loans,
       count(DISTINCT l.borrower_id) AS active_borrowers,
       coalesce(sum(l.principal), 0) AS outstanding_principal_usd,
       sum(l.principal * l.annual_interest_rate) / nullif(sum(l.principal), 0)
           AS principal_weighted_annual_rate
FROM months m LEFT JOIN credit.loans l ON l.originated_on <= m.month_end AND l.matures_on > m.month_end
WHERE m.month_end <= :'as_of_date'::date
GROUP BY m.month_end ORDER BY m.month_end;

\echo 'QUARTERLY: statement-level liquidity and coverage available by the as-of date'
SELECT b.cik, b.company_name, f.period_end, f.fiscal_year AS source_fiscal_year,
       f.fiscal_period, p.filed_on, f.is_derived,
       r.current_ratio, r.interest_coverage,
       f.operating_income / nullif(f.revenue,0) AS quarterly_operating_margin
FROM credit.financial_statements f JOIN credit.borrowers b USING(borrower_id)
JOIN credit.financial_statement_sources p USING(statement_id)
JOIN credit.financial_ratios r USING(statement_id)
WHERE f.duration_months=3 AND p.filed_on <= :'as_of_date'::date AND f.period_end <= :'as_of_date'::date
ORDER BY b.cik, f.period_end;

\echo 'ANNUAL: calendar-reporting-year flow totals (may be partial as of the selected date)'
-- Groups actual reporting-end dates, not inconsistent source fiscal labels.
-- Flow amounts may be summed; balance-sheet assets must not be summed across quarters.
SELECT b.cik, b.company_name, extract(year FROM f.period_end)::integer AS calendar_reporting_year,
       count(*) AS available_quarters, sum(f.revenue) AS reported_quarter_revenue_sum,
       sum(f.operating_income) AS reported_quarter_operating_income_sum,
       sum(f.interest_expense) AS reported_quarter_interest_expense_sum,
       sum(f.operating_income) / nullif(sum(f.interest_expense),0) AS aggregate_interest_coverage
FROM credit.financial_statements f JOIN credit.borrowers b USING(borrower_id)
JOIN credit.financial_statement_sources p USING(statement_id)
WHERE f.duration_months=3 AND p.filed_on <= :'as_of_date'::date AND f.period_end <= :'as_of_date'::date
GROUP BY b.cik, b.company_name, extract(year FROM f.period_end)
ORDER BY b.cik, calendar_reporting_year;
COMMIT;
