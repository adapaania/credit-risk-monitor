-- Reapplicable Week 3 migration. Caller runs this file in a transaction.
ALTER TABLE credit.covenant_test_results ADD COLUMN IF NOT EXISTS evaluated_on date;
ALTER TABLE credit.covenant_test_results ADD COLUMN IF NOT EXISTS outcome_reason text;
ALTER TABLE credit.watchlist ADD COLUMN IF NOT EXISTS opened_on date;
ALTER TABLE credit.watchlist ADD COLUMN IF NOT EXISTS closed_on date;
ALTER TABLE credit.watchlist ADD COLUMN IF NOT EXISTS closure_reason text;
ALTER TABLE credit.watchlist ADD COLUMN IF NOT EXISTS closed_by text;
ALTER TABLE credit.risk_rating_history ADD COLUMN IF NOT EXISTS source_statement_id bigint REFERENCES credit.financial_statements;
ALTER TABLE credit.risk_rating_history ADD COLUMN IF NOT EXISTS policy_version text NOT NULL DEFAULT 'pilot-v1';
ALTER TABLE credit.rating_audit ADD COLUMN IF NOT EXISTS old_record jsonb;
ALTER TABLE credit.rating_audit ADD COLUMN IF NOT EXISTS new_record jsonb;
ALTER TABLE credit.rating_audit DROP CONSTRAINT IF EXISTS rating_audit_operation_check;
ALTER TABLE credit.rating_audit ADD CONSTRAINT rating_audit_operation_check
    CHECK (operation IN ('BASELINE','INSERT','UPDATE','DELETE'));
CREATE UNIQUE INDEX IF NOT EXISTS rating_audit_baseline_key ON credit.rating_audit(rating_id)
    WHERE operation='BASELINE';

-- Attach known Week 2 baselines before installing auditing; no historical INSERT is invented.
UPDATE credit.risk_rating_history r SET source_statement_id=g.baseline_statement_id
FROM credit.loans l JOIN credit.loan_generation g USING(loan_id)
WHERE r.borrower_id=l.borrower_id AND r.effective_on=l.originated_on AND r.source_statement_id IS NULL;
INSERT INTO credit.rating_audit(rating_id,borrower_id,operation,new_rating,new_record)
SELECT r.rating_id,r.borrower_id,'BASELINE',r.rating,to_jsonb(r)
FROM credit.risk_rating_history r
WHERE NOT EXISTS (SELECT 1 FROM credit.rating_audit a WHERE a.rating_id=r.rating_id);

CREATE OR REPLACE FUNCTION credit.validate_monitoring_context(p_loan bigint,p_statement bigint,p_date date)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE l credit.loans; f credit.financial_statements; p credit.financial_statement_sources; canonical bigint;
BEGIN
    IF p_date IS NULL OR p_date > CURRENT_DATE THEN RAISE EXCEPTION 'Evaluation date must be explicit and not in the future'; END IF;
    SELECT * INTO STRICT l FROM credit.loans WHERE loan_id=p_loan FOR SHARE;
    SELECT * INTO STRICT f FROM credit.financial_statements WHERE statement_id=p_statement FOR SHARE;
    IF f.borrower_id<>l.borrower_id THEN RAISE EXCEPTION 'Statement borrower does not match loan borrower'; END IF;
    IF NOT (l.originated_on<=p_date AND p_date<l.matures_on) THEN RAISE EXCEPTION 'Loan is inactive on evaluation date'; END IF;
    IF f.duration_months<>3 OR f.currency<>l.currency THEN RAISE EXCEPTION 'Statement requires matching currency and 3-month duration'; END IF;
    SELECT * INTO p FROM credit.financial_statement_sources WHERE statement_id=p_statement FOR SHARE;
    IF NOT FOUND OR p.filed_on>p_date OR f.period_end>p_date THEN
        RAISE EXCEPTION 'Statement provenance missing or filing not yet available'; END IF;
    SELECT s.statement_id INTO canonical FROM credit.financial_statements s
    JOIN credit.financial_statement_sources sp USING(statement_id)
    WHERE s.borrower_id=f.borrower_id AND s.period_end=f.period_end AND s.duration_months=3
      AND sp.filed_on<=p_date
    ORDER BY sp.filed_on DESC,s.accession_number DESC,s.statement_id DESC LIMIT 1;
    IF canonical<>p_statement THEN RAISE EXCEPTION 'Statement is not the canonical filing available on evaluation date'; END IF;
