# 02 — Auth mandatory on all routers

## What to build

Remove the optional-auth design. Today auth is a single shared HTTP Basic
credential that is skipped entirely when env vars are unset. Replace it: every
router requires a valid Keycloak JWT (from slice 01), and there is no code path
or toggle that serves the API unauthenticated.

## Acceptance criteria

- [ ] Optional / shared HTTP Basic auth removed
- [ ] All routers (file, git, dbt, venv, env, metadv) require a valid Keycloak JWT
- [ ] No env toggle can disable auth
- [ ] Unauthenticated or invalid-token requests return 401 consistently
- [ ] Public health check (if kept) is the only unauthenticated route

## Blocked by

- 01 — Keycloak login end-to-end
