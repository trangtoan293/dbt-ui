# M3 — Engine Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dbt actually execute against query engines per the trust tiers: install the three adapters, run dbt against DuckDB from a per-user worktree, let an admin define secret-free per-project Connection config that dbt-ui templates into each worktree's `profiles.yml`, switch the active target, Test Connection, and — for the Production Engine (Dremio) — exchange the User's Keycloak token at job start so dbt connects AS the User, with the developer role barred from production.

**Architecture:** Connection config is **secret-free** and lives in the M2 admin Catalog entry (a `connections` block per Project, keyed by target name → `{engine, ...}`). dbt-ui **owns** each worktree's `profiles.yml`: it is rendered server-side from the Catalog connections when a Project is opened and when the active target changes — users never hand-edit it. dbt continues to run with `--profiles-dir <worktree>` (existing behaviour). For Dev Engines (DuckDB/Spark) the profile is complete and identity-free. For the Production Engine (Dremio) the profile's `token` field is `{{ env_var('DREMIO_TOKEN') }}`; at **job submission** the backend captures the requesting User's still-valid Keycloak access token, performs an RFC 8693 token exchange (ADR 0001 §6) for a short-lived Dremio token, holds it in memory scoped to that one job, and injects it into the dbt subprocess env — never persisted, scrubbed from logs.

**Tech Stack:** FastAPI, dbt-core + dbt-duckdb/dbt-spark/dbt-dremio adapters, `uv pip`, PyYAML, `httpx` (Keycloak token exchange), pytest + httpx, React + Monaco.

**Covers issues:** `docs/issues/11..13`. Glossary: `CONTEXT.md`. Decisions: `docs/adr/0001-multi-user-keycloak-architecture.md`.

---

## HARD DEPENDENCY ON M1 + M2

This plan calls these symbols verbatim. **If M1/M2 shipped different names, reconcile before executing M3.**

From **M1**:
- `auth.CurrentUser` (fields `sub`, `email`, `roles`; M2 added `name`).
- `auth.get_current_user` — request dependency returning `CurrentUser`.
- `auth.require_role(role: str)` — dependency factory, 403 on missing role.
- `utils.user_paths.resolve_under_root(sub, sub_path) -> Path` and `user_root(sub) -> Path`.
- `utils.audit.audit(sub, action, target, extra)`.
- `utils.secret_scrub.scrub(text) -> str`.
- `utils.input_validation.validate_dbt_target(target) -> str`.
- `tests/conftest.py` fixture `make_token(sub, email, roles, ...)`.

From **M2**:
- `utils.catalog` — `load() -> list[dict]`, `get(project_id) -> dict | None`, entries shaped `{"id": str, "repo_path": str, "main_branch": str}`, JSON-backed at `CATALOG_PATH`. **M3 adds** a `connections` key to each entry (Task 3).
- `utils.worktree.provision(sub, project_id, repo_path, main_branch) -> str`.
- `routes/catalog_routes.py` with `/api/open-project` — **M3 modifies** it to render `profiles.yml` after provisioning (Task 6).
- `tests/conftest.py` fixture `git_project` — a canonical local repo on `main` with `dbt_project.yml` (`profile: demo`).

M3 also reuses existing code in `routes/dbt_routes.py`: `run_dbt_command_task(sub, path, command, selector, target, full_refresh, env_vars)`, `get_dbt_env`, `get_venv_dbt_path`, the `dbt_command_status` dict, and the `validate_dbt_selector`/`validate_dbt_target` guards; `routes/venv_routes.py` `_recreate_venv_sync`; `utils/venv_utils.py` `get_venv_python_path`.

---

## Key design decisions (derived from ADR 0001 + CONTEXT.md, not re-litigated here)

1. **Connection config is secret-free and admin-owned** (CONTEXT → *Connection*). Stored in the Catalog entry. Per-User credentials are never part of it.
2. **profiles.yml is generated, not authored.** dbt-ui renders it into the worktree from the Catalog connections. A hand-edited `profiles.yml` will be overwritten on the next open/target-switch. This keeps engine config auditable and centralised.
3. **Engine trust tiers** (ADR §5): `duckdb` and `spark` are **Dev Engines** (identity-free, shared process identity). `dremio` is the **Production Engine** — per-User identity required.
4. **Dremio identity = token exchange at job start** (ADR §6): the Keycloak access token is exchanged for a short-lived Dremio token at submission, injected via env var, never stored, scrubbed from logs. Jobs that outlive the Dremio token fail with a clear message (refresh out of scope).
5. **RBAC**: only `admin` may write Connection config; only `maintainer` may run against the Production Engine; `developer` is 403 on any Dremio target.

---

## File Structure

- Create `backend/utils/profiles.py` — pure render of a profiles.yml dict from a Catalog `connections` block + profile name; writer into a worktree. One responsibility: config → YAML.
- Create `backend/utils/connections.py` — validate a `connections` block (engine whitelist, **no-secret** enforcement); map target → engine; classify Dev vs Production.
- Create `backend/utils/dremio_token.py` — RFC 8693 token exchange seam (Keycloak → Dremio), in-memory, never logged.
- Create `backend/routes/connection_routes.py` — `/api/connections/*` (get for any user, set admin-only, test-connection, set-target).
- Modify `backend/routes/venv_routes.py` — install the three adapters alongside dbt-core.
- Modify `backend/routes/catalog_routes.py` — render `profiles.yml` after worktree provisioning in `/api/open-project`.
- Modify `backend/routes/dbt_routes.py` — capture raw token at submit, gate Production engine by role, inject the exchanged Dremio token into the subprocess for Dremio targets.
- Modify `backend/main.py` — mount `connection_router`.
- Modify `backend/tests/conftest.py` — add a `catalog_with_conn` fixture.
- Frontend: add a `ConnectionPanel` (admin config + Test Connection), a target switcher in the dbt runner, and wire both through `apiFetch`.

---

## Task 0: Test fixtures for connections

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add a `catalog_with_conn` fixture**