END $$;

CREATE OR REPLACE FUNCTION credit.guard_covenant_definition() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP IN ('UPDATE','DELETE') AND EXISTS
        (SELECT 1 FROM credit.covenant_test_results WHERE covenant_id=OLD.covenant_id) THEN
        IF TG_OP='DELETE' OR NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Tested covenants are immutable; retain their historical terms'; END IF;
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    IF NEW.metric='debt_to_assets' THEN RAISE EXCEPTION 'Debt covenants remain disabled pending validation'; END IF;
    IF NEW.threshold IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric) THEN
        RAISE EXCEPTION 'Covenant threshold must be finite'; END IF;
    IF EXISTS (SELECT 1 FROM credit.covenants c WHERE c.loan_id=NEW.loan_id AND c.metric=NEW.metric
        AND c.covenant_id<>NEW.covenant_id
        AND NOT (c.effective_from=NEW.effective_from AND c.comparison=NEW.comparison
                 AND c.threshold=NEW.threshold AND c.effective_to IS NOT DISTINCT FROM NEW.effective_to)
        AND daterange(c.effective_from,c.effective_to,'[]') && daterange(NEW.effective_from,NEW.effective_to,'[]')) THEN
        RAISE EXCEPTION 'Overlapping covenant effective windows'; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS covenant_definition_guard ON credit.covenants;
CREATE TRIGGER covenant_definition_guard BEFORE INSERT OR UPDATE OR DELETE ON credit.covenants
FOR EACH ROW EXECUTE FUNCTION credit.guard_covenant_definition();

CREATE OR REPLACE FUNCTION credit.guard_tested_statement() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM credit.covenant_test_results WHERE statement_id=OLD.statement_id) THEN
        IF TG_OP='DELETE' OR NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Tested financial input/provenance is immutable; retain original evidence'; END IF;
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS tested_statement_guard ON credit.financial_statements;
CREATE TRIGGER tested_statement_guard BEFORE UPDATE OR DELETE ON credit.financial_statements
FOR EACH ROW EXECUTE FUNCTION credit.guard_tested_statement();
DROP TRIGGER IF EXISTS tested_source_guard ON credit.financial_statement_sources;
CREATE TRIGGER tested_source_guard BEFORE UPDATE OR DELETE ON credit.financial_statement_sources
FOR EACH ROW EXECUTE FUNCTION credit.guard_tested_statement();

CREATE OR REPLACE FUNCTION credit.guard_tested_loan() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM credit.covenants c JOIN credit.covenant_test_results r USING(covenant_id)
               WHERE c.loan_id=OLD.loan_id) AND (TG_OP='DELETE' OR NEW IS DISTINCT FROM OLD) THEN
        RAISE EXCEPTION 'Tested loan terms are immutable'; END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS tested_loan_guard ON credit.loans;
CREATE TRIGGER tested_loan_guard BEFORE UPDATE OR DELETE ON credit.loans
FOR EACH ROW EXECUTE FUNCTION credit.guard_tested_loan();

CREATE OR REPLACE FUNCTION credit.guard_covenant_result() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c credit.covenants; observed numeric; expected text;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Covenant result history is immutable'; END IF;
    IF TG_OP='UPDATE' THEN
        IF NEW IS DISTINCT FROM OLD THEN RAISE EXCEPTION 'Covenant result history is immutable'; END IF;
        RETURN NEW;
    END IF;
    SELECT * INTO STRICT c FROM credit.covenants WHERE covenant_id=NEW.covenant_id FOR UPDATE;
    PERFORM credit.validate_monitoring_context(c.loan_id,NEW.statement_id,NEW.evaluated_on);
    IF NOT (c.effective_from<=NEW.evaluated_on AND
            (c.effective_to IS NULL OR NEW.evaluated_on<=c.effective_to)) THEN
        RAISE EXCEPTION 'Covenant is inactive on evaluation date'; END IF;
    IF c.metric='debt_to_assets' THEN RAISE EXCEPTION 'Debt covenants remain disabled pending validation'; END IF;
    SELECT CASE c.metric WHEN 'current_ratio' THEN current_ratio WHEN 'interest_coverage' THEN interest_coverage END
    INTO observed FROM credit.financial_ratios WHERE statement_id=NEW.statement_id;
    expected=CASE WHEN observed IS NULL THEN 'unavailable'
                  WHEN (c.comparison='>=' AND observed>=c.threshold) OR
                       (c.comparison='<=' AND observed<=c.threshold) THEN 'pass' ELSE 'breach' END;
    IF NEW.observed_value IS DISTINCT FROM observed OR NEW.threshold IS DISTINCT FROM c.threshold
       OR NEW.comparison IS DISTINCT FROM c.comparison OR NEW.outcome IS DISTINCT FROM expected
       OR nullif(btrim(NEW.outcome_reason),'') IS NULL THEN
        RAISE EXCEPTION 'Result does not match the statement, covenant or required reason'; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS covenant_result_guard ON credit.covenant_test_results;
