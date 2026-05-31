# 16 — ref()/source() autocomplete

## What to build

Configure Monaco completions to suggest `ref()`, `source()`, `config()` and model
names from the Project's `manifest.json`. Typing `ref('` suggests model names;
`source('` suggests sources.

## Acceptance criteria

- [ ] Typing `ref('` suggests model names from manifest.json
- [ ] `source('` suggests source names
- [ ] Completions refresh when the manifest is regenerated
- [ ] Suggestions are scoped to the current Project

## Blocked by

- 07 — Per-user worktree provisioning
