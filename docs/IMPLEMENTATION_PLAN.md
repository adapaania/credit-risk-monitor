# Team tasks

Updated November 16, 2026. This tracks the FE513 proposal and the current 10-company pilot.

| Owner | Area | Next step |
| --- | --- | --- |
| Aania Adap | Financial data and checks | Confirm the imported fields and explain data limits |
| Halima Younus | Loans, covenants, ratings, and triggers | Review the proposed rules and monitoring results |
| Khush Mehta | Setup, reports, and access control | Test team setup, add role permissions, and measure query performance |

The branch includes a pilot importer, generated loans and covenants, monitoring functions, audit triggers, report views, and stored summaries. These are implementations to review together; their presence does not mean every owner has approved the choices. Setup instructions are in the [README](../README.md).

## Remaining work

1. Agree on the risk rules and final company sample. The current sample is smaller than the original proposal.
2. Test the full setup on each teammate's computer.
3. Add analyst, manager, executive, and auditor permissions. Test allowed and denied actions.
4. Measure query times before and after adding performance improvements, using the same data and queries.
5. Write the final report and prepare the presentation. Explain design choices, generated data, and changes from the proposal.

Keep debt-based covenants disabled until debt definitions and lease treatment are checked. Larger samples and a raw SEC-to-staging importer are not part of the current pilot build.
