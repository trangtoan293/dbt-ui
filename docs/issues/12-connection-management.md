# 12 — Connection management + test + target switch

## What to build

UI to define Project-level Connection config per engine (Dremio host/port, DuckDB
file path, Spark thrift endpoint), template it into profiles.yml, switch the
active target (dev DuckDB/Spark ↔ prod Dremio), and Test Connection. Per
CONTEXT.md → Connection, the Connection holds **no secrets** — credentials are
per-User and runtime. Start with the Dev Engines (DuckDB/Spark); Dremio identity
is slice 13.

## Acceptance criteria

- [ ] An admin can set Connection config per Project per engine
- [ ] profiles.yml is generated/templated from the Connection config
- [ ] Switching the active target works
- [ ] Test Connection gives a clear pass/fail for DuckDB and Spark
- [ ] No secret is stored in the Connection config

## Blocked by

- 11 — Adapters + DuckDB dev run