Append to `backend/tests/conftest.py` (reuses the M2 `git_project` fixture):
```python
@pytest.fixture
def catalog_with_conn(tmp_path, git_project, monkeypatch):
    """A Catalog with one project that has dev (duckdb) + prod (dremio) connections."""
    import json
    catalog_path = tmp_path / "catalog.json"
    entry = {
        "id": "p1",
        "name": "Demo",
        "repo_path": str(git_project),
        "main_branch": "main",
        "connections": {
            "dev": {"engine": "duckdb", "path": "dev.duckdb", "schema": "main"},
            "prod": {"engine": "dremio", "host": "dremio.local", "port": 9047,
                     "database": "dl", "schema": "analytics"},
        },
    }
    catalog_path.write_text(json.dumps([entry]))
    monkeypatch.setenv("CATALOG_PATH", str(catalog_path))
    return entry
```

- [ ] **Step 2: Verify fixture loads**

Run: `cd backend && python -m pytest -q`
Expected: collection succeeds, no errors.

---

## Task 1: Install the three adapters into the venv (issue 11)

**Files:**
- Modify: `backend/routes/venv_routes.py`
- Test: `backend/tests/test_adapters_install.py`

- [ ] **Step 1: Write the failing test**

The install is a subprocess; the test asserts the adapter install command is issued. Create `backend/tests/test_adapters_install.py`:
```python
import routes.venv_routes as vr


def test_dbt_adapters_constant_lists_three_engines():
    assert set(vr.DBT_ADAPTERS) == {"dbt-duckdb", "dbt-spark", "dbt-dremio"}


def test_install_adapters_issues_pip_command(monkeypatch, tmp_path):
    calls = []

    class _Res:
        success = True
        stdout = "ok"
        stderr = ""
        error = ""

    def fake_run(cmd, cwd, timeout=None, env=None):
        calls.append(cmd)
        return _Res()

    monkeypatch.setattr(vr, "run_command", fake_run)
    vr.install_adapters(tmp_path / ".dbt-ui-venv" / "bin" / "python", tmp_path, [])

    flat = [c for call in calls for c in call]
    assert "dbt-duckdb" in flat and "dbt-spark" in flat and "dbt-dremio" in flat
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_adapters_install.py -v`
Expected: FAIL — `AttributeError: module 'routes.venv_routes' has no attribute 'DBT_ADAPTERS'`.

- [ ] **Step 3: Add the adapters constant + installer**

Near the top of `backend/routes/venv_routes.py` (after imports), add:
```python
# Engine adapters installed into every project venv (issue 11).
# DuckDB + Spark are Dev Engines; Dremio is the Production Engine (ADR 0001 §5).
DBT_ADAPTERS = ["dbt-duckdb", "dbt-spark", "dbt-dremio"]


def install_adapters(venv_python, path, output_lines):
    """Install the dbt engine adapters into the project venv. Best-effort per
    adapter so one failing adapter does not block the others; failures are
    reported in output_lines."""
    for adapter in DBT_ADAPTERS:
        result = run_command(
            ["uv", "pip", "install", adapter, "--python", str(venv_python)],
            path,
            timeout=300,
        )
        if result.success:
            output_lines.append(f"Successfully installed {adapter}")
        else:
            output_lines.append(f"Warning: failed to install {adapter}: {result.stderr}")
```

- [ ] **Step 4: Call it after dbt-core installs**

In `_recreate_venv_sync`, immediately after the `output_lines.append(f"Successfully installed {dbt_core_spec}")` block (before the "Get installed dbt version" step), add:
```python
    # Install engine adapters (issue 11)
    output_lines.append("\nInstalling engine adapters...")
    install_adapters(venv_python, path, output_lines)
```

- [ ] **Step 5: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_adapters_install.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/venv_routes.py backend/tests/test_adapters_install.py
git commit -m "feat(engine): install dbt-duckdb/spark/dremio adapters into venv"
```

---

## Task 2: Connection validation + engine classification (issue 12)

**Files:**
- Create: `backend/utils/connections.py`
- Test: `backend/tests/test_connections.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_connections.py`:
```python
import pytest
from fastapi import HTTPException
from utils.connections import (
    validate_connections, engine_for_target, is_production_engine,
    SECRET_KEYS, DEV_ENGINES, PROD_ENGINES,
)


def test_valid_block_passes():
    block = {
        "dev": {"engine": "duckdb", "path": "dev.duckdb"},
        "prod": {"engine": "dremio", "host": "h", "port": 9047},
    }
    validate_connections(block)  # no raise


def test_rejects_unknown_engine():
    with pytest.raises(HTTPException) as e:
        validate_connections({"dev": {"engine": "oracle"}})
    assert e.value.status_code == 400


def test_rejects_secret_keys():
    for secret in SECRET_KEYS:
        with pytest.raises(HTTPException) as e:
            validate_connections({"prod": {"engine": "dremio", secret: "x"}})
        assert e.value.status_code == 400


def test_engine_for_target():
    block = {"dev": {"engine": "duckdb"}, "prod": {"engine": "dremio"}}
    assert engine_for_target(block, "prod") == "dremio"
    assert engine_for_target(block, "dev") == "duckdb"


def test_production_classification():
    assert is_production_engine("dremio") is True
    assert is_production_engine("duckdb") is False
    assert is_production_engine("spark") is False
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_connections.py -v`
Expected: FAIL — `No module named 'utils.connections'`.

- [ ] **Step 3: Implement `connections.py`**

Create `backend/utils/connections.py`:
```python
"""Validate and classify Project Connection config (CONTEXT.md -> Connection).

A Connection is secret-free, admin-owned, and per-Project. It is stored in the
Catalog entry under "connections": {target_name: {engine, ...non-secret fields}}.
Per-User credentials (Dremio token) are runtime and NEVER part of this config.
"""
from fastapi import HTTPException

DEV_ENGINES = {"duckdb", "spark"}
PROD_ENGINES = {"dremio"}
ALL_ENGINES = DEV_ENGINES | PROD_ENGINES

