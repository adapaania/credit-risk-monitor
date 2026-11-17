# Week 2 database role design

This is the Week 2 access-control design. Role creation, GRANT/REVOKE scripts, test logins and allowed/denied-operation tests are scheduled for Week 4. No database passwords or login credentials are generated or committed in Week 2.

## Ownership and loading

Use a dedicated non-login owner role for schema objects and controlled migrations. Human accounts should not own shared application tables. A separate controlled loader identity can import approved financials and synthetic datasets. The current local development connection owns this isolated prototype database; it is not an implementation of the final access policy.

The future permission script should revoke unnecessary PUBLIC privileges, separate schema USAGE from table privileges, explicitly grant sequence access only where required, and set default privileges for later objects. Approved query/function interfaces should avoid exposing arbitrary write access.

## Analyst

Read borrower identities, active loans, normalized financials, ratios, covenants, test outcomes and rating history. Initiate testing through the approved covenant function once implemented, with only the function privileges it requires. Analysts should not edit raw source provenance, generated loan terms, audit rows or role memberships. Rating proposals and corrections should follow the manager-approved workflow rather than direct unaudited edits.

## Manager

Read portfolio and borrower detail, approve rating changes, and manage watchlist closure through restricted interfaces that preserve reasons and audit records. No ability to delete audit history or change the schemas/permissions. Exact writable columns or stored interfaces will be selected with the Week 3 workflow.

## Executive

Read approved portfolio summary/report views only. No direct access to raw SEC staging, the original source JSON, audit maintenance, or write operations. Persistent report views are Week 3 work; the Week 2 query drafts define their intended outputs first.

## Auditor

Read financial provenance, loan/covenant configuration, test results, rating history, watchlist events, generation metadata and rating audits. No insert/update/delete, object ownership, role administration or ability to trigger data changes. Reports should expose the difference between real financial inputs and synthetic records.

## Verification to implement in Week 4

Use separate test identities and confirm both allowed and denied actions. In particular, executives must be unable to query source JSON directly; auditors must be unable to update or delete audit rows; analysts must be unable to change covenant thresholds directly; managers must be unable to bypass the rating audit. Test future objects and default privileges as well as the initial tables. A local superuser successfully running a query is not evidence that access controls are implemented.
