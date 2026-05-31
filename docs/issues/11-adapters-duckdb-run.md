# 11 — Adapters + DuckDB dev run

## What to build

Install the `dbt-dremio`, `dbt-duckdb`, and `dbt-spark` adapters into the project
venv (none are present today). Prove the engine pipeline end-to-end with DuckDB
first — it is embedded with no identity, so it isolates the dbt-execution
mechanics from the Dremio identity work in slice 13. A User runs dbt against
DuckDB from their worktree and sees results.

## Acceptance criteria

- [ ] dbt-dremio, dbt-duckdb, dbt-spark are installed/available in the venv
- [ ] `dbt run` / `dbt compile` against DuckDB succeeds from a worktree
- [ ] Results are returned to the UI
- [ ] DuckDB is selectable as the engine/target

## Blocked by

- 07 — Per-user worktree provisioning