# Keys that would carry a secret — forbidden in Connection config.
SECRET_KEYS = {"password", "token", "pat", "secret", "client_secret",
               "private_key", "private_key_path", "access_token", "api_key"}


def validate_connections(block: dict) -> None:
    """Raise HTTPException(400) if the connections block is malformed or holds
    any secret. A valid block maps target_name -> {engine: <known>, ...}."""
    if not isinstance(block, dict) or not block:
        raise HTTPException(status_code=400, detail="connections must be a non-empty object")

    for target, cfg in block.items():
        if not isinstance(cfg, dict):
            raise HTTPException(status_code=400, detail=f"target '{target}' must be an object")
        engine = cfg.get("engine")
        if engine not in ALL_ENGINES:
            raise HTTPException(
                status_code=400,
                detail=f"target '{target}': unknown engine '{engine}' "
                       f"(allowed: {sorted(ALL_ENGINES)})",
            )
        leaked = {k for k in cfg if k.lower() in SECRET_KEYS}
        if leaked:
            raise HTTPException(
                status_code=400,
                detail=f"target '{target}': connection config must not contain "
                       f"secrets {sorted(leaked)} — credentials are per-user and runtime",
            )


def engine_for_target(block: dict, target: str) -> str:
    cfg = block.get(target)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"target '{target}' not configured")
    return cfg["engine"]


def is_production_engine(engine: str) -> bool:
    return engine in PROD_ENGINES
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_connections.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/connections.py backend/tests/test_connections.py
git commit -m "feat(engine): secret-free Connection validation + engine tiers"
```

---

## Task 3: Render profiles.yml from connections (issues 11, 12)

**Files:**
- Create: `backend/utils/profiles.py`
- Test: `backend/tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_profiles.py`:
```python
import yaml
from pathlib import Path
from utils.profiles import build_profile, write_profiles


CONN = {
    "dev": {"engine": "duckdb", "path": "dev.duckdb", "schema": "main"},
    "prod": {"engine": "dremio", "host": "h", "port": 9047,
             "database": "dl", "schema": "analytics"},
}


def test_build_profile_shape():
    prof = build_profile("demo", CONN, default_target="dev")
    assert "demo" in prof
    assert prof["demo"]["target"] == "dev"
    assert set(prof["demo"]["outputs"]) == {"dev", "prod"}


def test_duckdb_output_is_complete_and_identity_free():
    out = build_profile("demo", CONN)["demo"]["outputs"]["dev"]
    assert out["type"] == "duckdb"
    assert out["path"] == "dev.duckdb"
    assert "token" not in out  # Dev Engine: no per-user identity


def test_dremio_output_references_runtime_token_env():
    out = build_profile("demo", CONN)["demo"]["outputs"]["prod"]
    assert out["type"] == "dremio"
    assert out["host"] == "h"
    # token is supplied at runtime via env var, never stored in the file
    assert out["token"] == "{{ env_var('DREMIO_TOKEN') }}"


def test_write_profiles_creates_file(tmp_path):
    write_profiles(tmp_path, "demo", CONN, default_target="dev")
    written = yaml.safe_load((tmp_path / "profiles.yml").read_text())
    assert written["demo"]["outputs"]["dev"]["type"] == "duckdb"
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_profiles.py -v`
Expected: FAIL — `No module named 'utils.profiles'`.

- [ ] **Step 3: Implement `profiles.py`**

Create `backend/utils/profiles.py`:
```python
"""Render a dbt profiles.yml from a Project's secret-free Connection block.

dbt-ui OWNS profiles.yml: it is generated into each worktree from the Catalog
connections (admin-set). For Dev Engines the output is complete. For the
Production Engine (Dremio) the credential is supplied at runtime via the
DREMIO_TOKEN env var (token exchange at job start, ADR 0001 §6) — the file only
references it, never embeds it.
"""
from pathlib import Path
import yaml

# env var name the dbt subprocess reads the exchanged Dremio token from.
DREMIO_TOKEN_ENV = "DREMIO_TOKEN"


def _output_for(target_cfg: dict) -> dict:
    engine = target_cfg["engine"]
    if engine == "duckdb":
        out = {"type": "duckdb", "path": target_cfg.get("path", "dev.duckdb")}
        if "schema" in target_cfg:
            out["schema"] = target_cfg["schema"]
        return out
    if engine == "spark":
        return {
            "type": "spark",
            "method": target_cfg.get("method", "thrift"),
            "host": target_cfg["host"],
            "port": target_cfg.get("port", 10000),
            "schema": target_cfg.get("schema", "default"),
        }
    if engine == "dremio":
        # Production Engine: identity supplied at runtime via env var.
        out = {
            "type": "dremio",
            "host": target_cfg["host"],
            "port": target_cfg.get("port", 9047),
            "token": "{{ env_var('" + DREMIO_TOKEN_ENV + "') }}",
            "use_ssl": target_cfg.get("use_ssl", True),
        }
        for k in ("database", "schema", "object_storage_source",
                  "object_storage_path", "dremio_space"):
            if k in target_cfg:
                out[k] = target_cfg[k]
        return out
    raise ValueError(f"unsupported engine: {engine}")


def build_profile(profile_name: str, connections: dict, default_target: str | None = None) -> dict:
    """Build the profiles.yml dict for one Project."""
    outputs = {t: _output_for(cfg) for t, cfg in connections.items()}
    target = default_target or next(iter(connections))
    return {profile_name: {"target": target, "outputs": outputs}}


