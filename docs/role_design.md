# Planned database permissions

These permissions are planned; GRANT/REVOKE scripts and role tests are not implemented yet. The current development user owns the database objects.

| Role | Allowed work | Restrictions |
| --- | --- | --- |
| Analyst | Read borrower details and run approved covenant tests | No changes to source records, loan terms, or audit history |
| Manager | Review ratings and close watchlist events with a reason | No changes to audit history or database permissions |
| Executive | Read approved portfolio summaries | No raw source records or write access |
| Auditor | Read source records, assumptions, results, and audits | No data changes or processing commands |

Use a separate owner for database objects and a controlled loader account for imports. Give each role only the table, function, schema, and sequence permissions it needs. Set default permissions for future objects too.

Test with separate role identities. Confirm that approved actions work and restricted actions fail. Running everything as the database owner does not test access control.
