# 15 — SQL format (sqlfluff/sqlfmt)

## What to build

A Format action (button and/or format-on-save) that runs `sqlfluff format` or
`sqlfmt` via the backend and returns formatted content, respecting a project
`.sqlfluff` config if present. A daily-use feature for dbt developers.

## Acceptance criteria

- [ ] Format action returns formatted SQL via the backend
- [ ] A project `.sqlfluff` config is respected when present
- [ ] Formatting works in the editor
- [ ] The file is not changed on disk unless the User saves

## Blocked by

- 02 — Auth mandatory on all routers
