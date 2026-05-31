# 03 — Server-derived path authority

## What to build

Stop trusting client-supplied paths. Compute each User's worktree root
server-side from their Keycloak `sub`. Every endpoint resolves the requested
path under that root and rejects anything outside it. Applies across file, git,
and dbt endpoints. This is the slice that actually makes per-user isolation hold
(see ADR 0001 §3).

## Acceptance criteria

- [ ] Worktree root is derived from the authenticated `sub`, never from the request body
- [ ] A User cannot read, write, or run dbt outside their own root
- [ ] A request carrying another User's path returns 403/404, not their data
- [ ] Existing path-traversal protection still holds
- [ ] File, git, and dbt endpoints all refactored to the authorized-root pattern

## Blocked by

- 02 — Auth mandatory on all routers
