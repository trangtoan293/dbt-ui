# 09 — Local git author + remove remote UI

## What to build

Set the git commit author from the User's Keycloak identity (name/email claims)
for commits in their worktree. Remove clone/push/pull from the Git UI and
backend — there is no remote (ADR 0001 §2). Keep local commit, branch, diff, and
history.

## Acceptance criteria

- [ ] Commits in a worktree are authored as the Keycloak user (name + email)
- [ ] Clone, push, and pull are removed from both UI and backend
- [ ] Local commit and branch still work within the worktree
- [ ] History and diff remain available

## Blocked by

- 07 — Per-user worktree provisioning
