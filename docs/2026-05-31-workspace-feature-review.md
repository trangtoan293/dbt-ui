# Workspace Feature Review — 2026-05-31

Session: personal workspaces implementation (`feat/user-workspace` branch).  
Commit reviewed: `d58254a feat(workspace): personal workspaces - self-service dbt project creation`

---

## 1. Scope of changes

| File | Type | What changed |
|------|------|-------------|
| `backend/utils/workspace.py` | NEW | Core workspace CRUD: create, list, get, delete, update_connections |
| `backend/routes/workspace_routes.py` | NEW | REST routes: list, create, open, delete, update-connections |
| `backend/tests/test_workspace.py` | NEW | 10 unit tests for workspace util (13 passed) |
| `backend/tests/test_workspace_routes.py` | NEW | 10 route integration tests (broken — see §4) |
| `backend/tests/test_engine_gate_workspace.py` | NEW | 3 engine-gate tests (passed) |
| `backend/routes/dbt_routes.py` | MODIFIED | `_engine_gate`: fallback to workspace connections when catalog miss |
| `backend/utils/user_paths.py` | MODIFIED | Added `user_data_path()` |
| `backend/main.py` | MODIFIED | Register `workspace_router` |
| `frontend/src/App.tsx` | MODIFIED | Replace `ProjectCatalogDialog` → `ProjectDialog`; add `projectName` state |
| `frontend/src/components/main/ProjectDialog.tsx` | NEW | Two-tab dialog: My Workspaces + Shared Projects |
| `frontend/src/components/main/CreateWorkspaceModal.tsx` | NEW | Workspace creation form (name + adapter) |
| `frontend/src/components/main/WorkspaceSettingsModal.tsx` | NEW | Connection settings form (dev target) |
| `frontend/src/components/main/MainLayout.tsx` | MODIFIED | Add `projectName` prop, workspace settings button, modal |
| `frontend/src/config/api.ts` | MODIFIED | Add workspace API helpers |
| `frontend/src/components/main/ProjectCatalogDialog.tsx` | DELETED | Replaced by ProjectDialog |

---

## 2. Bugs found & fixed this session

### 2.1 🔴 CRITICAL — Workspaces stored in wrong path (FIXED)

**Root cause:** `workspace.py` originally used `user_data_path()` (→ `git_repos/users/<sub>/workspaces/<id>`).
All other routes resolve via `resolve_under_root(sub, path)` = `git_repos/<sub>/...` (no `/users/` segment).

**Effect:** every file read / dbt run on a workspace → wrong directory → empty/404. Feature entirely non-functional by default.

**Fix applied:** `workspace.py` now uses `user_root(sub)` (from `user_paths.py`), storing at `git_repos/<sub>/workspaces/<id>`. Matches what routes resolve to.

```python
# Before
ws_path = user_data_path() / sub / "workspaces" / workspace_id

# After
ws_path = user_root(sub) / "workspaces" / workspace_id
```

---

### 2.2 🔴 HIGH — Engine gate bypassed for workspaces (FIXED)

**Root cause:** `_engine_gate` receives `project_id = "workspaces/<id>"` (the relative path from `workspace_open`). It called `get_workspace(user.sub, "workspaces/<id>")` which never matches because the store keys on bare `<id>` — so `connections = {}` → gate returned early → **prod engine check skipped**.

**Fix applied:**

```python
ws_id = project_id.split("/", 1)[1] if project_id.startswith("workspaces/") else project_id
ws = workspace_mod.get_workspace(user.sub, ws_id)
```

Regression test added: `test_engine_gate_strips_workspaces_prefix`.

---

### 2.3 🔴 HIGH — DB passwords returned to client on workspace list (FIXED)

**Root cause:** `list_workspaces()` returned `_load(sub)` raw. After `update_connections`, each workspace dict contained `connections` (with DB passwords), `path` (absolute server path), `owner_sub`.

**Fix applied:** Added `_public_view()` — only `id`, `name`, `adapter`, `created_at` sent to client.

---

### 2.4 🔴 HIGH — WorkspaceSettingsModal always overwrites connections with empty (FIXED)

**Root cause:** `MainLayout.tsx` passed hardcoded `connections={{}}` to `WorkspaceSettingsModal`. Existing connections never loaded. Opening Settings → Save → all connections wiped.

**Fix applied:**
- Added `POST /api/workspace/get` route (returns `id`, `name`, `adapter`, `connections` — owner only)
- Added `getWorkspace()` in `api.ts`
- `WorkspaceSettingsModal` now fetches existing connections on mount via `useEffect`
- Removed stale `connections` prop from `MainLayout`

---

### 2.5 🟡 HIGH — Route tests broken by httpx version bump (NOT FIXED)

`test_workspace_routes.py` + `test_catalog_routes.py` all error:

```
TypeError: Client.__init__() got an unexpected keyword argument 'app'
```

`uv.lock` bump pulled `httpx 0.28.1`. `starlette 0.35.1` `TestClient` dropped the `app=` kwarg.  
**13 unit tests pass. 10 route tests can't run — route layer unverified.**

**Fix needed:** Pin `httpx<0.28` in `pyproject.toml` (or fix `TestClient` construction).

---

### 2.6 🟡 HIGH — Broken frontend UI: missing CSS classes (NOT FIXED YET)

**Root cause:** `ProjectDialog`, `CreateWorkspaceModal`, `WorkspaceSettingsModal` use class names that **do not exist** in any CSS file. Classes assumed to be global utilities but no global utility stylesheet exists.