def write_profiles(worktree: Path, profile_name: str, connections: dict,
                   default_target: str | None = None) -> Path:
    """Render and write profiles.yml into the worktree. Overwrites any existing."""
    worktree = Path(worktree)
    profile = build_profile(profile_name, connections, default_target)
    dest = worktree / "profiles.yml"
    dest.write_text(yaml.safe_dump(profile, sort_keys=False))
    return dest
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_profiles.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/profiles.py backend/tests/test_profiles.py
git commit -m "feat(engine): render profiles.yml from secret-free connections"
```

---

## Task 4: Resolve a Project's profile name (shared helper)

**Files:**
- Modify: `backend/utils/profiles.py`
- Test: `backend/tests/test_profile_name.py`

> The profile name comes from `dbt_project.yml` (`profile:` key, fallback `name:`),
> mirroring the existing `/api/get-profile-targets` logic. Extract it so both
> open-project and the connection endpoints use one resolver.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_profile_name.py`:
```python
from utils.profiles import resolve_profile_name


def test_reads_profile_key(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: demo\nprofile: demo_profile\n")
    assert resolve_profile_name(tmp_path) == "demo_profile"


def test_falls_back_to_name(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: demo\n")
    assert resolve_profile_name(tmp_path) == "demo"
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_profile_name.py -v`
Expected: FAIL — `cannot import name 'resolve_profile_name'`.

- [ ] **Step 3: Add the resolver to `profiles.py`**

Append to `backend/utils/profiles.py`:
```python
def resolve_profile_name(worktree: Path) -> str:
    """Read the profile name from dbt_project.yml (profile: -> name: fallback)."""
    dbt_project = Path(worktree) / "dbt_project.yml"
    if not dbt_project.exists():
        raise FileNotFoundError("dbt_project.yml not found")
    data = yaml.safe_load(dbt_project.read_text()) or {}
    name = data.get("profile") or data.get("name")
    if not name:
        raise ValueError("no profile name in dbt_project.yml")
    return name
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_profile_name.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/profiles.py backend/tests/test_profile_name.py
git commit -m "feat(engine): resolve dbt profile name from dbt_project.yml"
```

---

## Task 5: Render profiles.yml on open-project (issues 11, 12)

**Files:**
- Modify: `backend/routes/catalog_routes.py`
- Test: `backend/tests/test_open_project_profiles.py`

> After M2's `/api/open-project` provisions the worktree, M3 renders profiles.yml
> into it from the entry's `connections`. Adjust the symbol names below to match
> the actual M2 `catalog_routes.py` (the request model and the provision call).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_open_project_profiles.py`:
```python
import yaml
from pathlib import Path
from fastapi.testclient import TestClient
from main import app