CREATE TRIGGER covenant_result_guard BEFORE INSERT OR UPDATE OR DELETE ON credit.covenant_test_results
FOR EACH ROW EXECUTE FUNCTION credit.guard_covenant_result();

CREATE OR REPLACE FUNCTION credit.test_loan_covenants(p_loan bigint,p_statement bigint,p_date date)
RETURNS SETOF credit.covenant_test_results LANGUAGE plpgsql AS $$
DECLARE c credit.covenants; observed numeric; result credit.covenant_test_results;
BEGIN
    PERFORM pg_advisory_xact_lock(51303);
    PERFORM credit.validate_monitoring_context(p_loan,p_statement,p_date);
    FOR c IN SELECT * FROM credit.covenants WHERE loan_id=p_loan
        AND effective_from<=p_date AND (effective_to IS NULL OR p_date<=effective_to)
        ORDER BY covenant_id FOR UPDATE LOOP
        SELECT * INTO result FROM credit.covenant_test_results
        WHERE covenant_id=c.covenant_id AND statement_id=p_statement;
        IF FOUND THEN RETURN NEXT result; CONTINUE; END IF;
        IF c.metric='debt_to_assets' THEN RAISE EXCEPTION 'Debt covenants remain disabled pending validation'; END IF;
        SELECT CASE c.metric WHEN 'current_ratio' THEN current_ratio WHEN 'interest_coverage' THEN interest_coverage END
        INTO observed FROM credit.financial_ratios WHERE statement_id=p_statement;
        INSERT INTO credit.covenant_test_results
            (covenant_id,statement_id,observed_value,comparison,threshold,outcome,evaluated_on,outcome_reason)
        VALUES(c.covenant_id,p_statement,observed,c.comparison,c.threshold,
            CASE WHEN observed IS NULL THEN 'unavailable'
                 WHEN (c.comparison='>=' AND observed>=c.threshold) OR
                      (c.comparison='<=' AND observed<=c.threshold) THEN 'pass' ELSE 'breach' END,
            p_date,CASE WHEN observed IS NULL THEN 'Missing/nonfinite input or nonpositive denominator'
                       ELSE 'Compared unrounded ratio with the stored contractual threshold' END)
        RETURNING * INTO result;
        RETURN NEXT result;
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION credit.guard_watchlist_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE b bigint; d date; o text;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Retain watchlist history; close events with a reason'; END IF;
    SELECT l.borrower_id,r.evaluated_on,r.outcome INTO b,d,o FROM credit.covenant_test_results r
    JOIN credit.covenants c USING(covenant_id) JOIN credit.loans l USING(loan_id) WHERE r.result_id=NEW.result_id;
    IF o IS DISTINCT FROM 'breach' OR b IS DISTINCT FROM NEW.borrower_id OR d IS DISTINCT FROM NEW.opened_on THEN
        RAISE EXCEPTION 'Watchlist event must match a breached result and its borrower/date'; END IF;
    IF TG_OP='UPDATE' AND
       (ROW(NEW.borrower_id,NEW.result_id,NEW.reason,NEW.opened_at,NEW.opened_on)
        IS DISTINCT FROM ROW(OLD.borrower_id,OLD.result_id,OLD.reason,OLD.opened_at,OLD.opened_on)
        OR (OLD.closed_on IS NOT NULL AND NEW IS DISTINCT FROM OLD)) THEN
        RAISE EXCEPTION 'Watchlist evidence and completed closures are immutable'; END IF;
    IF NEW.closed_on IS NULL THEN
        IF NEW.closed_at IS NOT NULL OR NEW.closure_reason IS NOT NULL OR NEW.closed_by IS NOT NULL THEN
            RAISE EXCEPTION 'Open events cannot have closure metadata'; END IF;
    ELSIF NEW.closed_on<NEW.opened_on OR NEW.closed_on>CURRENT_DATE OR NEW.closed_at IS NULL
          OR nullif(btrim(NEW.closure_reason),'') IS NULL OR NEW.closed_by IS NULL THEN
        RAISE EXCEPTION 'Closure requires a valid date, actor, timestamp and reason';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS watchlist_event_guard ON credit.watchlist;
