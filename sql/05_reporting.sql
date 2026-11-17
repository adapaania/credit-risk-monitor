-- Week 3 report views and CTAS tables, scoped by an explicit shared report date.
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE TABLE IF NOT EXISTS reporting.report_context (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    as_of_date date NOT NULL,
    refreshed_at timestamptz NOT NULL DEFAULT current_timestamp
);
CREATE TABLE IF NOT EXISTS credit.data_quality_runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    checked_at timestamptz NOT NULL DEFAULT current_timestamp,
    input_sha256 text NOT NULL,
    passed boolean NOT NULL,
    report jsonb NOT NULL
);

CREATE OR REPLACE VIEW reporting.v_daily_monitoring AS
SELECT ctx.as_of_date,b.borrower_id,b.cik,b.company_name,l.loan_id,l.synthetic_key,
       l.principal,l.currency,l.annual_interest_rate,l.originated_on,l.matures_on,
       f.statement_id,f.period_end,f.filed_on,f.current_ratio,f.interest_coverage,
       h.rating,h.effective_on AS rating_effective_on,
       tests.expected_covenants,tests.tested_covenants,tests.passes,tests.breaches,tests.unavailable,
       greatest(tests.expected_covenants-tests.tested_covenants,0) AS untested,
       CASE WHEN tests.expected_covenants=0 THEN 'no_active_covenants'
            WHEN f.statement_id IS NULL THEN 'financials_unavailable'
            WHEN tests.breaches>0 THEN 'breach' WHEN tests.unavailable>0 THEN 'unavailable'
            WHEN tests.tested_covenants<tests.expected_covenants THEN 'untested' ELSE 'pass' END AS monitoring_status,
       events.open_events AS borrower_open_watchlist_events
FROM reporting.report_context ctx
JOIN credit.loans l ON l.originated_on<=ctx.as_of_date AND l.matures_on>ctx.as_of_date
JOIN credit.borrowers b USING(borrower_id)
LEFT JOIN LATERAL (
    SELECT r.statement_id,r.period_end,p.filed_on,r.current_ratio,r.interest_coverage
    FROM credit.financial_ratios r JOIN credit.financial_statement_sources p USING(statement_id)
    WHERE r.borrower_id=b.borrower_id AND r.duration_months=3 AND p.filed_on<=ctx.as_of_date
      AND r.period_end<=ctx.as_of_date
    ORDER BY r.period_end DESC,p.filed_on DESC,r.statement_id DESC LIMIT 1
) f ON true
LEFT JOIN LATERAL (
    SELECT rating,effective_on FROM credit.risk_rating_history
    WHERE borrower_id=b.borrower_id AND effective_on<=ctx.as_of_date
    ORDER BY effective_on DESC LIMIT 1
) h ON true
CROSS JOIN LATERAL (
    SELECT count(*) AS expected_covenants,count(r.result_id) AS tested_covenants,
           count(*) FILTER(WHERE r.outcome='pass') AS passes,
           count(*) FILTER(WHERE r.outcome='breach') AS breaches,
           count(*) FILTER(WHERE r.outcome='unavailable') AS unavailable
    FROM credit.covenants c LEFT JOIN credit.covenant_test_results r
      ON r.covenant_id=c.covenant_id AND r.statement_id=f.statement_id AND r.evaluated_on<=ctx.as_of_date
    WHERE c.loan_id=l.loan_id AND c.effective_from<=ctx.as_of_date
      AND (c.effective_to IS NULL OR ctx.as_of_date<=c.effective_to)
) tests
CROSS JOIN LATERAL (
    SELECT count(*) AS open_events FROM credit.watchlist w WHERE w.borrower_id=b.borrower_id
    AND w.opened_on<=ctx.as_of_date AND (w.closed_on IS NULL OR ctx.as_of_date<w.closed_on)
) events;

CREATE OR REPLACE VIEW reporting.v_weekly_maturities AS
SELECT ctx.as_of_date,date_trunc('week',l.matures_on)::date AS maturity_week,
       count(*) AS loan_count,count(DISTINCT borrower_id) AS borrower_count,sum(principal) AS principal_usd
