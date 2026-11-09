# Core entity relationships

```mermaid
erDiagram
    borrowers ||--o{ loans : borrows
    borrowers ||--o{ financial_statements : files
    loans ||--o{ covenants : requires
    covenants ||--o{ covenant_test_results : produces
    financial_statements ||--o{ covenant_test_results : supports
    borrowers ||--o{ risk_rating_history : receives
    borrowers ||--o{ watchlist : appears_on
    covenant_test_results ||--o| watchlist : triggers
```

`rating_audit` retains identifiers without foreign keys so deleted rating records can still be audited. `portfolio_snapshots` stores monthly aggregates. SEC staging tables retain raw strings and source-quarter provenance, separate from typed application records.

Ratings use a proposed 1–10 scale; the team must agree on its meaning before generation. Ratios and statements retain duration and accession information to avoid silently mixing annual, quarterly, and amended observations. Covenant tests must validate that the statement borrower matches the loan borrower; this cross-table rule belongs in the upcoming testing function.
