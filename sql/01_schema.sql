-- PostgreSQL application schema. Run through scripts/setup.sh.
CREATE SCHEMA IF NOT EXISTS credit;

CREATE TABLE credit.borrowers (
    borrower_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cik bigint NOT NULL UNIQUE CHECK (cik > 0),
    company_name text NOT NULL,
    sic integer CHECK (sic BETWEEN 0 AND 9999),
    state text,
    ticker text
);

CREATE TABLE credit.loans (
    loan_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    borrower_id bigint NOT NULL REFERENCES credit.borrowers,
    principal numeric(20,2) NOT NULL CHECK (principal > 0),
    currency char(3) NOT NULL DEFAULT 'USD',
    annual_interest_rate numeric(10,6) NOT NULL CHECK (annual_interest_rate >= 0),
    originated_on date NOT NULL,
    matures_on date NOT NULL,
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic),
    CHECK (matures_on > originated_on)
);

CREATE TABLE credit.financial_statements (
    statement_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    borrower_id bigint NOT NULL REFERENCES credit.borrowers,
    source_quarter text NOT NULL CHECK (source_quarter ~ '^20[0-9]{2}q[1-4]$'),
    accession_number text NOT NULL,
    period_end date NOT NULL,
    fiscal_year integer NOT NULL,
    fiscal_period text NOT NULL CHECK (fiscal_period IN ('Q1','Q2','Q3','Q4','FY')),
    duration_months integer NOT NULL CHECK (duration_months IN (3,6,9,12)),
    currency char(3) NOT NULL DEFAULT 'USD',
    assets numeric(24,4),
    current_assets numeric(24,4),
    liabilities numeric(24,4),
    current_liabilities numeric(24,4),
    total_debt numeric(24,4),
    revenue numeric(24,4),
    operating_income numeric(24,4),
    interest_expense numeric(24,4),
    is_derived boolean NOT NULL DEFAULT false,
    UNIQUE (borrower_id, accession_number, period_end, duration_months)
);

CREATE TABLE credit.covenants (
    covenant_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loan_id bigint NOT NULL REFERENCES credit.loans,
    metric text NOT NULL CHECK (metric IN ('debt_to_assets','current_ratio','interest_coverage')),
    comparison text NOT NULL CHECK (comparison IN ('<=','>=')),
    threshold numeric(20,6) NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE credit.covenant_test_results (
    result_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    covenant_id bigint NOT NULL REFERENCES credit.covenants,
    statement_id bigint NOT NULL REFERENCES credit.financial_statements,
    observed_value numeric,
    comparison text NOT NULL CHECK (comparison IN ('<=','>=')),
    threshold numeric(20,6) NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('pass','breach','unavailable')),
    tested_at timestamptz NOT NULL DEFAULT current_timestamp,
    CHECK ((outcome = 'unavailable') = (observed_value IS NULL)),
    UNIQUE (covenant_id, statement_id)
);

CREATE TABLE credit.risk_rating_history (
    rating_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    borrower_id bigint NOT NULL REFERENCES credit.borrowers,
    rating integer NOT NULL CHECK (rating BETWEEN 1 AND 10),
    effective_on date NOT NULL,
    reason text NOT NULL,
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic),
    recorded_at timestamptz NOT NULL DEFAULT current_timestamp,
    UNIQUE (borrower_id, effective_on)
);

CREATE TABLE credit.watchlist (
    watchlist_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    borrower_id bigint NOT NULL REFERENCES credit.borrowers,
    result_id bigint NOT NULL UNIQUE REFERENCES credit.covenant_test_results,
    reason text NOT NULL,
    opened_at timestamptz NOT NULL DEFAULT current_timestamp,
    closed_at timestamptz,
    CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

CREATE TABLE credit.rating_audit (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rating_id bigint NOT NULL,
    borrower_id bigint NOT NULL,
    operation text NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    old_rating integer,
    new_rating integer,
    changed_by text NOT NULL DEFAULT session_user,
    changed_at timestamptz NOT NULL DEFAULT current_timestamp
);
-- Audit identifiers deliberately lack foreign keys so deletion cannot erase history.

CREATE TABLE credit.portfolio_snapshots (
    snapshot_month date PRIMARY KEY CHECK (extract(day FROM snapshot_month) = 1),
    loan_count bigint NOT NULL CHECK (loan_count >= 0),
    borrower_count bigint NOT NULL CHECK (borrower_count >= 0),
    principal_usd numeric(24,2) NOT NULL CHECK (principal_usd >= 0),
    watchlist_borrower_count bigint NOT NULL CHECK (watchlist_borrower_count >= 0),
    created_at timestamptz NOT NULL DEFAULT current_timestamp
);
