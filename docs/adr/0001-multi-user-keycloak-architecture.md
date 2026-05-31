# 1. Multi-user architecture: Keycloak SSO, per-user worktrees, Dremio identity passthrough

Date: 2026-05-30
Status: Accepted

## Context

dbt-ui ships as a single-shared-account web app with optional HTTP Basic auth,
a global in-memory status dict keyed only by project path, and client-supplied
project paths. We need to take it to production for multiple developers, with
Keycloak as the SSO provider and integration with three query engines (Dremio,
DuckDB, Spark), with security as the primary concern.

Several decisions are coupled and must be made together because each constrains
the others (token lifetime constrains transport; engine trust constrains where
identity must reach; tenancy constrains path authority).

## Decision

1. **Tenancy — per-user worktree.** Each User gets a private, server-provisioned
   git worktree per Project. File edits, dbt runs, output, and git credentials
   are isolated per Workspace.

2. **Project origin — admin catalog of local repos.** Users open Projects only
   from an admin-registered Project Catalog. Repositories live on the server as
   local directories; there is **no git remote** — no clone, push, or pull.
   Version control is local-only (commit/branch/diff/history). This removes the
   entire remote-credential surface (no per-user git tokens, no PAT vault, no
   provider federation). Commits carry the User's Keycloak identity as author.

3. **Path authority — server-derived.** Worktree paths are computed server-side
   from the User's Keycloak `sub`. The client never supplies a trusted path;
   every endpoint resolves under the User's own worktree root and rejects
   anything outside it.

4. **Auth transport — BFF.** A reverse-proxy/BFF (oauth2-proxy or nginx-OIDC)
   performs the OIDC flow, keeps tokens in a server-side session, and forwards
   the *actual access token* to FastAPI. Tokens are not exposed to browser JS.

5. **Engine trust tiers.** Dremio is the only Production Engine; dbt
   authenticates AS the User there. DuckDB and Spark are Dev Engines using a
   shared/process identity — no per-User data isolation expected.

6. **Dremio credential lifetime — token exchange at job start.** Because dbt
   runs as a background task that outlives the short-lived Keycloak access
   token, at job submission the backend exchanges the still-valid Keycloak token
   for a longer-lived Dremio session/PAT and injects that into the dbt
   subprocess.

## Alternatives considered

- **Shared account behind SSO** — simplest, but Keycloak would only gatekeep the
  app, not the data; no per-user audit. Rejected for a production multi-user
  tool.
- **SPA holds token, sends Bearer** — simpler than BFF but exposes tokens to XSS.
  Rejected in favour of BFF.
- **Refresh-token / offline-token storage** for long jobs — powerful but stores
  long-lived sensitive credentials server-side, enlarging attack surface.
  Rejected in favour of short-lived Dremio token exchange.
- **Uniform identity passthrough across all three engines** — not feasible:
  Spark per-user OIDC is non-native, DuckDB is embedded with no identity.
  Rejected in favour of engine trust tiers.

## Consequences

- The global `dbt_command_status` keyed by path is largely de-risked for free,
  because paths now embed the Keycloak `sub` and are server-derived.
- New dependency on a BFF component and on Keycloak ↔ Dremio trust (shared realm
  / token exchange config).
- Free-path project selection UX is removed; a Catalog UI and a worktree
  provisioning flow must be built.
- Git UI loses clone/push/pull; it keeps local commit, branch, diff, history.
  Getting repos onto the server is an out-of-band/admin concern, not a dbt-ui
  feature.
- Long jobs that exceed even the Dremio session lifetime are still out of scope
  (would need refresh/offline tokens — revisit if a scheduler is added).
