# 06 — Project Catalog (admin)

## What to build

Admins register local repositories (server directories) as Project Catalog
entries. Users see and open only Catalog projects; arbitrary path entry and
remote clone are removed. Catalog management is admin-only (role from the
Keycloak token). See ADR 0001 §2 — projects are local, no remote.

## Acceptance criteria

- [ ] An admin can add and remove a Catalog entry pointing at a local repo
- [ ] A non-admin cannot manage the Catalog (403)
- [ ] Users can list and open only Catalog projects
- [ ] The old free-path / clone-URL project selection is removed

## Blocked by

- 01 — Keycloak login end-to-end (roles)