CREATE TRIGGER watchlist_event_guard BEFORE INSERT OR UPDATE OR DELETE ON credit.watchlist
FOR EACH ROW EXECUTE FUNCTION credit.guard_watchlist_event();

CREATE OR REPLACE FUNCTION credit.open_breach_watchlist() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.outcome='breach' THEN
        INSERT INTO credit.watchlist(borrower_id,result_id,reason,opened_on)
        SELECT l.borrower_id,NEW.result_id,
               c.metric||' breach: observed '||NEW.observed_value||' '||c.comparison||' threshold '||NEW.threshold,
               NEW.evaluated_on
        FROM credit.covenants c JOIN credit.loans l USING(loan_id) WHERE c.covenant_id=NEW.covenant_id
        ON CONFLICT(result_id) DO NOTHING;
    END IF;
    RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS breach_watchlist ON credit.covenant_test_results;
CREATE TRIGGER breach_watchlist AFTER INSERT ON credit.covenant_test_results
FOR EACH ROW EXECUTE FUNCTION credit.open_breach_watchlist();

CREATE OR REPLACE FUNCTION credit.close_watchlist_event(p_event bigint,p_date date,p_reason text)
RETURNS credit.watchlist LANGUAGE plpgsql AS $$
DECLARE w credit.watchlist;
BEGIN
    SELECT * INTO STRICT w FROM credit.watchlist WHERE watchlist_id=p_event FOR UPDATE;
    IF w.closed_on IS NOT NULL THEN
        IF w.closed_on=p_date AND w.closure_reason=p_reason THEN RETURN w; END IF;
        RAISE EXCEPTION 'Watchlist event is already closed';
    END IF;
    IF p_date IS NULL OR p_date<w.opened_on OR p_date>CURRENT_DATE OR nullif(btrim(p_reason),'') IS NULL THEN
        RAISE EXCEPTION 'Closure requires a valid date and reason'; END IF;
    UPDATE credit.watchlist SET closed_on=p_date,closed_at=clock_timestamp(),closure_reason=p_reason,closed_by=session_user
    WHERE watchlist_id=p_event RETURNING * INTO w;
    RETURN w;
END $$;

CREATE OR REPLACE FUNCTION credit.rating_from_ratios(p_cr numeric,p_ic numeric)
RETURNS integer LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
SELECT CASE WHEN p_cr IS NULL OR p_ic IS NULL OR
    p_cr IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric) OR
    p_ic IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric) THEN NULL
ELSE greatest(
    CASE WHEN p_cr>=2 THEN 1 WHEN p_cr>=1.75 THEN 2 WHEN p_cr>=1.5 THEN 3 WHEN p_cr>=1.25 THEN 4
         WHEN p_cr>=1 THEN 5 WHEN p_cr>=.9 THEN 6 WHEN p_cr>=.8 THEN 7 WHEN p_cr>=.7 THEN 8 WHEN p_cr>=.6 THEN 9 ELSE 10 END,
    CASE WHEN p_ic>=20 THEN 1 WHEN p_ic>=12 THEN 2 WHEN p_ic>=8 THEN 3 WHEN p_ic>=5 THEN 4
         WHEN p_ic>=3 THEN 5 WHEN p_ic>=2 THEN 6 WHEN p_ic>=1.5 THEN 7 WHEN p_ic>=1 THEN 8 WHEN p_ic>=0 THEN 9 ELSE 10 END)
END $$;

