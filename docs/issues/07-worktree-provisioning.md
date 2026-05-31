# 07 — Per-user worktree provisioning

## What to build

When a User opens a Catalog Project, the server provisions (or reuses) that
User's private worktree, branched off the Project's local Main, at a path derived
from their `sub`. The User can edit and save a file in that worktree end-to-end.
This is the slice that turns "path authority" into a real per-user Workspace.

## Acceptance criteria

- [ ] Opening a Project creates a worktree branched off Main for that User
- [ ] The worktree path is under the User's server-derived root
- [ ] Two Users opening the same Project get isolated worktrees
- [ ] Editing and saving a file in the worktree works end-to-end
- [ ] Reopening the Project reuses the existing worktree

## Blocked by

- 06 — Project Catalog
- 03 — Server-derived path authority
