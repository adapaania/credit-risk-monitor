-- Additive support for the normalized pilot; safe to apply to the starter schema.
CREATE TABLE IF NOT EXISTS credit.financial_statement_sources (
    statement_id bigint PRIMARY KEY REFERENCES credit.financial_statements,
    filed_on date NOT NULL,
    fiscal_start date NOT NULL,
    source_duration_days integer NOT NULL CHECK (source_duration_days BETWEEN 60 AND 380),
    source_file text NOT NULL,
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    raw_record jsonb NOT NULL CHECK (jsonb_typeof(raw_record) = 'object'),
    imported_at timestamptz NOT NULL DEFAULT current_timestamp
);
COMMENT ON TABLE credit.financial_statement_sources IS
'Original CSV row including YTD amounts, tags, source fiscal labels and per-metric quarter derivation. Application statements use normalized 3-month amounts.';

ALTER TABLE credit.loans ADD COLUMN IF NOT EXISTS synthetic_key text UNIQUE;
CREATE TABLE IF NOT EXISTS credit.loan_generation (
    loan_id bigint PRIMARY KEY REFERENCES credit.loans,
    baseline_statement_id bigint NOT NULL REFERENCES credit.financial_statements,
    generation_seed bigint NOT NULL,
    policy_version text NOT NULL,
    input_sha256 text NOT NULL CHECK (input_sha256 ~ '^[a-f0-9]{64}$'),
    manifest jsonb NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS covenants_loan_metric_start_key
    ON credit.covenants (loan_id, metric, effective_from);
