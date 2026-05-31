# 14 — Multi-tab editing

## What to build

Allow opening multiple files in tabs at once, with an unsaved-change indicator per
tab. All file operations stay within the User's authorized worktree root (slice
03). The analysis doc rates this the single highest-impact daily-productivity gap.

## Acceptance criteria

- [ ] Multiple files can be open as tabs simultaneously
- [ ] Switching tabs preserves each file's editor state
- [ ] Each tab shows an unsaved-change indicator
- [ ] All file operations respect server-derived path authority

## Blocked by

- 03 — Server-derived path authority