def test_open_project_writes_profiles(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    r = client.post("/api/open-project", json={"id": "p1"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    wt = Path(r.json()["worktree"])
    profile = yaml.safe_load((wt / "profiles.yml").read_text())
    assert profile["demo"]["outputs"]["dev"]["type"] == "duckdb"
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_open_project_profiles.py -v`
Expected: FAIL — no `profiles.yml` written (file missing).

- [ ] **Step 3: Render profiles in the open-project handler**

In `backend/routes/catalog_routes.py`, import at the top:
```python
from utils.profiles import write_profiles, resolve_profile_name
from utils.connections import validate_connections
```

In the `/api/open-project` handler, after the line that provisions the worktree
(`worktree = provision(...)` — match the real variable name), add:
```python
    # Render profiles.yml from the Project's Connection config (issues 11, 12).
    connections = entry.get("connections")
    if connections:
        validate_connections(connections)
        profile_name = resolve_profile_name(worktree)
        write_profiles(worktree, profile_name, connections)
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_open_project_profiles.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/catalog_routes.py backend/tests/test_open_project_profiles.py
git commit -m "feat(engine): render profiles.yml into worktree on open-project"
```

---

## Task 6: Connection endpoints — get / set (admin) / set-target (issue 12)

**Files:**
- Create: `backend/routes/connection_routes.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_connection_routes.py`

> Set is admin-only (RBAC, issue 08). Setting connections re-validates (no secrets)
> and persists into the Catalog entry. Set-target re-renders profiles.yml for the
> calling user's worktree with the chosen default target.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_connection_routes.py`:
```python
import yaml
from pathlib import Path
from fastapi.testclient import TestClient
from main import app


def _open(client, tok):
    client.post("/api/open-project", json={"id": "p1"},
                headers={"Authorization": f"Bearer {tok}"})


def test_get_connections_any_user(catalog_with_conn, make_token):
    client = TestClient(app)
    tok = make_token(sub="u", email="u@x.io", roles=["developer"])
    r = client.post("/api/connections/get", json={"id": "p1"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert "prod" in r.json()["connections"]


def test_set_connections_requires_admin(catalog_with_conn, make_token):
    client = TestClient(app)
    dev = make_token(sub="d", email="d@x.io", roles=["developer"])
    r = client.post("/api/connections/set",
                    json={"id": "p1", "connections": {"dev": {"engine": "duckdb"}}},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 403


def test_set_connections_rejects_secret(catalog_with_conn, make_token):
    client = TestClient(app)
    admin = make_token(sub="a", email="a@x.io", roles=["admin"])
    r = client.post("/api/connections/set",
                    json={"id": "p1",
                          "connections": {"prod": {"engine": "dremio", "token": "leak"}}},
                    headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 400


def test_set_target_rerenders_profiles(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, tok)
    r = client.post("/api/connections/set-target", json={"id": "p1", "target": "dev"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    wt = Path(r.json()["worktree"])
    profile = yaml.safe_load((wt / "profiles.yml").read_text())
    assert profile["demo"]["target"] == "dev"
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_connection_routes.py -v`
Expected: FAIL — 404s (routes not mounted).

- [ ] **Step 3: Implement `connection_routes.py`**

Create `backend/routes/connection_routes.py`:
```python
"""Project Connection config endpoints (issue 12).

Get: any authenticated user. Set: admin only. Set-target: re-renders the calling
user's worktree profiles.yml with a new default target. All config is secret-free.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user, require_role, CurrentUser
from utils import catalog
from utils.connections import validate_connections, engine_for_target
from utils.profiles import write_profiles, resolve_profile_name
from utils.input_validation import validate_dbt_target
from utils.user_paths import resolve_under_root
from utils.audit import audit

router = APIRouter()


class ProjectIdRequest(BaseModel):
    id: str


class SetConnectionsRequest(BaseModel):
    id: str
    connections: dict


class SetTargetRequest(BaseModel):
    id: str
    target: str


@router.post("/api/connections/get")
async def get_connections(req: ProjectIdRequest, user: CurrentUser = Depends(get_current_user)):
    entry = catalog.get(req.id)
    if entry is None:
        return {"connections": {}}
    return {"connections": entry.get("connections", {})}


@router.post("/api/connections/set")
async def set_connections(req: SetConnectionsRequest,
                          user: CurrentUser = Depends(require_role("admin"))):
    validate_connections(req.connections)
    entry = catalog.get(req.id)
    if entry is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="project not in catalog")
    catalog.set_connections(req.id, req.connections)
    audit(sub=user.sub, action="connections_set", target=req.id,
          extra={"targets": list(req.connections.keys())})
    return {"ok": True}


@router.post("/api/connections/set-target")
async def set_target(req: SetTargetRequest, user: CurrentUser = Depends(get_current_user)):
    target = validate_dbt_target(req.target)
    entry = catalog.get(req.id)
    if entry is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="project not in catalog")
    connections = entry.get("connections", {})
    engine_for_target(connections, target)  # 404 if target unknown
    worktree = resolve_under_root(user.sub, req.id)
    profile_name = resolve_profile_name(worktree)
    write_profiles(worktree, profile_name, connections, default_target=target)
    audit(sub=user.sub, action="set_target", target=req.id, extra={"target": target})
    return {"ok": True, "worktree": str(worktree), "target": target}
```

- [ ] **Step 4: Add `set_connections` to the Catalog module**

In `backend/utils/catalog.py`, add (uses M2's `load()` + `_save()`, confirmed aligned):
```python
def set_connections(project_id: str, connections: dict) -> None:
    """Persist a connections block onto an existing Catalog entry."""
    entries = load()
    for entry in entries:
        if entry["id"] == project_id:
            entry["connections"] = connections
            _save(entries)
            return
    raise KeyError(project_id)
```

- [ ] **Step 5: Mount the router in `main.py`**

In `backend/main.py`, alongside the other `app.include_router(...)` calls:
```python
from routes.connection_routes import router as connection_router
app.include_router(connection_router)
```

- [ ] **Step 6: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_connection_routes.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/routes/connection_routes.py backend/utils/catalog.py backend/main.py backend/tests/test_connection_routes.py
git commit -m "feat(engine): connection get/set(admin)/set-target endpoints"
```

---

## Task 7: Dremio token exchange seam (issue 13)

**Files:**
- Create: `backend/utils/dremio_token.py`
- Test: `backend/tests/test_dremio_token.py`

> RFC 8693 token exchange (ADR 0001 §6). The actual Keycloak↔Dremio trust config is
> HITL (Task 13 verification). This task builds the seam and its failure modes;
> tests stub the HTTP call. The exchanged token is returned to the caller and held
> only in the job's process env — never persisted.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_dremio_token.py`:
```python
import pytest
from utils.dremio_token import exchange_for_dremio, TokenExchangeError


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def test_exchange_returns_access_token(monkeypatch):
    def fake_post(url, data=None, timeout=None):
        assert data["grant_type"] == "urn:ietf:params:oauth:grant-type:token-exchange"
        assert data["subject_token"] == "kc-token"
        return _Resp(200, {"access_token": "dremio-token", "expires_in": 3600})

    monkeypatch.setattr("utils.dremio_token.httpx.post", fake_post)
    monkeypatch.setenv("KEYCLOAK_TOKEN_URL", "https://kc/token")
    monkeypatch.setenv("DREMIO_AUDIENCE", "dremio")
    monkeypatch.setenv("DREMIO_EXCHANGE_CLIENT_ID", "dbt-ui")
    token = exchange_for_dremio("kc-token")
    assert token == "dremio-token"


def test_exchange_failure_raises(monkeypatch):
    def fake_post(url, data=None, timeout=None):
        return _Resp(400, {"error": "invalid_grant"})

    monkeypatch.setattr("utils.dremio_token.httpx.post", fake_post)
    monkeypatch.setenv("KEYCLOAK_TOKEN_URL", "https://kc/token")
    monkeypatch.setenv("DREMIO_AUDIENCE", "dremio")
    monkeypatch.setenv("DREMIO_EXCHANGE_CLIENT_ID", "dbt-ui")
    with pytest.raises(TokenExchangeError):
        exchange_for_dremio("kc-token")


def test_missing_config_raises(monkeypatch):
    monkeypatch.delenv("KEYCLOAK_TOKEN_URL", raising=False)
    with pytest.raises(TokenExchangeError):
        exchange_for_dremio("kc-token")
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_dremio_token.py -v`
Expected: FAIL — `No module named 'utils.dremio_token'`.

- [ ] **Step 3: Implement `dremio_token.py`**

Create `backend/utils/dremio_token.py`:
```python
"""Exchange a user's Keycloak access token for a short-lived Dremio token.

RFC 8693 token exchange, performed at dbt job START while the Keycloak token is
still valid (ADR 0001 §6). The result is short-lived, held only in the job's
subprocess env, never persisted, and scrubbed from logs. If a job outlives the
Dremio token, dbt fails — token refresh is out of scope.
"""
import os
import httpx

GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"


class TokenExchangeError(Exception):
    """Raised when the Keycloak->Dremio token exchange fails or is misconfigured."""


def exchange_for_dremio(keycloak_token: str) -> str:
    token_url = os.environ.get("KEYCLOAK_TOKEN_URL")
    audience = os.environ.get("DREMIO_AUDIENCE")
    client_id = os.environ.get("DREMIO_EXCHANGE_CLIENT_ID")
    if not (token_url and audience and client_id):
        raise TokenExchangeError(
            "Dremio token exchange not configured "
            "(KEYCLOAK_TOKEN_URL / DREMIO_AUDIENCE / DREMIO_EXCHANGE_CLIENT_ID)"
        )

    data = {
        "grant_type": GRANT,
        "client_id": client_id,
        "subject_token": keycloak_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": audience,
        "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
    }
    client_secret = os.environ.get("DREMIO_EXCHANGE_CLIENT_SECRET")
    if client_secret:
        data["client_secret"] = client_secret

    try:
        resp = httpx.post(token_url, data=data, timeout=15)
    except Exception as e:  # network errors must not leak the token
        raise TokenExchangeError("token exchange request failed") from e

    if resp.status_code != 200:
        raise TokenExchangeError(f"token exchange rejected (status {resp.status_code})")

    token = resp.json().get("access_token")
    if not token:
        raise TokenExchangeError("token exchange response had no access_token")
    return token
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_dremio_token.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/dremio_token.py backend/tests/test_dremio_token.py
git commit -m "feat(engine): Keycloak->Dremio RFC 8693 token-exchange seam"
```

---

## Task 8: Gate the Production Engine + inject the Dremio token at job start (issue 13)

**Files:**
- Modify: `backend/routes/dbt_routes.py`
- Test: `backend/tests/test_prod_engine_gate.py`

> At submission: resolve the chosen target's engine from the Catalog connections.
> If it is the Production Engine (Dremio): require the `maintainer` role (developer
> → 403), capture the raw Keycloak token from the Authorization header, exchange it
> NOW (while valid), and pass the result into the background task as
> `env_vars["DREMIO_TOKEN"]`. For Dev Engines, nothing changes.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_prod_engine_gate.py`:
```python
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app


def _open(client, tok):
    client.post("/api/open-project", json={"id": "p1"},
                headers={"Authorization": f"Bearer {tok}"})


def test_developer_blocked_from_prod_engine(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    dev = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, dev)
    r = client.post("/api/dbt-command",
                    json={"path": "p1", "command": "run", "target": "prod", "selector": ""},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 403


def test_maintainer_prod_run_exchanges_token(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    maint = make_token(sub="user-m", email="m@x.io", roles=["maintainer"])
    _open(client, maint)
    captured = {}

    def fake_task(sub, path, command, selector="", target="", full_refresh=False, env_vars=None):
        captured["env"] = env_vars or {}

    with patch("routes.dbt_routes.exchange_for_dremio", return_value="dremio-tok"), \
         patch("routes.dbt_routes.run_dbt_command_task", side_effect=fake_task):
        r = client.post("/api/dbt-command",
                        json={"path": "p1", "command": "run", "target": "prod", "selector": ""},
                        headers={"Authorization": f"Bearer {maint}"})
    assert r.status_code == 200
    assert captured["env"].get("DREMIO_TOKEN") == "dremio-tok"


def test_dev_target_no_token(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    dev = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, dev)
    captured = {}

    def fake_task(sub, path, command, selector="", target="", full_refresh=False, env_vars=None):
        captured["env"] = env_vars or {}

    with patch("routes.dbt_routes.run_dbt_command_task", side_effect=fake_task):
        r = client.post("/api/dbt-command",
                        json={"path": "p1", "command": "run", "target": "dev", "selector": ""},
                        headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 200
    assert "DREMIO_TOKEN" not in captured["env"]
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_prod_engine_gate.py -v`
Expected: FAIL — developer not blocked / token not injected.

- [ ] **Step 3: Add the gate + injection in the dbt-command handler**

In `backend/routes/dbt_routes.py`, add imports near the top:
```python
from utils import catalog
from utils.connections import engine_for_target, is_production_engine
from utils.dremio_token import exchange_for_dremio, TokenExchangeError
```

In the `/api/dbt-command` handler, after `target = validate_dbt_target(action.target)`
and before `background_tasks.add_task(...)`, insert:
```python
    # Engine trust gate (issue 13 / ADR 0001 §5). project_id == the sub-path.
    project_id = action.path
    entry = catalog.get(project_id)
    connections = entry.get("connections", {}) if entry else {}
    if target and connections:
        engine = engine_for_target(connections, target)
        if is_production_engine(engine):
            if "maintainer" not in user.roles:
                _audit(sub=user.sub, action="prod_run_denied", target=str(path),
                       extra={"target_env": target, "engine": engine})
                raise HTTPException(status_code=403,
                                    detail="Production Engine requires the maintainer role")
            # Exchange the still-valid Keycloak token NOW (job outlives it).
            header = request.headers.get("Authorization", "")
            kc_token = header[len("Bearer "):] if header.startswith("Bearer ") else ""
            try:
                dremio_token = exchange_for_dremio(kc_token)
            except TokenExchangeError as e:
                raise HTTPException(status_code=502,
                                    detail=f"Dremio token exchange failed: {e}")
            env_vars = {**(env_vars or {}), "DREMIO_TOKEN": dremio_token}
```

> `request` is already a handler param (the route is `async def ... (request: Request, ...)`);
> if not, add `request: Request` to the signature. `env_vars` is the dict already
> built from the env cookie earlier in the handler — this merges the token in.

- [ ] **Step 4: Confirm the token never reaches logs**

In `run_dbt_command_task`, the captured stdout/stderr is already passed through
`scrub(...)` (M1, issue 04). Verify `DREMIO_TOKEN` values are caught: add the
token-bearing query param/env pattern to `utils/secret_scrub.py` if the M1 scrub
list does not already cover `token=` / bearer-like values. Add a test:

Create `backend/tests/test_token_scrubbed.py`:
```python
from utils.secret_scrub import scrub


def test_dremio_token_value_is_scrubbed():
    out = scrub("connecting with token=eyJabc.def.ghi to dremio")
    assert "eyJabc.def.ghi" not in out
```

Run: `cd backend && python -m pytest tests/test_token_scrubbed.py -v`
If it fails, extend the regex list in `utils/secret_scrub.py` to redact `token=<value>`
and JWT-shaped strings, then re-run until green.

- [ ] **Step 5: Run the gate tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_prod_engine_gate.py tests/test_token_scrubbed.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/dbt_routes.py backend/utils/secret_scrub.py backend/tests/test_prod_engine_gate.py backend/tests/test_token_scrubbed.py
git commit -m "feat(engine): gate Production Engine by role + inject exchanged Dremio token"
```

---

## Task 9: Test Connection endpoint (issue 12 Dev + issue 13 Dremio-as-user)

**Files:**
- Modify: `backend/routes/connection_routes.py`
- Test: `backend/tests/test_test_connection.py`

> Test Connection runs `dbt debug --target <t>` in the user's worktree. For a Dremio
> target it exchanges the caller's token first (so the test runs AS the requesting
> User, issue 13) and is maintainer-gated; for Dev Engines it runs as-is.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_test_connection.py`:
```python
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app


def _open(client, tok):
    client.post("/api/open-project", json={"id": "p1"},
                headers={"Authorization": f"Bearer {tok}"})


def test_duckdb_connection_test_runs_dbt_debug(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, tok)

    class _R:
        success = True
        stdout = "All checks passed!"
        stderr = ""
        error = ""

    with patch("routes.connection_routes.run_command", return_value=_R()):
        r = client.post("/api/connections/test", json={"id": "p1", "target": "dev"},
                        headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_dremio_connection_test_requires_maintainer(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    dev = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, dev)
    r = client.post("/api/connections/test", json={"id": "p1", "target": "prod"},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_test_connection.py -v`
Expected: FAIL — route not found.

- [ ] **Step 3: Implement the test-connection endpoint**

Append to `backend/routes/connection_routes.py` (add imports at top):
```python
from fastapi import HTTPException
from utils.connections import is_production_engine
from utils.dremio_token import exchange_for_dremio, TokenExchangeError
from utils.dbt_utils import get_dbt_env
from utils.venv_utils import get_venv_dbt_path
from utils.subprocess_utils import run_command
from utils.secret_scrub import scrub
from fastapi import Request


@router.post("/api/connections/test")
async def test_connection(req: SetTargetRequest, request: Request,
                          user: CurrentUser = Depends(get_current_user)):
    target = validate_dbt_target(req.target)
    entry = catalog.get(req.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="project not in catalog")
    connections = entry.get("connections", {})
    engine = engine_for_target(connections, target)

    worktree = resolve_under_root(user.sub, req.id)
    env = get_dbt_env(worktree)

    if is_production_engine(engine):
        if "maintainer" not in user.roles:
            raise HTTPException(status_code=403,
                                detail="Testing the Production Engine requires the maintainer role")
        header = request.headers.get("Authorization", "")
        kc_token = header[len("Bearer "):] if header.startswith("Bearer ") else ""
        try:
            env = {**env, "DREMIO_TOKEN": exchange_for_dremio(kc_token)}
        except TokenExchangeError as e:
            raise HTTPException(status_code=502, detail=f"Dremio token exchange failed: {e}")

    dbt = get_venv_dbt_path(worktree)
    result = run_command(
        [str(dbt), "debug", "--target", target,
         "--project-dir", str(worktree), "--profiles-dir", str(worktree)],
        worktree, timeout=60, env=env,
    )
    audit(sub=user.sub, action="test_connection", target=req.id,
          extra={"target_env": target, "engine": engine, "ok": result.success})
    return {"ok": result.success, "output": scrub(result.stdout or result.error or "")}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_test_connection.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/connection_routes.py backend/tests/test_test_connection.py
git commit -m "feat(engine): Test Connection (dbt debug), Dremio runs as requesting user"
```

---

## Task 10: DuckDB end-to-end run proof (issue 11 acceptance)

**Files:**
- Test: `backend/tests/test_duckdb_e2e.py`

> Integration test that exercises the real pipeline: provision worktree → render
> DuckDB profile → install adapters → `dbt run` → results returned. Marked slow;
> requires the venv + adapters. If CI lacks dbt, skip via marker — but it MUST pass
> locally before issue 11 is declared done.

- [ ] **Step 1: Write the end-to-end test**

Create `backend/tests/test_duckdb_e2e.py`:
```python
import shutil
import pytest
from pathlib import Path
from utils.worktree import provision
from utils.profiles import write_profiles, resolve_profile_name

pytestmark = pytest.mark.skipif(shutil.which("dbt") is None and shutil.which("uv") is None,
                                reason="dbt/uv not available in this environment")


def test_dbt_run_against_duckdb(git_project, tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    wt = Path(provision(sub="user-a", project_id="p1",
                         repo_path=str(git_project), main_branch="main"))
    conn = {"dev": {"engine": "duckdb", "path": "dev.duckdb", "schema": "main"}}
    write_profiles(wt, resolve_profile_name(wt), conn, default_target="dev")

    import subprocess
    # Use a one-off venv with dbt-duckdb (mirrors _recreate_venv_sync, trimmed).
    subprocess.run(["uv", "venv", str(wt / ".dbt-ui-venv")], check=True)
    py = wt / ".dbt-ui-venv" / "bin" / "python"
    subprocess.run(["uv", "pip", "install", "dbt-core", "dbt-duckdb",
                    "--python", str(py)], check=True)
    dbt = wt / ".dbt-ui-venv" / "bin" / "dbt"
    r = subprocess.run([str(dbt), "run", "--project-dir", str(wt),
                        "--profiles-dir", str(wt), "--target", "dev"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
```

- [ ] **Step 2: Run it, verify it passes**

Run: `cd backend && python -m pytest tests/test_duckdb_e2e.py -v -s`
Expected: PASS (1 model built). If it skips, run in an env with `uv` available.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_duckdb_e2e.py
git commit -m "test(engine): DuckDB dbt run end-to-end from a provisioned worktree"
```

---

## Task 11: Frontend — Connection panel, target switcher, Test Connection

**Files:**
- Create: `frontend/src/components/dbt/ConnectionPanel.tsx`
- Modify: the dbt runner component that issues `/api/dbt-command` (target selector)
- Modify: the admin/project area to mount `ConnectionPanel`

> No frontend test infra exists in this repo — verify manually in the dev server.
> Use `apiFetch(apiUrl('/api/...'), ...)` for EVERY call (per CLAUDE.md).

- [ ] **Step 1: Build the Connection panel (admin)**

Create `frontend/src/components/dbt/ConnectionPanel.tsx`: a form, visible only when
the current user has the `admin` role, that:
- loads current config via `apiFetch(apiUrl('/api/connections/get'), { method: 'POST', body: JSON.stringify({ id: projectId }) })`
- edits per-target `{engine, host, port, path, schema, ...}` (no password/token fields — those are rejected server-side)
- saves via `/api/connections/set`
- shows server validation errors (e.g. the 400 "must not contain secrets") inline.

- [ ] **Step 2: Add a target switcher to the dbt runner**

In the dbt command component, add a target `<select>` populated from
`/api/get-profile-targets` (existing endpoint). On change, call
`/api/connections/set-target` so profiles.yml's default target is rewritten, then
pass `target` in the `/api/dbt-command` body (already supported).

- [ ] **Step 3: Add a Test Connection button**

A button per target that calls `/api/connections/test` and renders `ok` + scrubbed
`output`. Disable the prod target's button for non-maintainers (the server also
enforces 403).

- [ ] **Step 4: Manual verification**

Run: `cd frontend && npm run dev`
- As admin: set DuckDB dev + Dremio prod connections; confirm a `token`/`password`
  field is rejected with the server error.
- As developer: switch to `dev`, run dbt (DuckDB) successfully; the `prod` target
  run/test are blocked (403 surfaced).
- As maintainer: Test Connection against `prod` runs as the user (HITL, needs real
  Dremio+Keycloak — see Task 13).

- [ ] **Step 5: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: success.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/dbt/ConnectionPanel.tsx frontend/src
git commit -m "feat(engine): connection panel, target switcher, test connection UI"
```

---

## Task 12: M3 verification gate

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite green**

Run: `cd backend && python -m pytest -v`
Expected: all pass (M1 + M2 + M3).

- [ ] **Step 2: No secret can enter Connection config**

Run: `cd backend && python -m pytest tests/test_connections.py tests/test_connection_routes.py -v`
Expected: secret-key rejection tests pass.

- [ ] **Step 3: Production Engine is role-gated and identity-passed**

Run: `cd backend && python -m pytest tests/test_prod_engine_gate.py tests/test_test_connection.py -v`
Expected: developer 403 on prod; maintainer run injects an exchanged token.

- [ ] **Step 4: DuckDB pipeline proven**

Run: `cd backend && python -m pytest tests/test_duckdb_e2e.py -v -s`
Expected: PASS (model built against DuckDB).

- [ ] **Step 5: Frontend builds**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: success.

- [ ] **Step 6: Token never persisted / logged (manual grep)**

Run: `cd backend && grep -rn "DREMIO_TOKEN\|access_token\|dremio_token" --include=*.py . | grep -iv "env_var\|exchange_for_dremio\|scrub\|test"`
Expected: no line that writes the token to a file or a non-scrubbed log.

- [ ] **Step 7: HITL — real Dremio + Keycloak walk-through (issue 13)**

Configure Keycloak token-exchange (`KEYCLOAK_TOKEN_URL`, `DREMIO_AUDIENCE`,
`DREMIO_EXCHANGE_CLIENT_ID`[`/SECRET`]) and Dremio ↔ Keycloak trust. As a
maintainer: Test Connection against Dremio succeeds and Dremio's audit shows the
real person; run dbt against Dremio and confirm row/column policy reflects the
User. As a developer: the prod target is blocked. Force a job to outlive the
Dremio token and confirm it fails with a clear message (no silent retry).

- [ ] **Step 8: security-reviewer pass**

Run the security-reviewer agent over the M3 diff. Focus: the token never lands in
profiles.yml/logs/disk; the Production-Engine role gate cannot be bypassed via a
crafted `target`; Connection config stays secret-free; path authority still holds
on the new endpoints. Resolve CRITICAL/HIGH before declaring M3 done.

---

## Self-Review notes

- **Issue 11 (adapters + DuckDB run):** Task 1 (install three adapters) + Tasks 3/5 (profiles render incl. DuckDB) + Task 10 (end-to-end DuckDB run) + Task 11 (DuckDB selectable as target). ✅
- **Issue 12 (connection mgmt + test + target switch):** Task 2 (validation/no-secrets), Task 3/4 (profiles render + name), Task 6 (get/set admin + set-target), Task 9 (Test Connection for DuckDB/Spark), Task 11 (UI). ✅
- **Issue 13 (Dremio identity passthrough):** Task 7 (token-exchange seam), Task 8 (job-start exchange + injection + developer block + scrub), Task 9 (Test Connection as user, maintainer-gated), Task 12 Step 7 (HITL trust config). ✅
- **RBAC coupling (issue 08):** admin gate on `/api/connections/set` (Task 6); maintainer gate on the Production Engine at run and at Test Connection (Tasks 8, 9). Closes the "production-engine gate deferred to M3" note from the M2 self-review. ✅
- **profiles.yml ownership:** dbt-ui generates it; a user-edited file is overwritten on open/target-switch. This is intentional and keeps engine config centralised/auditable. If a project needs a hand-tuned profile, that is a follow-up, not M3.
- **M2 coupling — ALIGNED (2026-05-31):** the M2 plan was edited to match this plan's assumptions: catalog `load()` (was `list_entries`), `get(id) -> dict | None` (was `get_entry`, which raised 404; callers now raise 404 themselves), entry key `id`, persist helper `_save`, `/api/open-project` body `{id}` returning `worktree`, and `entry.get("name", ...)` so M3's name-less connection fixtures don't KeyError. The only remaining inline reconcile is whether the real `/api/dbt-command` handler already declares `request: Request` (Task 8) — add it if absent.
- **Token-exchange config is HITL** (Keycloak realm + Dremio trust). The code degrades safely: missing config → `TokenExchangeError` → 502 with a clear message, never a silent or insecure fallback.
- **Out of scope (consistent with ADR):** token refresh for jobs that outlive the Dremio token; per-user data isolation on Spark/DuckDB Dev Engines; remote engines.
