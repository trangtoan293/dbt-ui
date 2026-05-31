# M4 — IDE Productivity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise daily-driver ergonomics on the secured multi-user foundation: edit multiple files in tabs with per-tab unsaved indicators, format SQL on demand via the project's own sqlfluff, and get `ref()`/`source()`/`config()` autocomplete from the Project's `manifest.json`.

**Architecture:** Three independent slices over the existing single-file editor. (1) **Multi-tab** lifts open-file state out of the per-file `useFileContent` hook into a `useEditorTabs` store in `MainLayout`, with a per-path content cache so switching tabs preserves unsaved edits; a `TabBar` renders the open set. (2) **SQL format** installs `sqlfluff` into the per-project venv (so the project's `.sqlfluff` dialect/templater apply) and adds a stateless `/api/format-sql` endpoint that formats a buffer and returns it without touching disk. (3) **Autocomplete** adds `/api/manifest-symbols` (model + source + macro names from `manifest.json`) and a Monaco `CompletionItemProvider` that fires inside `ref('`/`source('`/`config(`.

**Tech Stack:** FastAPI, sqlfluff (in the project venv), pytest + httpx, React, `@monaco-editor/react`, Monaco completion API.

**Covers issues:** `docs/issues/14..16`. Glossary: `CONTEXT.md`. Decisions: `docs/adr/0001-multi-user-keycloak-architecture.md`.

---

## DEPENDENCIES

M4 depends on **M1 + M2 only — NOT M3.** It can be built in parallel with M3 (different files; the one shared file is `routes/venv_routes.py`, see the note in Task 1).

Symbols M4 reuses (all from M1/M2, verified present):
- `auth.get_current_user`, `auth.CurrentUser` — request dependency + user.
- `utils.user_paths.resolve_under_root(sub, sub_path) -> Path` — server-derived path authority (issue 03); every endpoint resolves the worktree under the user root.
- `utils.input_validation.validate_dbt_selector` / path validation in `file_routes`.
- `utils.subprocess_utils.run_command(cmd, cwd, timeout=, env=) -> result(.success/.stdout/.stderr/.error)`.
- `utils.dbt_utils.parse_dbt_manifest(path) -> dict | None`, `get_dbt_env(path, env_vars)`.
- `utils.venv_utils.get_venv_python_path(path)`, `get_venv_dbt_path(path)`; `routes/venv_routes._recreate_venv_sync` (install hook).
- Frontend: `config/api.ts` `apiFetch`/`apiUrl`; `MainLayout.tsx` state hub (`selectedFile`, `modifiedFiles`, `hasUnsavedChanges`); `components/editor/editor/Editor.tsx` + hooks (`useFileContent`, `useFileSave`); `components/editor/editor/EditorContent.tsx` (Monaco via `@monaco-editor/react`).
- `tests/conftest.py` `make_token`, `git_project` fixtures.

**No frontend test infra exists** (`frontend/package.json` has no test script). Frontend tasks are verified manually in the dev server, consistent with M2/M3. Backend tasks are full TDD.

---

## File Structure

- Modify `backend/routes/venv_routes.py` — install `sqlfluff` into the project venv alongside the existing dbt install.
- Create `backend/utils/sql_format.py` — stateless format helper (run sqlfluff over a buffer, return formatted text or a clear error).
- Create `backend/routes/format_routes.py` — `/api/format-sql`.
- Create `backend/utils/manifest_symbols.py` — extract model/source/macro names from a manifest dict.
- Create `backend/routes/symbol_routes.py` — `/api/manifest-symbols`.
- Modify `backend/main.py` — mount `format_router`, `symbol_router`.
- Create `frontend/src/components/main/hooks/useEditorTabs.ts` — open-tab store + per-path content cache.
- Create `frontend/src/components/editor/editor/TabBar.tsx` — the tab strip.
- Modify `frontend/src/components/main/MainLayout.tsx` — use `useEditorTabs` instead of the single `selectedFile`.
- Modify `frontend/src/components/editor/editor/Editor.tsx` + `EditorContent.tsx` — seed/report content via the active tab; register the completion provider; add a Format action.

---

## Task 1: Install sqlfluff into the project venv (issue 15)

**Files:**
- Modify: `backend/routes/venv_routes.py`
- Test: `backend/tests/test_sqlfluff_install.py`

> sqlfluff runs from the **project venv** so the project's `.sqlfluff` (dialect,
> templater) governs formatting. **Merge note for M3:** M3 Task 1 adds a
> `DBT_ADAPTERS` install in the same `_recreate_venv_sync`. Keep both — add a
> separate `FORMAT_TOOLS` list and call after the adapters block. No conflict.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_sqlfluff_install.py`:
```python
import routes.venv_routes as vr


def test_format_tools_lists_sqlfluff():
    assert "sqlfluff" in vr.FORMAT_TOOLS


def test_install_format_tools_issues_pip_command(monkeypatch, tmp_path):
    calls = []

    class _Res:
        success = True
        stdout = "ok"
        stderr = ""
        error = ""

    monkeypatch.setattr(vr, "run_command", lambda cmd, cwd, timeout=None, env=None: calls.append(cmd) or _Res())
    vr.install_format_tools(tmp_path / ".dbt-ui-venv" / "bin" / "python", tmp_path, [])

    flat = [c for call in calls for c in call]
    assert "sqlfluff" in flat
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_sqlfluff_install.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'FORMAT_TOOLS'`.

- [ ] **Step 3: Add the constant + installer**

Near the top of `backend/routes/venv_routes.py` (after imports), add:
```python
# SQL formatting tools installed into every project venv (issue 15). sqlfluff is
# run from the venv so the project's own .sqlfluff dialect/templater apply.
FORMAT_TOOLS = ["sqlfluff"]


def install_format_tools(venv_python, path, output_lines):
    """Install SQL format tooling into the project venv (best-effort per tool)."""
    for tool in FORMAT_TOOLS:
        result = run_command(
            ["uv", "pip", "install", tool, "--python", str(venv_python)],
            path, timeout=300,
        )
        if result.success:
            output_lines.append(f"Successfully installed {tool}")
        else:
            output_lines.append(f"Warning: failed to install {tool}: {result.stderr}")
```

- [ ] **Step 4: Call it during venv creation**

In `_recreate_venv_sync`, after the dbt-core install success block (and after the
M3 adapters block if present), add:
```python
    output_lines.append("\nInstalling SQL format tools...")
    install_format_tools(venv_python, path, output_lines)
```

- [ ] **Step 5: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_sqlfluff_install.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/venv_routes.py backend/tests/test_sqlfluff_install.py
git commit -m "feat(format): install sqlfluff into the project venv"
```

---

## Task 2: `/api/format-sql` endpoint (issue 15)

**Files:**
- Create: `backend/utils/sql_format.py`
- Create: `backend/routes/format_routes.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_format_sql.py`

> Stateless: takes the current buffer + the file sub-path, runs `sqlfluff format -`
> (stdin) with `cwd` = the worktree so a project `.sqlfluff` is picked up, and
> returns the formatted text. **Disk is never written** (acceptance: the file changes
> only when the user saves). On failure, return `ok: false` + a scrubbed message so
> the editor buffer is left untouched.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_format_sql.py`:
```python
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app


def _open_dir(sub, tmp_path):
    # Path authority resolves <user_root>/<sub_path>; create it so it exists.
    from utils.user_paths import resolve_under_root
    p = resolve_under_root(sub, "p1")
    p.mkdir(parents=True, exist_ok=True)
    return p


def test_format_returns_formatted_buffer(make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    _open_dir("user-a", tmp_path)
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])

    class _R:
        success = True
        stdout = "select 1\n"
        stderr = ""
        error = ""

    with patch("routes.format_routes.run_command", return_value=_R()):
        r = client.post("/api/format-sql",
                        json={"path": "p1", "file_path": "models/x.sql", "content": "SELECT     1"},
                        headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["formatted"] == "select 1\n"


def test_format_failure_returns_ok_false(make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    _open_dir("user-a", tmp_path)
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])

    class _R:
        success = False
        stdout = ""
        stderr = "Parsing error at line 1"
        error = "Parsing error at line 1"

    with patch("routes.format_routes.run_command", return_value=_R()):
        r = client.post("/api/format-sql",
                        json={"path": "p1", "file_path": "models/x.sql", "content": "SELECT ("},
                        headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "formatted" not in r.json() or r.json().get("formatted") is None
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_format_sql.py -v`
Expected: FAIL — `/api/format-sql` 404.

- [ ] **Step 3: Implement the format helper**

Create `backend/utils/sql_format.py`:
```python
"""Stateless SQL formatting via the project venv's sqlfluff (issue 15).

Reads SQL from stdin, returns formatted text. cwd = the worktree so a project
.sqlfluff (dialect, templater) is respected. Never writes to disk.
"""
from pathlib import Path

from utils.venv_utils import get_venv_dbt_path  # locates the venv bin dir
from utils.dbt_utils import get_dbt_env
from utils.subprocess_utils import run_command


def _sqlfluff_bin(worktree: Path) -> str:
    # sqlfluff sits next to dbt in the venv bin dir.
    dbt = Path(get_venv_dbt_path(worktree))
    candidate = dbt.parent / "sqlfluff"
    return str(candidate) if candidate.exists() else "sqlfluff"


def format_sql(worktree: Path, content: str) -> dict:
    """Format SQL text. Returns {ok, formatted?} or {ok: False, error}."""
    bin_path = _sqlfluff_bin(worktree)
    env = get_dbt_env(worktree)
    result = run_command(
        [bin_path, "format", "-"],   # '-' = read from stdin, write to stdout
        worktree, timeout=60, env=env, stdin=content,
    )
    if result.success:
        return {"ok": True, "formatted": result.stdout}
    return {"ok": False, "error": (result.error or result.stderr or "format failed")}
```

> **Reconcile:** confirm `run_command` accepts a `stdin=` kwarg. If it does not,
> extend it (it wraps `subprocess.run`; pass `input=stdin, text=True`). This is the
> only signature change M4 needs in shared code.

- [ ] **Step 4: Implement the endpoint**

Create `backend/routes/format_routes.py`:
```python
"""SQL formatting endpoint (issue 15). Stateless — returns formatted text, never
writes the file."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user, CurrentUser
from utils.user_paths import resolve_under_root
from utils.sql_format import format_sql
from utils.subprocess_utils import run_command  # re-exported so tests patch here
from utils.secret_scrub import scrub

router = APIRouter()


class FormatRequest(BaseModel):
    path: str          # project sub-path (worktree), resolved under the user root
    file_path: str     # for context/logging only
    content: str


@router.post("/api/format-sql")
async def format_sql_endpoint(req: FormatRequest, user: CurrentUser = Depends(get_current_user)):
    worktree = resolve_under_root(user.sub, req.path)
    result = format_sql(worktree, req.content)
    if not result.get("ok"):
        return {"ok": False, "error": scrub(result.get("error", "format failed"))}
    return {"ok": True, "formatted": result["formatted"]}
```

> `format_sql` imports `run_command` from `utils.subprocess_utils`; the test patches
> `routes.format_routes.run_command`. To make that patch effective, have
> `utils.sql_format.format_sql` call the module-level name — simplest is to import
> `run_command` inside `format_routes` and pass it in, OR patch
> `utils.sql_format.run_command` in the test. **Pick one and make the test target match
> the call site.** (Recommended: patch `utils.sql_format.run_command` and drop the
> re-export here.)

- [ ] **Step 5: Mount the router**

In `backend/main.py`, with the other routers:
```python
from routes.format_routes import router as format_router
app.include_router(format_router)
```

- [ ] **Step 6: Align the test patch target, run, verify pass**

Update the two tests' `patch("routes.format_routes.run_command", ...)` to
`patch("utils.sql_format.run_command", ...)` per the Step 4 note.

Run: `cd backend && python -m pytest tests/test_format_sql.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/utils/sql_format.py backend/routes/format_routes.py backend/main.py backend/tests/test_format_sql.py
git commit -m "feat(format): /api/format-sql formats a buffer via project sqlfluff"
```

---

## Task 3: Format action in the editor (issue 15 — frontend, manual)

**Files:**
- Modify: `frontend/src/components/editor/editor/EditorHeader.tsx` (add a Format button)
- Modify: `frontend/src/components/editor/editor/Editor.tsx` (call the endpoint, replace buffer)

> Verify manually — no FE test infra. Use `apiFetch(apiUrl('/api/...'), ...)`.

- [ ] **Step 1: Add a Format handler in `Editor.tsx`**

Add, using the existing `content`/`setContent`/`selectedFile`/`projectPath`:
```tsx
const [formatting, setFormatting] = useState(false)

const handleFormat = async () => {
  if (!selectedFile || formatting) return
  setFormatting(true)
  try {
    const res = await apiFetch(apiUrl('/api/format-sql'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: projectPath, file_path: selectedFile, content }),
    })
    const data = await res.json()
    if (data.ok) {
      setContent(data.formatted)        // buffer only — file unchanged until save
    } else {
      console.error('Format failed:', data.error)
    }
  } finally {
    setFormatting(false)
  }
}
```
Pass `onFormat={handleFormat}` and `formatting` down to `EditorHeader`.

- [ ] **Step 2: Add the button to `EditorHeader.tsx`**

Next to the Save button, render a Format button (only for `.sql` files):
```tsx
{selectedFile?.endsWith('.sql') && (
  <button className="view-toggle-btn" onClick={onFormat} disabled={formatting}
          title="Format SQL (sqlfluff)">
    {formatting ? '…' : 'Format'}
  </button>
)}
```
Add `onFormat: () => void` and `formatting: boolean` to `EditorHeaderProps`.

- [ ] **Step 3: Manual verification**

Run: `cd frontend && npm run dev`
- Open a `.sql` model, click **Format** → buffer reformats, the unsaved indicator
  appears, disk is unchanged until Save.
- A file with a syntax error → format fails, the buffer is left intact (check console).
- Add a project `.sqlfluff` (e.g. `dialect = duckdb`) → formatting honors it.

- [ ] **Step 4: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/editor/editor/EditorHeader.tsx frontend/src/components/editor/editor/Editor.tsx
git commit -m "feat(format): Format SQL button in the editor"
```

---

## Task 4: `/api/manifest-symbols` endpoint (issue 16)

**Files:**
- Create: `backend/utils/manifest_symbols.py`
- Create: `backend/routes/symbol_routes.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_manifest_symbols.py`

> Serves the names Monaco completes: model names (for `ref(`), source pairs (for
> `source(`), and macro names. Pure extraction over the manifest dict, so it is
> unit-testable without a real dbt run.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_manifest_symbols.py`:
```python
from utils.manifest_symbols import extract_symbols

MANIFEST = {
    "nodes": {
        "model.demo.stg_orders": {"resource_type": "model", "name": "stg_orders"},
        "model.demo.dim_users": {"resource_type": "model", "name": "dim_users"},
        "test.demo.t1": {"resource_type": "test", "name": "t1"},
    },
    "sources": {
        "source.demo.raw.orders": {"source_name": "raw", "name": "orders"},
    },
    "macros": {
        "macro.demo.cents_to_dollars": {"name": "cents_to_dollars"},
    },
}


def test_extracts_model_names():
    syms = extract_symbols(MANIFEST)
    assert sorted(syms["models"]) == ["dim_users", "stg_orders"]


def test_excludes_non_models_from_models():
    assert "t1" not in extract_symbols(MANIFEST)["models"]


def test_extracts_sources():
    assert {"source": "raw", "table": "orders"} in extract_symbols(MANIFEST)["sources"]


def test_extracts_macros():
    assert "cents_to_dollars" in extract_symbols(MANIFEST)["macros"]


def test_empty_manifest():
    syms = extract_symbols({})
    assert syms == {"models": [], "sources": [], "macros": []}
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_manifest_symbols.py -v`
Expected: FAIL — `No module named 'utils.manifest_symbols'`.

- [ ] **Step 3: Implement the extractor**

Create `backend/utils/manifest_symbols.py`:
```python
"""Extract autocomplete symbols from a dbt manifest.json dict (issue 16)."""


def extract_symbols(manifest: dict) -> dict:
    nodes = (manifest or {}).get("nodes", {})
    sources = (manifest or {}).get("sources", {})
    macros = (manifest or {}).get("macros", {})

    models = [n["name"] for n in nodes.values()
              if n.get("resource_type") == "model" and n.get("name")]
    source_pairs = [{"source": s.get("source_name"), "table": s.get("name")}
                    for s in sources.values()
                    if s.get("source_name") and s.get("name")]
    macro_names = [m["name"] for m in macros.values() if m.get("name")]

    return {"models": models, "sources": source_pairs, "macros": macro_names}
```

- [ ] **Step 4: Implement the endpoint**

Create `backend/routes/symbol_routes.py`:
```python
"""Autocomplete symbol endpoint (issue 16): model/source/macro names from the
Project's manifest.json."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user, CurrentUser
from utils.user_paths import resolve_under_root
from utils.dbt_utils import parse_dbt_manifest
from utils.manifest_symbols import extract_symbols

router = APIRouter()


class ProjectPathRequest(BaseModel):
    path: str


@router.post("/api/manifest-symbols")
async def manifest_symbols(req: ProjectPathRequest, user: CurrentUser = Depends(get_current_user)):
    worktree = resolve_under_root(user.sub, req.path)
    manifest = parse_dbt_manifest(worktree)
    if not manifest:
        return {"models": [], "sources": [], "macros": [], "compiled": False}
    return {**extract_symbols(manifest), "compiled": True}
```

- [ ] **Step 5: Mount the router**

In `backend/main.py`:
```python
from routes.symbol_routes import router as symbol_router
app.include_router(symbol_router)
```

- [ ] **Step 6: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_manifest_symbols.py -v`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/utils/manifest_symbols.py backend/routes/symbol_routes.py backend/main.py backend/tests/test_manifest_symbols.py
git commit -m "feat(autocomplete): /api/manifest-symbols from manifest.json"
```

---

## Task 5: Monaco ref()/source()/config() autocomplete (issue 16 — frontend, manual)

**Files:**
- Modify: `frontend/src/components/editor/editor/EditorContent.tsx` (register the provider on mount)

> Fetch symbols when a file opens or the manifest is recompiled (`compilationTrigger`
> already exists in `MainLayout`/`Editor`). Register one Monaco completion provider
> that triggers inside `ref('`, `source('`, `config(`.

- [ ] **Step 1: Load symbols in `Editor.tsx`**

Add state + an effect keyed on `projectPath` and `compilationTrigger`:
```tsx
const [symbols, setSymbols] = useState<{ models: string[]; sources: { source: string; table: string }[]; macros: string[] }>({ models: [], sources: [], macros: [] })

useEffect(() => {
  if (!projectPath) return
  apiFetch(apiUrl('/api/manifest-symbols'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: projectPath }),
  }).then(r => r.json()).then(setSymbols).catch(() => {})
}, [projectPath, compilationTrigger])
```
Pass `symbols` to `EditorContent`.

- [ ] **Step 2: Register the provider in `EditorContent.tsx`**

`@monaco-editor/react` exposes `onMount={(editor, monaco) => ...}`. Register once;
keep the latest symbols in a ref so the provider always reads fresh data:
```tsx
const symbolsRef = useRef(symbols)
useEffect(() => { symbolsRef.current = symbols }, [symbols])

const handleMount = (editor, monaco) => {
  monaco.languages.registerCompletionItemProvider(['sql', 'jinja-sql', 'sql-jinja'], {
    triggerCharacters: ["'", '"', '('],
    provideCompletionItems(model, position) {
      const line = model.getValueInRange({
        startLineNumber: position.lineNumber, startColumn: 1,
        endLineNumber: position.lineNumber, endColumn: position.column,
      })
      const mk = (label: string, insert: string) => ({
        label, kind: monaco.languages.CompletionItemKind.Value, insertText: insert,
      })
      if (/ref\(\s*['"]$/.test(line)) {
        return { suggestions: symbolsRef.current.models.map(m => mk(m, m)) }
      }
      if (/source\(\s*['"]$/.test(line)) {
        return { suggestions: symbolsRef.current.sources.map(s =>
          mk(`${s.source}.${s.table}`, `${s.source}', '${s.table}`)) }
      }
      if (/config\(\s*$/.test(line)) {
        const opts = ['materialized', 'schema', 'alias', 'tags', 'unique_key']
        return { suggestions: opts.map(o => mk(o, `${o}=`)) }
      }
      return { suggestions: [] }
    },
  })
}
```
Wire `onMount={handleMount}` on `<MonacoEditor />`.

- [ ] **Step 3: Manual verification**

Run: `cd frontend && npm run dev`
- After a successful `dbt compile`, typing `ref('` suggests model names; `source('`
  suggests `source.table`; `config(` suggests config keys.
- Recompile (changes the manifest) → new models appear in suggestions.
- Suggestions reflect only the current Project (the worktree's manifest).

- [ ] **Step 4: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/editor/editor/EditorContent.tsx frontend/src/components/editor/editor/Editor.tsx
git commit -m "feat(autocomplete): ref/source/config Monaco completions from manifest"
```

---

## Task 6: `useEditorTabs` store with per-tab content cache (issue 14 — frontend)

**Files:**
- Create: `frontend/src/components/main/hooks/useEditorTabs.ts`

> The crux of multi-tab: today `useFileContent(selectedFile)` reloads from disk on
> every switch, so naive tabs would discard unsaved edits. This store keeps the open
> set, the active path, and a **per-path content cache** so switching tabs restores
> the in-progress buffer. The `Editor` reads/writes the active tab's cached content
> instead of reloading on every switch.

- [ ] **Step 1: Implement the hook**

Create `frontend/src/components/main/hooks/useEditorTabs.ts`:
```ts
import { useState, useCallback } from 'react'

export interface TabCache {
  content: string
  originalContent: string
  loaded: boolean      // false until first disk load completes
}

export interface UseEditorTabs {
  openPaths: string[]
  activePath: string | null
  isDirty: (path: string) => boolean
  openTab: (path: string) => void
  closeTab: (path: string) => void
  setActive: (path: string) => void
  getCache: (path: string) => TabCache | undefined
  setCache: (path: string, patch: Partial<TabCache>) => void
}

export function useEditorTabs(): UseEditorTabs {
  const [openPaths, setOpenPaths] = useState<string[]>([])
  const [activePath, setActivePath] = useState<string | null>(null)
  const [cache, setCacheState] = useState<Record<string, TabCache>>({})

  const openTab = useCallback((path: string) => {
    setOpenPaths(prev => (prev.includes(path) ? prev : [...prev, path]))
    setActivePath(path)
  }, [])

  const closeTab = useCallback((path: string) => {
    setOpenPaths(prev => {
      const next = prev.filter(p => p !== path)
      setActivePath(cur => (cur === path ? (next[next.length - 1] ?? null) : cur))
      return next
    })
    setCacheState(prev => {
      const { [path]: _drop, ...rest } = prev
      return rest
    })
  }, [])

  const setCache = useCallback((path: string, patch: Partial<TabCache>) => {
    setCacheState(prev => ({
      ...prev,
      [path]: { content: '', originalContent: '', loaded: false, ...prev[path], ...patch },
    }))
  }, [])

  const isDirty = useCallback(
    (path: string) => {
      const c = cache[path]
      return !!c && c.loaded && c.content !== c.originalContent
    },
    [cache],
  )

  return {
    openPaths, activePath, isDirty,
    openTab, closeTab, setActive: setActivePath,
    getCache: (path) => cache[path],
    setCache,
  }
}
```

- [ ] **Step 2 (optional but recommended): sanity-check the reducer logic**

No FE test runner is configured. If you want a guard for this pure logic, add
`vitest` (`npm i -D vitest`) and a small spec asserting: opening twice doesn't
duplicate, closing the active tab activates a neighbour, `isDirty` is true only when
`content !== originalContent` and `loaded`. Otherwise verify via Task 7's manual run.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/main/hooks/useEditorTabs.ts
git commit -m "feat(tabs): editor tab store with per-path content cache"
```

---

## Task 7: TabBar + wire MainLayout/Editor (issue 14 — frontend, manual)

**Files:**
- Create: `frontend/src/components/editor/editor/TabBar.tsx`
- Modify: `frontend/src/components/main/MainLayout.tsx`
- Modify: `frontend/src/components/editor/editor/Editor.tsx`

> Replace the single `selectedFile` with the tab store. The active tab's path drives
> the `Editor`; the `Editor` seeds its buffer from the tab cache (loading from disk
> only the first time a tab is opened) and writes edits back to the cache so switching
> away and back preserves them.

- [ ] **Step 1: Build `TabBar.tsx`**

```tsx
import { X } from 'lucide-react'

interface TabBarProps {
  openPaths: string[]
  activePath: string | null
  isDirty: (p: string) => boolean
  onActivate: (p: string) => void
  onClose: (p: string) => void
}

export default function TabBar({ openPaths, activePath, isDirty, onActivate, onClose }: TabBarProps) {
  if (openPaths.length === 0) return null
  return (
    <div className="tab-bar" role="tablist">
      {openPaths.map(path => {
        const name = path.split('/').pop() ?? path
        return (
          <div key={path} role="tab" aria-selected={path === activePath}
               className={`tab ${path === activePath ? 'tab-active' : ''}`}
               onClick={() => onActivate(path)} title={path}>
            <span className="tab-name">{name}</span>
            {isDirty(path) && <span className="tab-dirty" aria-label="unsaved">●</span>}
            <button className="tab-close" aria-label={`Close ${name}`}
                    onClick={(e) => { e.stopPropagation(); onClose(path) }}>
              <X size={12} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
```
Add `.tab-bar/.tab/.tab-active/.tab-dirty/.tab-close` styles to `Editor.css`
(horizontal strip, active tab raised, dirty dot in the accent color).

- [ ] **Step 2: Use the tab store in `MainLayout.tsx`**

- Replace `const [selectedFile, setSelectedFile] = useState<string|null>(null)` with:
  ```tsx
  const tabs = useEditorTabs()
  ```
- Where `onFileSelect={setSelectedFile}` was passed to the Sidebar, pass
  `onFileSelect={tabs.openTab}`.
- Where `selectedFile={selectedFile}` was passed to the `Editor`, pass
  `selectedFile={tabs.activePath}` and also pass the `tabs` object (or the specific
  cache getters/setters) so the Editor can read/write the active tab's buffer.
- Render `<TabBar ... />` directly above the `Editor`, fed from `tabs`.
- The existing `hasUnsavedChanges`/`modifiedFiles` plumbing now derives from
  `tabs.isDirty`; keep the unsaved-changes guard, but check **all** open tabs before a
  destructive project action (loop `tabs.openPaths.some(tabs.isDirty)`).

- [ ] **Step 3: Make `Editor.tsx` read/write the active tab cache**

In `Editor`, change `useFileContent` usage so that:
- On activating a path whose cache `loaded === false`, load from disk (the existing
  `/api/read-file` path) and `tabs.setCache(path, { content, originalContent, loaded: true })`.
- On activating a path already `loaded`, seed `content`/`originalContent` from
  `tabs.getCache(path)` **without** re-reading disk.
- On every edit, `tabs.setCache(activePath, { content })` so the dirty state + buffer
  persist across switches.
- After a successful save (`useFileSave`), `tabs.setCache(path, { originalContent: content })`
  so the dirty dot clears.

> Keep the change minimal: `useFileContent` can stay as the disk loader for the
> first load; the cache is the source of truth thereafter. Do not duplicate server
> state — the cache holds the in-progress buffer only.

- [ ] **Step 4: Manual verification (issue 14 acceptance)**

Run: `cd frontend && npm run dev`
- Open several files → each appears as a tab; clicking a tab switches the editor.
- Edit file A, switch to B, back to A → A's unsaved edits are preserved; A shows the
  dirty dot.
- Save A → dirty dot clears; disk content matches.
- Close a dirty tab → the unsaved-changes guard prompts (reuse `UnsavedChangesModal`).
- All file operations still resolve under the user's worktree root (issue 03) — open
  a file, confirm reads/saves hit `/api/read-file`/`/api/write-file` with the
  worktree sub-path.

- [ ] **Step 5: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: success.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/editor/editor/TabBar.tsx frontend/src/components/main/MainLayout.tsx frontend/src/components/editor/editor/Editor.tsx frontend/src/components/editor/Editor.css
git commit -m "feat(tabs): multi-tab editing with per-tab unsaved indicators"
```

---

## Task 8: M4 verification gate

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite green**

Run: `cd backend && python -m pytest -v`
Expected: all pass (M1 + M2 + [M3 if merged] + M4: sqlfluff install, format-sql, manifest-symbols).

- [ ] **Step 2: Frontend builds**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: success.

- [ ] **Step 3: Multi-tab edit-preservation walk-through (issue 14)**

Open ≥3 files; edit two without saving; switch among all tabs; confirm each retains
its buffer and dirty dot; save one and confirm only its dot clears; close a dirty tab
and confirm the guard fires.

- [ ] **Step 4: Format walk-through (issue 15)**

Format a messy `.sql` model (buffer changes, disk unchanged until save); add a
`.sqlfluff` and confirm dialect is honored; a parse error leaves the buffer intact.

- [ ] **Step 5: Autocomplete walk-through (issue 16)**

After `dbt compile`: `ref('` → models, `source('` → sources, `config(` → keys;
recompile and confirm new models appear; suggestions scoped to the current Project.

- [ ] **Step 6: Path-authority spot check**

Run: `cd backend && grep -rn "resolve_under_root" routes/format_routes.py routes/symbol_routes.py`
Expected: both endpoints resolve under the user root (no client-trusted absolute paths).

---

## Self-Review notes

- **Issue 14 (multi-tab):** Task 6 (`useEditorTabs` + content cache) + Task 7 (TabBar + MainLayout/Editor wiring). Per-tab unsaved indicator = `isDirty`; edit preservation = the per-path cache; path authority unchanged (still `/api/read-file`/`write-file` under the worktree). ✅
- **Issue 15 (SQL format):** Task 1 (install sqlfluff in venv) + Task 2 (`/api/format-sql`, stateless, `.sqlfluff` honored via worktree cwd) + Task 3 (Format button). File is not changed on disk until save (buffer-only `setContent`). ✅
- **Issue 16 (ref/source autocomplete):** Task 4 (`/api/manifest-symbols`) + Task 5 (Monaco provider for `ref(`/`source(`/`config(`); refresh on `compilationTrigger`; Project-scoped via the worktree manifest). ✅
- **Dependency posture:** M4 needs only M1 (path authority, auth, venv) + M2 (worktree provisioning so a real manifest/`.sqlfluff` exist per user). **Independent of M3** — can ship before or after it. Only shared file with M3 is `venv_routes.py` (additive `FORMAT_TOOLS` vs M3's `DBT_ADAPTERS`); merge by keeping both install calls.
- **Shared-code change to reconcile:** `run_command` may need a `stdin=`/`input=` kwarg for Task 2. That is the only edit to existing utility signatures; everything else is additive.
- **Frontend testing:** no runner exists, so FE tasks are manual (consistent with M2/M3). The one piece of non-trivial pure logic (`useEditorTabs`) has an optional vitest spec suggested in Task 6 Step 2; adopt it if the team wants a regression guard without standing up full FE test infra.
- **Out of scope:** split-pane / side-by-side editing, drag-to-reorder tabs, format-on-save as a default (left as an opt-in follow-up), and lint (as opposed to format) surfacing — none are in issues 14–16.
