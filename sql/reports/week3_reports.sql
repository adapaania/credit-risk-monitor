-- Uses the explicit date in reporting.report_context. Refresh with reporting.refresh_reports(date).
BEGIN READ ONLY;
\echo 'Report context'
TABLE reporting.report_context;
\echo 'Daily monitoring: active loans, latest available ratios, test status and rating'
SELECT cik,company_name,principal,period_end,filed_on,current_ratio,interest_coverage,rating,
       monitoring_status,breaches,unavailable,untested,borrower_open_watchlist_events
FROM reporting.v_daily_monitoring ORDER BY cik;
\echo 'Weekly maturities'
SELECT * FROM reporting.v_weekly_maturities ORDER BY maturity_week;
\echo 'Monthly portfolio CTAS'
SELECT * FROM reporting.monthly_portfolio_ctas ORDER BY month_end;
\echo 'Covenant outcome CTAS'
SELECT * FROM reporting.covenant_summary_ctas ORDER BY cik,metric,outcome;
\echo 'Annual calendar-reporting-year flow totals'
SELECT * FROM reporting.v_annual_financials ORDER BY cik,calendar_reporting_year;
\echo 'Rating assessment and change history'
SELECT cik,company_name,effective_on,previous_rating,rating,source_statement_id
FROM reporting.v_rating_history ORDER BY cik,effective_on;
\echo 'Watchlist event and distinct borrower counts'
SELECT count(*) AS events,count(DISTINCT cik) AS borrowers,
       count(*) FILTER(WHERE is_open) AS open_events,
       count(DISTINCT cik) FILTER(WHERE is_open) AS open_borrowers FROM reporting.v_watchlist;
COMMIT;