Missing classes vs what exists:

| Class used by components | Exists in CSS? |
|--------------------------|---------------|
| `project-path-dialog` | ❌ (CSS has `.dialog-overlay`) |
| `project-path-dialog-content` | ❌ (CSS has `.dialog-container`) |
| `btn-primary` | ❌ (CSS has `.submit-button`, `.browse-button`) |
| `btn-secondary` | ❌ |
| `catalog-list` | ❌ |
| `catalog-item` | ❌ |
| `catalog-item-info` | ❌ |
| `catalog-item-actions` | ❌ |
| `catalog-item-branch` | ❌ |
| `no-projects` | ❌ |
| `tabs`, `tab-btn`, `tab-btn active` | ✅ (in `ProjectPathDialog.css`) |
| `modal-overlay`, `modal-content` | ✅ |
| `form-group`, `modal-actions` | ✅ |
| `error-message` | ✅ |

**Effect:** All buttons are browser-default unstyled. List renders as bare `<ul>`. Dialog has no visual container. User sees raw HTML lines — unusable UX.

**Fix needed:** Add missing classes to `ProjectPathDialog.css` (see §3 below).

---

### 2.7 🟡 MEDIUM — Empty connections guard missing → StopIteration 500 (FIXED)

`_write_workspace_profiles` calls `next(iter(connections))` — raises `StopIteration` if `connections = {}`, which FastAPI catches as unhandled exception → 500.

**Fix applied:** `update_connections` now validates `if not connections: raise HTTPException(400, "At least one connection required")`.

---

## 3. CSS fix needed (pending)

Add to `frontend/src/components/main/ProjectPathDialog.css`:

```css
/* ProjectDialog shell */
.project-path-dialog {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e1e1e 0%, #2d2d30 100%);
}

.project-path-dialog-content {
  background-color: #252526;
  border-radius: 8px;
  padding: 40px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  min-width: 520px;
  max-width: 640px;
}

.project-path-dialog-content h2 {
  margin: 0 0 20px 0;
  font-size: 24px;
  font-weight: 600;
  color: #ffffff;
}

/* Shared buttons */
.btn-primary {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  background-color: #0e639c;
  color: #ffffff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background-color: #1177bb;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  background-color: #3c3c3c;
  color: #cccccc;
  border: 1px solid #4e4e4e;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #4e4e4e;
}

.btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Catalog / workspace list */
.catalog-list {
  list-style: none;
  margin: 0 0 16px 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
}

.catalog-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background-color: #1e1e1e;
  border: 1px solid #3c3c3c;
  border-radius: 4px;
  transition: border-color 0.2s;
}

.catalog-item:hover {
  border-color: #4c4c4c;
}

.catalog-item-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.catalog-item-info strong {
  font-size: 14px;
  color: #cccccc;
}

.catalog-item-branch {
  font-size: 12px;
  color: #6d6d6d;
}

.catalog-item-actions {
  display: flex;
  gap: 8px;
}

.no-projects {
  font-size: 13px;
  color: #858585;
  text-align: center;
  padding: 24px 0;
}
```

---

## 4. Remaining gaps (not fixed)

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| A | HIGH | Route tests broken (`httpx 0.28` / `TestClient(app=)`) | Pin `httpx<0.28` in `pyproject.toml` |
| B | MEDIUM | Workspace has no venv → `dbt run` + SQL format (M4) fail | Call `_recreate_venv_sync(ws_path, adapter)` in `create_workspace` |
| C | MEDIUM | Adapter stored but no `profiles.yml` seeded on create → first dbt run fails until user sets connection | Seed stub `profiles.yml` from adapter on create |
| D | MEDIUM | `datetime.utcnow()` deprecated (Python 3.12) | Use `datetime.now(timezone.utc)` |
| E | LOW | `workspaces/` prefix not reserved as catalog project ID | Low collision risk; accept or add guard |
| F | LOW | No server-side name length validation on create | Add `if not name or len(name) > 64` |

---

## 5. M4 impact

M4 plan is independent of workspace feature (`feat/user-workspace`). One shared file: `MainLayout.tsx`.

**M4 Task 7** does a significant rewrite of `MainLayout` (adds `useEditorTabs`, `TabBar`, replaces `selectedFile`). When implementing M4, preserve:
- `projectName` prop
- `showWorkspaceSettings` state
- `<WorkspaceSettingsModal>` render block
- `workspaces/` prefix check for settings button

These additions are additive and do not conflict with M4's tab logic.

**Functional gap:** Workspace has no venv → M4's Format SQL button will fail on workspace paths until gap B (above) is fixed.

---

## 6. Test results

```
backend unit tests:    14 passed (test_workspace + test_engine_gate_workspace)
backend route tests:   10 ERRORS — httpx 0.28 compat (pre-existing project-wide, not workspace-specific)
frontend typecheck:    156 errors — React named-import issue (pre-existing project-wide)
frontend build:        ✅ (vite/esbuild succeeds)
```

---

## 7. Recommended next steps

1. **Fix CSS** — add missing classes to `ProjectPathDialog.css` (§3). Unblocks UI entirely.
2. **Fix httpx** — pin `httpx<0.28` so route tests can run.
3. **Seed venv on create** — call venv provision in `create_workspace` (gap B+C).
4. **Verify docker-compose** — ensure `GIT_REPOS_PATH` matches volume mount (same issue as §6 in `2026-05-31-session-notes.md`).
5. **M4** — independent, can start any time after CSS fix lands.
