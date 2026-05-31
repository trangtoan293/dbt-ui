# 05 — Production hardening pass

## What to build

A cross-cutting hardening pass for production. May be split into separate issues
if preferred; bundled here as one slice.

- Restrict CORS to the specific origins, methods, and headers actually needed (no
  `*` for methods/headers).
- Set `Secure` + `SameSite` on cookies (credentials must travel over HTTPS).
- Cap file read size before loading into memory.
- Per-user rate limit on dbt commands (e.g. N compile/run per minute).
- Structured audit log: who (`sub`), what action, when — for state-changing
  endpoints.

## Acceptance criteria

- [ ] CORS no longer uses wildcard methods/headers; origins are explicit
- [ ] Cookies set `Secure` and `SameSite`
- [ ] Reading an oversized file is rejected rather than OOMing
- [ ] Exceeding the per-user dbt rate limit returns 429
- [ ] Audit log records `sub` + action + timestamp for state-changing endpoints

## Blocked by

- 02 — Auth mandatory on all routers
