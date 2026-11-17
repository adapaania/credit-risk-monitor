# Pilot covenant and rating policy

Policy version `pilot-v1`, implemented November 16, 2026, for the 10-company development pilot. These are explicit educational modeling assumptions. The loans, contractual thresholds and internal ratings are synthetic; they are not actual borrowing terms, underwriting decisions, external agency ratings or default probabilities. Real SEC inputs remain unchanged. This policy completes the Week 1 requirements definition and supports Week 2 generation.

## Financial measures

- Current ratio is current assets divided by current liabilities at the statement date.
- Interest coverage is standalone-quarter operating income divided by standalone-quarter interest expense. Operating income is the chosen project numerator, not EBITDA or an adjusted EBIT measure.
- Denominators must be positive. A missing input or nonpositive denominator yields an unavailable ratio. Negative operating income remains a valid negative coverage value.
- Debt-based covenants are disabled. Optional total liabilities and total debt remain null on imported pilot statements. Candidate debt amounts are retained only in source provenance.
- Testing is quarterly. Equality passes a minimum covenant: observed value `>=` threshold. Future testing must retain `unavailable` separately from `pass` and `breach`; it must not replace missing input with zero.

## Baseline and timing

Each borrower has one synthetic loan, originated the day after the earliest available filing in the pilot. Only that filing's information calibrates the loan, covenant thresholds and initial rating. Later observations are not used to tune these decisions. This avoids using future information but does not make the 10-company selected sample representative or establish out-of-sample predictive validity.

Loans have a three-year bullet term, no modeled amortization or early repayment, and USD principal. Outstanding principal is constant from origination through the day before maturity. Covenant effective dates are inclusive in storage; a future testing function must also require an active loan (`originated_on <= test_date < matures_on`) and financial information actually available on the evaluation date. Loan principal and its generated interest rate do not replace the company's reported interest expense.

## Synthetic loan generation

Default seed: `5132026`. Each CIK gets its own Python `random.Random` instance seeded by `pilot-v1:<seed>:<cik>`, so input row order does not alter decisions. A principal fraction is drawn in integer steps from 5 to 20 ten-thousandths: 0.05%–0.20% of baseline assets, capped at USD 250 million and rounded to cents. The annual interest rate is drawn in one-basis-point steps from 4.50% through 8.50%, stored as a decimal fraction (0.045–0.085). Rates are educational assumptions and are not claimed to reproduce historical market pricing.

Stable loan keys are `pilot-v1-<cik>`. A changed seed generates an alternative dataset in a separate output directory; importing it over an existing loan with the same key fails if values differ. Each saved generation manifest records the policy, seed, original input hash, output hashes and record counts. Input financial data must never be committed to Git.

## Covenant threshold calibration

There are two covenants per loan, both minimum comparisons using `>=`:

- Current-ratio threshold: `max(0.10, 0.80 * baseline_current_ratio)`.
- Interest-coverage threshold: `min(5.00, max(1.00, 0.60 * baseline_interest_coverage))`.

Thresholds are rounded down to six decimals and remain fixed for the loan term in this pilot. The liquidity rule gives borrower-specific baseline headroom rather than applying a common liquidity minimum to all industries. The coverage floor prevents accepting a negative contractual minimum for a borrower already reporting losses; the cap keeps extremely high baseline coverage from creating an unnecessarily high synthetic minimum.

The generator deliberately retains weak baseline borrowers such as Intel. It does not assert that every modeled loan would pass an origination underwriting process. A borrower may already fall below a synthetic minimum at origination. No financial amounts are altered to manufacture a pass or breach. Generation itself does not test covenants; the implemented Week 3 monitoring replay populates formal tests and watchlist events separately.

## Complete internal rating scale

Ratings run from 1 (lowest monitored risk) to 10 (highest monitored risk). Grade each ratio separately, then take the worse (larger-numbered) grade. Lower bounds are inclusive and upper bounds exclusive:

- Grade 1: current ratio at least 2.00; coverage at least 20.00.
- Grade 2: current ratio 1.75–<2.00; coverage 12.00–<20.00.
- Grade 3: current ratio 1.50–<1.75; coverage 8.00–<12.00.
- Grade 4: current ratio 1.25–<1.50; coverage 5.00–<8.00.
- Grade 5: current ratio 1.00–<1.25; coverage 3.00–<5.00.
- Grade 6: current ratio 0.90–<1.00; coverage 2.00–<3.00.
- Grade 7: current ratio 0.80–<0.90; coverage 1.50–<2.00.
- Grade 8: current ratio 0.70–<0.80; coverage 1.00–<1.50.
- Grade 9: current ratio 0.60–<0.70; coverage 0.00–<1.00.
- Grade 10: current ratio below 0.60; coverage below 0.00.

These are two independent scales, not a requirement to meet both ranges on the same line. For example, current ratio 0.85 is grade 7 while coverage 25 is grade 1; the combined rating is 7. Grade 10 does not mean an observed default. This conservative simple rule does not adjust for industry and should be discussed as a project limitation.

An unavailable ratio produces no automatic rating; the unavailable covenant test remains visible for analyst review rather than being treated as grade 1. The complete pilot has both ratios. Week 2 loads one initial synthetic rating per borrower on origination day with the baseline accession and ratios in its reason. Week 3 now records an assessment for each later available quarterly statement, with new effective dates, source references and reasons. A repeated grade is still an assessment, not necessarily a change. Corrections and deletions are audited; old/new row snapshots are retained. Initial ratings predate auditing and receive upgrade-time BASELINE snapshots, not invented INSERT history.

## Week 3 interface requirements

The implemented covenant function matches statement and loan borrowers, enforces active/effective dates, selects explicit canonical 3-month evidence, retains ratio/comparator/threshold snapshots, and prevents duplicate covenant/statement results. One event is stored per breached result; borrower counts use distinct borrower IDs. Explicit closure with a required reason and rating audits for INSERT/UPDATE/DELETE are implemented and tested. Later passing tests do not automatically close earlier events. Tested evidence/terms are immutable in this fixed-policy pilot; future amendments require a controlled revision/version workflow. Week 4 will implement who may invoke these interfaces.