FROM reporting.report_context ctx JOIN credit.loans l
  ON l.originated_on<=ctx.as_of_date AND l.matures_on>ctx.as_of_date AND l.matures_on<=ctx.as_of_date+90
GROUP BY ctx.as_of_date,date_trunc('week',l.matures_on);

CREATE OR REPLACE VIEW reporting.v_monthly_portfolio AS
WITH months AS (
    SELECT (d+interval '1 month - 1 day')::date AS month_end
    FROM reporting.report_context ctx CROSS JOIN LATERAL generate_series(
        (SELECT date_trunc('month',min(originated_on)) FROM credit.loans),
        date_trunc('month',ctx.as_of_date),interval '1 month') d
    WHERE (d+interval '1 month - 1 day')::date<=ctx.as_of_date
)
SELECT month_end,count(l.loan_id) AS loan_count,count(DISTINCT l.borrower_id) AS borrower_count,
       coalesce(sum(l.principal),0) AS principal_usd,
       count(DISTINCT l.borrower_id) FILTER(WHERE EXISTS(
           SELECT 1 FROM credit.watchlist w WHERE w.borrower_id=l.borrower_id
           AND w.opened_on<=m.month_end AND (w.closed_on IS NULL OR m.month_end<w.closed_on)
       )) AS watchlist_borrower_count,
       sum(l.principal*l.annual_interest_rate)/nullif(sum(l.principal),0) AS weighted_annual_interest_rate
FROM months m LEFT JOIN credit.loans l ON l.originated_on<=m.month_end AND m.month_end<l.matures_on
GROUP BY month_end;

CREATE OR REPLACE VIEW reporting.v_quarterly_covenant_results AS
SELECT ctx.as_of_date,b.cik,b.company_name,l.loan_id,c.covenant_id,c.metric,
       f.period_end,f.fiscal_period,p.filed_on,r.result_id,r.evaluated_on,r.observed_value,
       r.comparison,r.threshold,r.outcome,r.outcome_reason,r.tested_at
FROM reporting.report_context ctx JOIN credit.covenant_test_results r ON r.evaluated_on<=ctx.as_of_date
JOIN credit.covenants c USING(covenant_id) JOIN credit.loans l USING(loan_id)
JOIN credit.borrowers b ON b.borrower_id=l.borrower_id
JOIN credit.financial_statements f USING(statement_id)
JOIN credit.financial_statement_sources p USING(statement_id);

CREATE OR REPLACE VIEW reporting.v_annual_financials AS
WITH available AS (
    -- Count each reporting date once, using the latest filing known at the cutoff.
    SELECT DISTINCT ON (f.borrower_id, f.period_end)
           ctx.as_of_date, f.*
    FROM reporting.report_context ctx
    JOIN credit.financial_statements f ON f.period_end<=ctx.as_of_date AND f.duration_months=3
    JOIN credit.financial_statement_sources p
      ON p.statement_id=f.statement_id AND p.filed_on<=ctx.as_of_date
    ORDER BY f.borrower_id, f.period_end, p.filed_on DESC,
             f.accession_number DESC, f.statement_id DESC
)
SELECT f.as_of_date,b.cik,b.company_name,extract(year FROM f.period_end)::integer AS calendar_reporting_year,
       count(*) AS available_quarters,sum(f.revenue) AS quarter_revenue_sum,
       sum(f.operating_income) AS quarter_operating_income_sum,sum(f.interest_expense) AS quarter_interest_sum,
       sum(f.operating_income)/nullif(sum(f.interest_expense),0) AS aggregate_interest_coverage
FROM available f
JOIN credit.borrowers b USING(borrower_id)
GROUP BY f.as_of_date,b.cik,b.company_name,extract(year FROM f.period_end);

CREATE OR REPLACE VIEW reporting.v_watchlist AS
SELECT ctx.as_of_date,b.cik,b.company_name,w.watchlist_id,w.result_id,w.opened_on,
       CASE WHEN w.closed_on<=ctx.as_of_date THEN w.closed_on END AS closed_on,
       w.reason,CASE WHEN w.closed_on<=ctx.as_of_date THEN w.closure_reason END AS closure_reason,
       CASE WHEN w.closed_on<=ctx.as_of_date THEN w.closed_by END AS closed_by,
       (w.closed_on IS NULL OR ctx.as_of_date<w.closed_on) AS is_open
