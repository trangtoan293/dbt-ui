# 10 — Diff viewer + merge to Main

## What to build

A diff viewer (before/after) for a User's Workspace changes, plus a
merge-branch-into-Main action gated to maintainers, with the diff shown as a
mandatory review step before the merge. Main is the shared local branch (no
remote). Reuse the existing 3-way merge handling for conflicts.

The diff viewer is pulled into this phase (not IDE-productivity) because it is the
review step of the merge flow, not just a convenience.

## Acceptance criteria

- [ ] Diff viewer shows the worktree branch vs Main
- [ ] A maintainer can merge their branch into Main after reviewing the diff
- [ ] A developer cannot merge into Main (403)
- [ ] Merge conflicts are surfaced using the existing 3-way merge handling

## Blocked by

- 09 — Local git author + remove remote UI
- 08 — RBAC enforcement
