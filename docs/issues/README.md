# dbt-ui — Production Issues

Vertical-slice issues for taking dbt-ui to production. Derived from the grilling
session captured in `../adr/0001-multi-user-keycloak-architecture.md` and the
glossary in `../../CONTEXT.md`. Use that glossary's vocabulary when implementing.

Each file is one tracer-bullet slice: a thin path through every layer, demoable
on its own. Execute in dependency order. `HITL` slices need a human (config or
trust decisions); `AFK` slices can be implemented and merged unattended.

## Dependency order

| # | Slice | Type | Blocked by |
|---|---|---|---|
| 01 | Keycloak login end-to-end | HITL | — |
| 02 | Auth mandatory on all routers | AFK | 01 |
| 03 | Server-derived path authority | AFK | 02 |
| 04 | Per-user status isolation + secret scrub | AFK | 03 |
| 05 | Production hardening pass | AFK | 02 |
| 06 | Project Catalog (admin) | AFK | 01 |
| 07 | Per-user worktree provisioning | AFK | 06, 03 |
| 08 | RBAC enforcement (3 roles) | AFK | 07 |
| 09 | Local git author + remove remote UI | AFK | 07 |
| 10 | Diff viewer + merge to Main | AFK | 09, 08 |
| 11 | Adapters + DuckDB dev run | AFK | 07 |
| 12 | Connection management + test + target switch | AFK | 11 |
| 13 | Dremio production identity passthrough | HITL | 12, 08, 01 |
| 14 | Multi-tab editing | AFK | 03 |
| 15 | SQL format (sqlfluff/sqlfmt) | AFK | 02 |
| 16 | ref()/source() autocomplete | AFK | 07 |

Phases: 01–05 security foundation · 06–10 tenancy & projects ·
11–13 engine integration · 14–16 IDE productivity.