CREATE OR REPLACE FUNCTION credit.guard_rating_source() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE b bigint; filed date;
BEGIN
    IF TG_OP='UPDATE' AND ROW(NEW.rating_id,NEW.borrower_id) IS DISTINCT FROM ROW(OLD.rating_id,OLD.borrower_id) THEN
        RAISE EXCEPTION 'Rating identity/borrower cannot be reassigned'; END IF;
    IF nullif(btrim(NEW.reason),'') IS NULL THEN RAISE EXCEPTION 'Rating requires a reason'; END IF;
    IF NEW.source_statement_id IS NOT NULL THEN
        SELECT f.borrower_id,p.filed_on INTO b,filed FROM credit.financial_statements f
        JOIN credit.financial_statement_sources p USING(statement_id) WHERE f.statement_id=NEW.source_statement_id;
        IF b IS DISTINCT FROM NEW.borrower_id OR filed IS NULL OR filed>NEW.effective_on THEN
            RAISE EXCEPTION 'Rating source borrower/availability is invalid'; END IF;
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS rating_source_guard ON credit.risk_rating_history;
CREATE TRIGGER rating_source_guard BEFORE INSERT OR UPDATE ON credit.risk_rating_history
FOR EACH ROW EXECUTE FUNCTION credit.guard_rating_source();

CREATE OR REPLACE FUNCTION credit.audit_rating_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN RETURN NULL; END IF;
    INSERT INTO credit.rating_audit(rating_id,borrower_id,operation,old_rating,new_rating,old_record,new_record,changed_by,changed_at)
    VALUES(CASE WHEN TG_OP='DELETE' THEN OLD.rating_id ELSE NEW.rating_id END,
           CASE WHEN TG_OP='DELETE' THEN OLD.borrower_id ELSE NEW.borrower_id END,TG_OP,
           CASE WHEN TG_OP='INSERT' THEN NULL ELSE OLD.rating END,
           CASE WHEN TG_OP='DELETE' THEN NULL ELSE NEW.rating END,
           CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END,
           CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END,session_user,clock_timestamp());
    RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS rating_change_audit ON credit.risk_rating_history;
CREATE TRIGGER rating_change_audit AFTER INSERT OR UPDATE OR DELETE ON credit.risk_rating_history
FOR EACH ROW EXECUTE FUNCTION credit.audit_rating_change();

CREATE OR REPLACE FUNCTION credit.protect_rating_audit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Rating audit is append-only'; END $$;
DROP TRIGGER IF EXISTS rating_audit_guard ON credit.rating_audit;
CREATE TRIGGER rating_audit_guard BEFORE UPDATE OR DELETE ON credit.rating_audit
FOR EACH ROW EXECUTE FUNCTION credit.protect_rating_audit();

CREATE OR REPLACE FUNCTION credit.record_financial_rating(p_loan bigint,p_statement bigint,p_date date)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE b bigint; cr numeric; ic numeric; grade integer; existing credit.risk_rating_history; new_id bigint;
BEGIN
    PERFORM pg_advisory_xact_lock(51303);
    PERFORM credit.validate_monitoring_context(p_loan,p_statement,p_date);
    SELECT borrower_id,current_ratio,interest_coverage INTO b,cr,ic
    FROM credit.financial_ratios WHERE statement_id=p_statement;
    grade=credit.rating_from_ratios(cr,ic);
    IF grade IS NULL THEN RETURN NULL; END IF; -- unavailable tests remain visible; analyst review required.
    SELECT * INTO existing FROM credit.risk_rating_history WHERE borrower_id=b AND effective_on=p_date;
    IF FOUND THEN
        IF existing.rating<>grade OR existing.source_statement_id IS DISTINCT FROM p_statement THEN
            RAISE EXCEPTION 'Rating already exists on this date with different evidence; do not overwrite history'; END IF;
        RETURN existing.rating_id;
    END IF;
    INSERT INTO credit.risk_rating_history(borrower_id,rating,effective_on,reason,source_statement_id,policy_version)
    VALUES(b,grade,p_date,'pilot-v1; quarterly synthetic assessment; current_ratio='||cr||'; interest_coverage='||ic,
           p_statement,'pilot-v1') RETURNING rating_id INTO new_id;
    RETURN new_id;
END $$;
