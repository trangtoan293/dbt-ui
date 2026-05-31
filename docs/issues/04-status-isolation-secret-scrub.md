# 04 — Per-user status isolation + secret scrub

## What to build

Key the in-memory dbt command status by `(sub, path)` instead of `path` alone, so
one User can never poll and read another User's dbt output, SQL, or errors. In
addition, scrub secrets (tokens, connection strings, credentials in stack traces)
from dbt stdout/stderr before storing or returning them.

## Acceptance criteria

- [ ] dbt command status is isolated per `(sub, path)`
- [ ] User B polling a path that User A ran returns nothing belonging to A
- [ ] Secrets are redacted from dbt output before it is stored or returned
- [ ] Secrets are redacted from server logs

## Blocked by

- 03 — Server-derived path authority
