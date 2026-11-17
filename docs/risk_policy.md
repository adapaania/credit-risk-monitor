# Proposed risk rules

These rules define the current `pilot-v1` implementation. Halima and the team should review them before treating them as the final project policy. They are classroom assumptions, not actual lending decisions or default predictions.

## Ratios

- Current ratio = current assets / current liabilities.
- Interest coverage = standalone-quarter operating income / standalone-quarter interest expense.

Missing or nonfinite inputs, or nonpositive denominators, make a ratio unavailable. Negative operating income remains negative. Debt-based covenants are disabled.

## Generated loans

Each borrower gets one USD loan with a three-year term. Principal stays unchanged until maturity; repayments are not modeled.

The baseline is the first available filing. Origination is the following day. Later financials do not change the original loan terms.

Using seed `5132026`, the generator chooses:

- Principal: 0.05%–0.20% of baseline assets, capped at USD 250 million.
- Annual interest rate: 4.50%–8.50%.

The seed is combined with each company's CIK so reordering the CSV does not change the results. Output hashes and assumptions are saved in a local manifest. Generated loan interest does not replace the company's reported interest expense.

## Covenants

Both rules require the observed ratio to be at least the threshold. Equality passes.

| Metric | Fixed threshold |
| --- | --- |
| Current ratio | `max(0.10, 0.80 × baseline current ratio)` |
| Interest coverage | `min(5.00, max(1.00, 0.60 × baseline interest coverage))` |

Thresholds are rounded down to six decimal places. Weak baseline borrowers are retained, so a synthetic loan can breach a covenant at origination. These assumptions do not adjust for industry.

## Ratings

Grade each ratio separately and use the worse grade. A higher number means higher modeled risk.

| Grade | Current ratio lower bound | Interest coverage lower bound |
| --- | ---: | ---: |
| 1 | 2.00 | 20.00 |
| 2 | 1.75 | 12.00 |
| 3 | 1.50 | 8.00 |
| 4 | 1.25 | 5.00 |
| 5 | 1.00 | 3.00 |
| 6 | 0.90 | 2.00 |
| 7 | 0.80 | 1.50 |
| 8 | 0.70 | 1.00 |
| 9 | 0.60 | 0.00 |
| 10 | Below 0.60 | Below 0.00 |

For each column, use the first row whose lower bound is met. For example, a current ratio of 0.85 gives grade 7 and coverage of 25 gives grade 1, so the overall grade is 7. Grade 10 does not mean an observed default. Missing ratios require review and produce no automatic rating.

The system records an assessment for each available statement, even if the grade is unchanged. See [monitoring](monitoring.md) for test results, watchlist events, and rating audits.
