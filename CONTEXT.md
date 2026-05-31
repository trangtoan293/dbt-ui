# Context Glossary — dbt-ui

> Ubiquitous language for dbt-ui. Glossary only — no implementation details.
> Update inline as terms are resolved during design sessions.

## Terms

### User
A person authenticated through Keycloak SSO. Each User has a distinct identity
carried through every request. Replaces the former single shared account.

### Project
A dbt repository the organisation works on. Projects are not arbitrary: they
come from the Project Catalog. A Project may be worked on by many Users at once,
each through their own Workspace.

### Project Catalog
The admin-registered set of allowed dbt repositories living **on the server**
(local directories — no remote). Users may only open Projects from the Catalog.
There is no clone, push, or pull: version control is local-only. The Catalog is
the boundary that keeps Project origin auditable.

### Workspace
A User's private, isolated working area for one Project: their own git worktree.
File edits, dbt runs, command output, and git credentials belong to exactly one
Workspace and are never visible to another User.

### Worktree
The on-disk git checkout backing a Workspace. One Worktree per (User, Project),
provisioned by the server (branched off the Project's local main, no remote).
Its path is derived server-side from the User's Keycloak identity — never
supplied by the client. Commits carry the User's Keycloak identity as author.

### Main
The shared local branch of a Project that integrated work lands on. With no git
remote, Main lives only on the server. Users advance Main by merging their
Workspace branch into it from within dbt-ui (with a diff review step). Who may
merge into Main is an authorization concern.

### Role
A User's Keycloak realm role, governing what they may do:
- **admin** — manage the Project Catalog and Users.
- **maintainer** — merge into Main; run dbt against the Production Engine.
- **developer** — work only within their own Workspace; run dbt against Dev
  Engines; cannot merge into Main unaided.

### Query Engine
The data backend dbt executes against. Selected per project via dbt profile +
installed dbt adapter. Engines are not equivalent in trust level:

- **Production Engine** — Dremio. Carries real, access-controlled data. dbt
  authenticates AS the User via Keycloak identity passthrough, so row/column
  policy and audit at the engine reflect the real person. This is the only
  engine where data-level security matters.
- **Dev Engine** — DuckDB and Spark. Used for local development and testing
  only. dbt connects with a shared / process identity; no per-User data
  isolation is expected at these engines.

### Connection
The Project-level, non-secret configuration for reaching a Query Engine (e.g.
Dremio host/port, DuckDB file path, Spark thrift endpoint). Set by an admin,
templated into profiles.yml. Distinct from the per-User **credential**: for the
Production Engine the credential is the User's runtime-exchanged token, never
part of the Connection. "Test connection" against the Production Engine
therefore runs as the requesting User.
