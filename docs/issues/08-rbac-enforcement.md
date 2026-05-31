# 08 — RBAC enforcement (3 roles)

## What to build

Enforce the three Keycloak roles end-to-end (see CONTEXT.md → Role):

- **admin** — manage Catalog and Users.
- **maintainer** — merge into Main; run dbt against the Production Engine.
- **developer** — own Workspace only; Dev Engines only; cannot merge into Main.

Authorization is checked server-side on each gated action; the role is read from
the Keycloak token.

## Acceptance criteria

- [ ] developer is blocked from merging into Main and from Production Engine runs
- [ ] maintainer is allowed to merge into Main and run the Production Engine
- [ ] admin-only Catalog/User management is enforced
- [ ] Role is read from the Keycloak token, not client-supplied
- [ ] Violations return 403

## Blocked by

- 07 — Per-user worktree provisioning
