# 13 — Dremio production identity passthrough

## What to build

For the Production Engine (Dremio), at dbt **job submission** exchange the User's
still-valid Keycloak token for a longer-lived Dremio session/token, hold it
in-memory scoped to that job, and inject it into the dbt subprocess so dbt
connects AS the User (ADR 0001 §5–6). The exchange happens at job start, not at
connect time, because the background job outlives the short-lived Keycloak access
token. Test Connection against Dremio runs as the requesting User. Restricted to
maintainers.

## Acceptance criteria

- [ ] Token exchange happens at job start, while the Keycloak token is still valid
- [ ] Dremio sees the real per-User identity (row/column policy + audit reflect the person)
- [ ] The Dremio token is never persisted and is scrubbed from logs
- [ ] A job that outlives the Dremio token fails with a clear message (token refresh is out of scope)
- [ ] Test Connection against Dremio runs as the requesting User
- [ ] developer role cannot run against the Production Engine

## Blocked by

- 12 — Connection management
- 08 — RBAC enforcement
- 01 — Keycloak login end-to-end

(HITL: requires Dremio ↔ Keycloak trust configuration — shared realm / token exchange setup.)