FROM reporting.report_context ctx JOIN credit.watchlist w ON w.opened_on<=ctx.as_of_date
JOIN credit.borrowers b USING(borrower_id);

CREATE OR REPLACE VIEW reporting.v_rating_history AS
SELECT ctx.as_of_date,b.cik,b.company_name,h.rating_id,h.effective_on,h.rating,
       lag(h.rating) OVER(PARTITION BY h.borrower_id ORDER BY h.effective_on) AS previous_rating,
       h.source_statement_id,h.policy_version,h.reason,h.is_synthetic
FROM reporting.report_context ctx JOIN credit.risk_rating_history h ON h.effective_on<=ctx.as_of_date
JOIN credit.borrowers b USING(borrower_id);

-- CTAS defines real stored report tables. Explicit refresh preserves their identity/grants.
CREATE TABLE IF NOT EXISTS reporting.monthly_portfolio_ctas AS
SELECT * FROM reporting.v_monthly_portfolio WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS monthly_portfolio_ctas_key ON reporting.monthly_portfolio_ctas(month_end);
CREATE TABLE IF NOT EXISTS reporting.covenant_summary_ctas AS
SELECT as_of_date,cik,company_name,metric,outcome,count(*) AS test_count
FROM reporting.v_quarterly_covenant_results GROUP BY as_of_date,cik,company_name,metric,outcome WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS covenant_summary_ctas_key
ON reporting.covenant_summary_ctas(as_of_date,cik,metric,outcome);
CREATE TABLE IF NOT EXISTS reporting.refresh_log (
    refresh_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    as_of_date date NOT NULL,
    refreshed_at timestamptz NOT NULL DEFAULT current_timestamp,
    month_rows bigint NOT NULL,
    covenant_summary_rows bigint NOT NULL
);

CREATE OR REPLACE FUNCTION reporting.refresh_reports(p_date date) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    IF p_date IS NULL OR p_date>CURRENT_DATE THEN RAISE EXCEPTION 'Report date must be explicit and not in the future'; END IF;
    PERFORM pg_advisory_xact_lock(51303);
    INSERT INTO reporting.report_context(singleton,as_of_date) VALUES(true,p_date)
    ON CONFLICT(singleton) DO UPDATE SET as_of_date=EXCLUDED.as_of_date,refreshed_at=clock_timestamp();
    -- DELETE/INSERT is atomic in this transaction and avoids DROP/CASCADE or stale rows.
    DELETE FROM reporting.monthly_portfolio_ctas;
    INSERT INTO reporting.monthly_portfolio_ctas SELECT * FROM reporting.v_monthly_portfolio;
    DELETE FROM reporting.covenant_summary_ctas;
    INSERT INTO reporting.covenant_summary_ctas
    SELECT as_of_date,cik,company_name,metric,outcome,count(*) FROM reporting.v_quarterly_covenant_results
    GROUP BY as_of_date,cik,company_name,metric,outcome;
    INSERT INTO credit.portfolio_snapshots(snapshot_month,loan_count,borrower_count,principal_usd,watchlist_borrower_count)
    SELECT date_trunc('month',month_end)::date,loan_count,borrower_count,principal_usd,watchlist_borrower_count
    FROM reporting.monthly_portfolio_ctas
    ON CONFLICT(snapshot_month) DO UPDATE SET loan_count=EXCLUDED.loan_count,borrower_count=EXCLUDED.borrower_count,
        principal_usd=EXCLUDED.principal_usd,watchlist_borrower_count=EXCLUDED.watchlist_borrower_count,created_at=clock_timestamp();
    INSERT INTO reporting.refresh_log(as_of_date,month_rows,covenant_summary_rows)
    SELECT p_date,(SELECT count(*) FROM reporting.monthly_portfolio_ctas),(SELECT count(*) FROM reporting.covenant_summary_ctas);
END $$;
