# Personal Workspaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to create and manage their own isolated dbt projects without admin intervention.

**Architecture:** Each user gets a `workspaces/` folder under their user root. Workspaces are full dbt projects with git versioning and database connections stored in `workspaces.json`. The system enforces a max of 3 workspaces per user.

**Tech Stack:** Python (FastAPI), TypeScript (React), dbt CLI, git

---

## Task 1: Add user_data_path helper to user_paths.py

**Files:**
- Modify: `backend/utils/user_paths.py`

- [ ] **Step 1: Add user_data_path function**

```python
def user_data_path() -> Path:
    """Root directory for user-specific data (workspaces, etc.)."""
    return Path(os.environ.get("USER_DATA_PATH", str(git_repos_path() / "users"))).resolve()
```

- [ ] **Step 2: Commit**

```bash
git add backend/utils/user_paths.py
git commit -m "feat(workspace): add user_data_path helper"
```

## Task 2: Create workspace utility module

**Files:**
- Create: `backend/utils/workspace.py`
- Create: `backend/tests/test_workspace.py`

- [ ] **Step 1: Write test for list_workspaces**

```python
# backend/tests/test_workspace.py
import pytest
from pathlib import Path
from utils import workspace

def test_list_workspaces_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    result = workspace.list_workspaces("user-123")
    assert result == []

def test_list_workspaces_returns_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    # Create a workspace manually
    ws_data = {
        "id": "ws-1",
        "name": "test-ws",
        "adapter": "postgres",
        "owner_sub": "user-123",
        "path": str(tmp_path / "user-123" / "workspaces" / "ws-1"),
        "created_at": "2026-05-31T10:00:00Z"
    }
    workspace._save("user-123", [ws_data])
    
    result = workspace.list_workspaces("user-123")
    assert len(result) == 1
    assert result[0]["id"] == "ws-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace.py::test_list_workspaces_empty -v`
Expected: FAIL with "module 'workspace' not found"

- [ ] **Step 3: Implement workspace.py skeleton**

```python
# backend/utils/workspace.py
"""Personal workspace management.

Each user can create up to MAX_WORKSPACES isolated dbt projects.
Workspaces are stored under USER_DATA_PATH/<sub>/workspaces/.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import HTTPException
from utils.user_paths import user_data_path

MAX_WORKSPACES = int(os.environ.get("DBT_UI__MAX_WORKSPACES", "3"))


def _workspaces_file(sub: str) -> Path:
    return user_data_path() / sub / "workspaces.json"


def _load(sub: str) -> list:
    f = _workspaces_file(sub)
    if not f.exists():
        return []
    return json.loads(f.read_text() or "[]")


def _save(sub: str, workspaces: list) -> None:
    f = _workspaces_file(sub)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(workspaces, indent=2))


def list_workspaces(sub: str) -> list:
    """List all workspaces for a user."""
    return _load(sub)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_workspace.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write test for get_workspace**

```python
def test_get_workspace_found(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    ws_data = {
        "id": "ws-1",
        "name": "test-ws",
        "adapter": "postgres",
        "owner_sub": "user-123",
        "path": str(tmp_path / "user-123" / "workspaces" / "ws-1"),
        "created_at": "2026-05-31T10:00:00Z"
    }
    workspace._save("user-123", [ws_data])
    
    result = workspace.get_workspace("user-123", "ws-1")
    assert result is not None
    assert result["id"] == "ws-1"

def test_get_workspace_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    result = workspace.get_workspace("user-123", "ws-999")
    assert result is None

def test_get_workspace_wrong_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    ws_data = {
        "id": "ws-1",
        "name": "test-ws",
        "adapter": "postgres",
        "owner_sub": "user-123",
        "path": str(tmp_path / "user-123" / "workspaces" / "ws-1"),
        "created_at": "2026-05-31T10:00:00Z"
    }
    workspace._save("user-123", [ws_data])
    
    # Try to access with different user
    result = workspace.get_workspace("user-456", "ws-1")
    assert result is None
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace.py::test_get_workspace_found -v`
Expected: FAIL with "get_workspace not defined"

- [ ] **Step 7: Implement get_workspace**

```python
def get_workspace(sub: str, workspace_id: str) -> dict | None:
    """Get workspace by ID, verify ownership."""
    for ws in _load(sub):
        if ws["id"] == workspace_id and ws["owner_sub"] == sub:
            return ws
    return None
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_workspace.py -v`
Expected: PASS (5 tests)

- [ ] **Step 9: Write test for create_workspace**

```python
def test_create_workspace_success(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    monkeypatch.setenv("DBT_UI__MAX_WORKSPACES", "3")
    
    result = workspace.create_workspace("user-123", "my-project", "postgres")
    
    assert result["name"] == "my-project"
    assert result["adapter"] == "postgres"
    assert result["owner_sub"] == "user-123"
    assert Path(result["path"]).exists()
    assert (Path(result["path"]) / "dbt_project.yml").exists()
    assert (Path(result["path"]) / ".git").exists()

def test_create_workspace_exceeds_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    monkeypatch.setenv("DBT_UI__MAX_WORKSPACES", "2")
    
    # Create 2 workspaces
    workspace.create_workspace("user-123", "ws-1", "postgres")
    workspace.create_workspace("user-123", "ws-2", "postgres")
    
    # Try to create 3rd
    with pytest.raises(HTTPException) as exc:
        workspace.create_workspace("user-123", "ws-3", "postgres")
    assert exc.value.status_code == 400
    assert "Maximum" in str(exc.value.detail)
```

- [ ] **Step 10: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace.py::test_create_workspace_success -v`
Expected: FAIL with "create_workspace not defined"

- [ ] **Step 11: Implement create_workspace**

```python
import subprocess
import shutil

def create_workspace(sub: str, name: str, adapter: str) -> dict:
    """Create new workspace with dbt init."""
    workspaces = _load(sub)
    
    # Check limit
    if len(workspaces) >= MAX_WORKSPACES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_WORKSPACES} workspaces allowed"
        )
    
    # Generate ID and path
    workspace_id = uuid.uuid4().hex[:8]
    ws_path = user_data_path() / sub / "workspaces" / workspace_id
    ws_path.mkdir(parents=True, exist_ok=True)
    
    # Run dbt init
    result = subprocess.run(
        ["dbt", "init", name, "--adapter", adapter, "--skip-profile-setup"],
        cwd=str(ws_path),
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        shutil.rmtree(ws_path, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail=f"dbt init failed: {result.stderr}"
        )
    
    # Git init and initial commit
    subprocess.run(["git", "init"], cwd=str(ws_path), check=True)
    subprocess.run(["git", "add", "."], cwd=str(ws_path), check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial dbt project"],
        cwd=str(ws_path),
        check=True
    )
    
    # Save metadata
    ws_data = {
        "id": workspace_id,
        "name": name,
        "adapter": adapter,
        "owner_sub": sub,
        "path": str(ws_path),
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    workspaces.append(ws_data)
    _save(sub, workspaces)
    
    return ws_data
```

- [ ] **Step 12: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_workspace.py -v`
Expected: PASS (7 tests)

- [ ] **Step 13: Write test for delete_workspace**

```python
def test_delete_workspace_success(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    
    ws = workspace.create_workspace("user-123", "test-ws", "postgres")
    ws_path = Path(ws["path"])
    assert ws_path.exists()
    
    workspace.delete_workspace("user-123", ws["id"])
    
    assert not ws_path.exists()
    assert workspace.get_workspace("user-123", ws["id"]) is None

def test_delete_workspace_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    
    with pytest.raises(HTTPException) as exc:
        workspace.delete_workspace("user-123", "ws-999")
    assert exc.value.status_code == 404
```

- [ ] **Step 14: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace.py::test_delete_workspace_success -v`
Expected: FAIL with "delete_workspace not defined"

- [ ] **Step 15: Implement delete_workspace**

```python
def delete_workspace(sub: str, workspace_id: str) -> None:
    """Delete workspace and remove from metadata."""
    ws = get_workspace(sub, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Remove folder
    ws_path = Path(ws["path"])
    if ws_path.exists():
        shutil.rmtree(ws_path)
    
    # Remove from metadata
    workspaces = [w for w in _load(sub) if w["id"] != workspace_id]
    _save(sub, workspaces)
```

- [ ] **Step 16: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_workspace.py -v`
Expected: PASS (9 tests)

- [ ] **Step 17: Write test for update_connections**

```python
def test_update_connections_success(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    
    ws = workspace.create_workspace("user-123", "test-ws", "postgres")
    
    connections = {
        "dev": {
            "type": "postgres",
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "schema": "public"
        }
    }
    
    workspace.update_connections("user-123", ws["id"], connections)
    
    # Verify saved
    updated = workspace.get_workspace("user-123", ws["id"])
    assert updated["connections"] == connections
    
    # Verify profiles.yml written
    profiles_path = Path(ws["path"]) / "profiles.yml"
    assert profiles_path.exists()
```

- [ ] **Step 18: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace.py::test_update_connections_success -v`
Expected: FAIL with "update_connections not defined"

- [ ] **Step 19: Implement update_connections**

```python
from utils.profiles import write_profiles

def update_connections(sub: str, workspace_id: str, connections: dict) -> None:
    """Update workspace connections and write profiles.yml."""
    ws = get_workspace(sub, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Update metadata
    workspaces = _load(sub)
    for w in workspaces:
        if w["id"] == workspace_id:
            w["connections"] = connections
            break
    _save(sub, workspaces)
    
    # Write profiles.yml
    ws_path = Path(ws["path"])
    profile_name = ws["name"].replace("-", "_").replace(" ", "_")
    write_profiles(ws_path, profile_name, connections)
```

- [ ] **Step 20: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_workspace.py -v`
Expected: PASS (10 tests)

- [ ] **Step 21: Commit**

```bash
git add backend/utils/workspace.py backend/tests/test_workspace.py
git commit -m "feat(workspace): implement workspace CRUD operations"
```

## Task 3: Create workspace API routes

**Files:**
- Create: `backend/routes/workspace_routes.py`
- Create: `backend/tests/test_workspace_routes.py`

- [ ] **Step 1: Write test for workspace list endpoint**

```python
# backend/tests/test_workspace_routes.py
import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch

@pytest.fixture
def client():
    return TestClient(app)

def test_workspace_list_empty(client):
    with patch("routes.workspace_routes.workspace.list_workspaces") as mock:
        mock.return_value = []
        
        response = client.post(
            "/api/workspace/list",
            json={},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace_routes.py::test_workspace_list_empty -v`
Expected: FAIL with "module 'workspace_routes' not found"

- [ ] **Step 3: Implement workspace_routes.py skeleton**

```python
# backend/routes/workspace_routes.py
"""Workspace API routes."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from auth import get_current_user, CurrentUser
from utils import workspace

router = APIRouter()


class CreateWorkspaceRequest(BaseModel):
    name: str
    adapter: str


class WorkspaceIdRequest(BaseModel):
    id: str


class UpdateConnectionsRequest(BaseModel):
    id: str
    connections: dict


@router.post("/api/workspace/list")
async def workspace_list(user: CurrentUser = Depends(get_current_user)):
    return workspace.list_workspaces(user.sub)
```

- [ ] **Step 4: Register router in main.py**

```python
# backend/main.py (add to imports)
from routes import workspace_routes

# backend/main.py (add to app.include_router calls)
app.include_router(workspace_routes.router, dependencies=auth_dependency)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_workspace_routes.py::test_workspace_list_empty -v`
Expected: PASS

- [ ] **Step 6: Write test for workspace create endpoint**

```python
def test_workspace_create_success(client):
    with patch("routes.workspace_routes.workspace.create_workspace") as mock:
        mock.return_value = {
            "id": "ws-1",
            "name": "my-project",
            "adapter": "postgres",
            "owner_sub": "user-123",
            "path": "/path/to/ws",
            "created_at": "2026-05-31T10:00:00Z"
        }
        
        response = client.post(
            "/api/workspace/create",
            json={"name": "my-project", "adapter": "postgres"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "my-project"
        assert data["adapter"] == "postgres"
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace_routes.py::test_workspace_create_success -v`
Expected: FAIL with "404 Not Found" (endpoint doesn't exist)

- [ ] **Step 8: Implement workspace create endpoint**

```python
@router.post("/api/workspace/create")
async def workspace_create(
    req: CreateWorkspaceRequest,
    user: CurrentUser = Depends(get_current_user)
):
    ws = workspace.create_workspace(user.sub, req.name, req.adapter)
    return ws
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd backend && pytest tests/test_workspace_routes.py::test_workspace_create_success -v`
Expected: PASS

- [ ] **Step 10: Write test for workspace delete endpoint**

```python
def test_workspace_delete_success(client):
    with patch("routes.workspace_routes.workspace.delete_workspace") as mock:
        mock.return_value = None
        
        response = client.post(
            "/api/workspace/delete",
            json={"id": "ws-1"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json() == {"deleted": "ws-1"}
```

- [ ] **Step 11: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace_routes.py::test_workspace_delete_success -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 12: Implement workspace delete endpoint**

```python
@router.post("/api/workspace/delete")
async def workspace_delete(
    req: WorkspaceIdRequest,
    user: CurrentUser = Depends(get_current_user)
):
    workspace.delete_workspace(user.sub, req.id)
    return {"deleted": req.id}
```

- [ ] **Step 13: Run test to verify it passes**

Run: `cd backend && pytest tests/test_workspace_routes.py::test_workspace_delete_success -v`
Expected: PASS

- [ ] **Step 14: Write test for workspace open endpoint**

```python
def test_workspace_open_success(client):
    with patch("routes.workspace_routes.workspace.get_workspace") as mock:
        mock.return_value = {
            "id": "ws-1",
            "name": "my-project",
            "adapter": "postgres",
            "owner_sub": "user-123",
            "path": "/home/dbtui/users/user-123/workspaces/ws-1",
            "created_at": "2026-05-31T10:00:00Z"
        }
        
        response = client.post(
            "/api/workspace/open",
            json={"id": "ws-1"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "workspaces/ws-1"
        assert data["name"] == "my-project"
```

- [ ] **Step 15: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace_routes.py::test_workspace_open_success -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 16: Implement workspace open endpoint**

```python
@router.post("/api/workspace/open")
async def workspace_open(
    req: WorkspaceIdRequest,
    user: CurrentUser = Depends(get_current_user)
):
    ws = workspace.get_workspace(user.sub, req.id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Return relative path for resolve_under_root compatibility
    relative_path = f"workspaces/{ws['id']}"
    return {
        "path": relative_path,
        "name": ws["name"]
    }
```

- [ ] **Step 17: Run test to verify it passes**

Run: `cd backend && pytest tests/test_workspace_routes.py::test_workspace_open_success -v`
Expected: PASS

- [ ] **Step 18: Write test for workspace update connections endpoint**

```python
def test_workspace_update_connections_success(client):
    with patch("routes.workspace_routes.workspace.update_connections") as mock:
        mock.return_value = None
        
        connections = {
            "dev": {
                "type": "postgres",
                "host": "localhost",
                "port": 5432
            }
        }
        
        response = client.post(
            "/api/workspace/update-connections",
            json={"id": "ws-1", "connections": connections},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        assert response.json() == {"success": True}
```

- [ ] **Step 19: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace_routes.py::test_workspace_update_connections_success -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 20: Implement workspace update connections endpoint**

```python
@router.post("/api/workspace/update-connections")
async def workspace_update_connections(
    req: UpdateConnectionsRequest,
    user: CurrentUser = Depends(get_current_user)
):
    workspace.update_connections(user.sub, req.id, req.connections)
    return {"success": True}
```

- [ ] **Step 21: Run all tests to verify they pass**

Run: `cd backend && pytest tests/test_workspace_routes.py -v`
Expected: PASS (5 tests)

- [ ] **Step 22: Commit**

```bash
git add backend/routes/workspace_routes.py backend/tests/test_workspace_routes.py backend/main.py
git commit -m "feat(workspace): add workspace API endpoints"
```

## Task 4: Extend engine_gate to support workspaces

**Files:**
- Modify: `backend/routes/dbt_routes.py:34-75`
- Create: `backend/tests/test_engine_gate_workspace.py`

- [ ] **Step 1: Write test for engine_gate with workspace**

```python
# backend/tests/test_engine_gate_workspace.py
import pytest
from unittest.mock import patch, MagicMock
from routes.dbt_routes import _engine_gate

def test_engine_gate_workspace_with_connections():
    user = MagicMock()
    user.sub = "user-123"
    user.roles = ["developer"]
    
    request = MagicMock()
    request.headers.get.return_value = "Bearer test-token"
    
    with patch("routes.dbt_routes.catalog.get") as catalog_mock, \
         patch("routes.dbt_routes.workspace.get_workspace") as ws_mock:
        
        catalog_mock.return_value = None  # Not in catalog
        
        ws_mock.return_value = {
            "id": "ws-1",
            "connections": {
                "dev": {
                    "type": "postgres",
                    "host": "localhost"
                }
            }
        }
        
        result = _engine_gate(
            user, request, "ws-1", "/path/to/ws",
            "dev", {}
        )
        
        # Should not raise, should return env_vars
        assert result == {}

def test_engine_gate_workspace_no_connections():
    user = MagicMock()
    user.sub = "user-123"
    user.roles = ["developer"]
    
    request = MagicMock()
    request.headers.get.return_value = "Bearer test-token"
    
    with patch("routes.dbt_routes.catalog.get") as catalog_mock, \
         patch("routes.dbt_routes.workspace.get_workspace") as ws_mock:
        
        catalog_mock.return_value = None
        ws_mock.return_value = {"id": "ws-1", "connections": {}}
        
        result = _engine_gate(
            user, request, "ws-1", "/path/to/ws",
            "dev", {}
        )
        
        assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_engine_gate_workspace.py::test_engine_gate_workspace_with_connections -v`
Expected: FAIL (workspace not imported in dbt_routes)

- [ ] **Step 3: Modify _engine_gate to support workspaces**

```python
# backend/routes/dbt_routes.py (modify _engine_gate function)
def _engine_gate(user, request, project_id: str, worktree, explicit_target: str, env_vars: dict) -> dict:
    """If the effective target's engine is the Production Engine (Dremio): require
    the maintainer role and inject a freshly-exchanged Dremio token into env_vars.
    Dev Engines pass through untouched. Returns the (possibly augmented) env_vars.
    Raises HTTPException(403) on a non-maintainer; (502) on exchange failure."""
    
    # Try catalog first
    entry = catalog.get(project_id)
    
    # If not in catalog, try workspace
    if not entry:
        from utils import workspace
        ws = workspace.get_workspace(user.sub, project_id)
        if ws:
            connections = ws.get("connections", {})
        else:
            connections = {}
    else:
        connections = entry.get("connections", {})
    
    if not connections:
        return env_vars or {}

    # Effective target: explicit arg wins; else the profile's default target.
    target = explicit_target
    if not target:
        try:
            target = read_default_target(worktree, resolve_profile_name(worktree))
        except Exception:
            target = None
    if not target:
        return env_vars or {}

    try:
        engine = engine_for_target(connections, target)
    except HTTPException:
        return env_vars or {}

    if not is_production_engine(engine):
        return env_vars or {}

    if "maintainer" not in user.roles:
        _audit(sub=user.sub, action="prod_run_denied", target=project_id,
               extra={"target_env": target, "engine": engine})
        raise HTTPException(status_code=403,
                            detail="Production Engine requires the maintainer role")

    # Exchange the still-valid Keycloak token NOW (the job outlives it; ADR §6).
    header = request.headers.get("Authorization", "")
    kc_token = header[len("Bearer "):] if header.startswith("Bearer ") else ""
    try:
        dremio_token = exchange_for_dremio(kc_token)
    except TokenExchangeError as e:
        raise HTTPException(status_code=502, detail=f"Dremio token exchange failed: {e}")
    return {**(env_vars or {}), "DREMIO_TOKEN": dremio_token}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_engine_gate_workspace.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/routes/dbt_routes.py backend/tests/test_engine_gate_workspace.py
git commit -m "feat(workspace): extend engine_gate to support workspace connections"
```

## Task 5: Add frontend workspace API functions

**Files:**
- Modify: `frontend/src/config/api.ts`

- [ ] **Step 1: Add workspace API functions**

```typescript
// frontend/src/config/api.ts (add to end)

export interface Workspace {
  id: string
  name: string
  adapter: string
  created_at: string
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const r = await apiFetch(apiUrl('/api/workspace/list'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!r.ok) throw new Error('Failed to list workspaces')
  return r.json()
}

export async function createWorkspace(name: string, adapter: string): Promise<Workspace> {
  const r = await apiFetch(apiUrl('/api/workspace/create'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, adapter }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw new Error(data.detail || 'Failed to create workspace')
  }
  return r.json()
}

export async function deleteWorkspace(id: string): Promise<void> {
  const r = await apiFetch(apiUrl('/api/workspace/delete'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  })
  if (!r.ok) throw new Error('Failed to delete workspace')
}

export async function openWorkspace(id: string): Promise<{ path: string, name: string }> {
  const r = await apiFetch(apiUrl('/api/workspace/open'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  })
  if (!r.ok) throw new Error('Failed to open workspace')
  return r.json()
}

export async function updateWorkspaceConnections(
  id: string,
  connections: any
): Promise<void> {
  const r = await apiFetch(apiUrl('/api/workspace/update-connections'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, connections }),
  })
  if (!r.ok) throw new Error('Failed to update connections')
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/config/api.ts
git commit -m "feat(workspace): add workspace API functions to frontend"
```

## Task 6: Create ProjectDialog with tabs

**Files:**
- Rename: `frontend/src/components/main/ProjectCatalogDialog.tsx` → `ProjectDialog.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Rename ProjectCatalogDialog to ProjectDialog**

```bash
cd frontend/src/components/main
mv ProjectCatalogDialog.tsx ProjectDialog.tsx
```

- [ ] **Step 2: Update ProjectDialog to add tabs**

```tsx
// frontend/src/components/main/ProjectDialog.tsx (replace entire file)
import { useState, useEffect } from 'react'
import { apiUrl, apiFetch, listWorkspaces, openWorkspace, Workspace } from '../../config/api'
import CreateWorkspaceModal from './CreateWorkspaceModal'
import './ProjectPathDialog.css'

interface CatalogEntry {
  id: string
  name: string
  repo_path: string
  main_branch: string
}

interface CurrentUser {
  sub: string
  email: string
  roles: string[]
}

interface ProjectDialogProps {
  onOpen: (projectId: string, projectName: string) => void
}

export default function ProjectDialog({ onOpen }: ProjectDialogProps) {
  const [activeTab, setActiveTab] = useState<'workspaces' | 'catalog'>('workspaces')
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [catalogEntries, setCatalogEntries] = useState<CatalogEntry[]>([])
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)

  const isAdmin = user?.roles.includes('admin') ?? false

  useEffect(() => {
    loadUser()
    loadWorkspaces()
    loadCatalog()
  }, [])

  const loadUser = async () => {
    try {
      const r = await apiFetch(apiUrl('/api/me'), { method: 'GET' })
      if (r.ok) setUser(await r.json())
    } catch {}
  }

  const loadWorkspaces = async () => {
    try {
      const ws = await listWorkspaces()
      setWorkspaces(ws)
    } catch (e: any) {
      setError('Failed to load workspaces')
    }
  }

  const loadCatalog = async () => {
    try {
      const r = await apiFetch(apiUrl('/api/catalog/list'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (r.ok) setCatalogEntries(await r.json())
    } catch (e) {
      setError('Failed to load catalog')
    }
  }

  const handleOpenWorkspace = async (ws: Workspace) => {
    setLoading(true)
    setError('')
    try {
      const result = await openWorkspace(ws.id)
      onOpen(result.path, result.name)
    } catch (e: any) {
      setError(e.message || 'Failed to open workspace')
    } finally {
      setLoading(false)
    }
  }

  const handleOpenCatalog = async (entry: CatalogEntry) => {
    setLoading(true)
    setError('')
    try {
      const r = await apiFetch(apiUrl('/api/open-project'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: entry.id }),
      })
      if (!r.ok) {
        const data = await r.json().catch(() => ({}))
        setError(data.detail || 'Failed to open project')
        return
      }
      const data = await r.json()
      onOpen(data.path, entry.name)
    } catch (e) {
      setError('Failed to open project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="project-path-dialog">
      <div className="project-path-dialog-content">
        <h2>Open Project</h2>

        {error && <div className="error-message">{error}</div>}

        <div className="tabs">
          <button
            className={activeTab === 'workspaces' ? 'active' : ''}
            onClick={() => setActiveTab('workspaces')}
          >
            My Workspaces
          </button>
          <button
            className={activeTab === 'catalog' ? 'active' : ''}
            onClick={() => setActiveTab('catalog')}
          >
            Shared Projects
          </button>
        </div>

        {activeTab === 'workspaces' && (
          <div>
            {workspaces.length === 0 ? (
              <p className="no-projects">No workspaces yet. Create one below.</p>
            ) : (
              <ul className="catalog-list">
                {workspaces.map((ws) => (
                  <li key={ws.id} className="catalog-item">
                    <div className="catalog-item-info">
                      <strong>{ws.name}</strong>
                      <span className="catalog-item-branch">{ws.adapter}</span>
                    </div>
                    <div className="catalog-item-actions">
                      <button
                        className="btn-primary"
                        onClick={() => handleOpenWorkspace(ws)}
                        disabled={loading}
                      >
                        Open
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <button
              className="btn-primary"
              onClick={() => setShowCreateModal(true)}
            >
              Create Workspace
            </button>
          </div>
        )}

        {activeTab === 'catalog' && (
          <div>
            {catalogEntries.length === 0 ? (
              <p className="no-projects">
                No projects in catalog.{isAdmin ? ' Add one via admin panel.' : ' Ask an admin to add a project.'}
              </p>
            ) : (
              <ul className="catalog-list">
                {catalogEntries.map((entry) => (
                  <li key={entry.id} className="catalog-item">
                    <div className="catalog-item-info">
                      <strong>{entry.name}</strong>
                      <span className="catalog-item-branch">{entry.main_branch}</span>
                    </div>
                    <div className="catalog-item-actions">
                      <button
                        className="btn-primary"
                        onClick={() => handleOpenCatalog(entry)}
                        disabled={loading}
                      >
                        Open
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {showCreateModal && (
          <CreateWorkspaceModal
            onClose={() => setShowCreateModal(false)}
            onCreated={() => {
              loadWorkspaces()
              setShowCreateModal(false)
            }}
          />
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Update App.tsx to use ProjectDialog**

```tsx
// frontend/src/App.tsx (change import)
import ProjectDialog from './components/main/ProjectDialog'

// frontend/src/App.tsx (change usage)
<ProjectDialog onOpen={handleProjectOpen} />
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/main/ProjectDialog.tsx frontend/src/App.tsx
git commit -m "feat(workspace): create ProjectDialog with workspaces and catalog tabs"
```

## Task 7: Create CreateWorkspaceModal component

**Files:**
- Create: `frontend/src/components/main/CreateWorkspaceModal.tsx`

- [ ] **Step 1: Implement CreateWorkspaceModal**

```tsx
// frontend/src/components/main/CreateWorkspaceModal.tsx
import { useState } from 'react'
import { createWorkspace } from '../../config/api'
import './ProjectPathDialog.css'

interface CreateWorkspaceModalProps {
  onClose: () => void
  onCreated: () => void
}

export default function CreateWorkspaceModal({ onClose, onCreated }: CreateWorkspaceModalProps) {
  const [name, setName] = useState('')
  const [adapter, setAdapter] = useState('postgres')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const handleCreate = async () => {
    if (!name.trim()) return
    
    setCreating(true)
    setError('')
    try {
      await createWorkspace(name.trim(), adapter)
      onCreated()
    } catch (e: any) {
      setError(e.message || 'Failed to create workspace')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3>Create Workspace</h3>
        
        {error && <div className="error-message">{error}</div>}
        
        <div className="form-group">
          <label>Workspace name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-analytics"
            disabled={creating}
          />
        </div>
        
        <div className="form-group">
          <label>Adapter</label>
          <select
            value={adapter}
            onChange={(e) => setAdapter(e.target.value)}
            disabled={creating}
          >
            <option value="postgres">PostgreSQL</option>
            <option value="dremio">Dremio</option>
            <option value="duckdb">DuckDB</option>
            <option value="spark">Spark</option>
          </select>
        </div>
        
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose} disabled={creating}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleCreate}
            disabled={creating || !name.trim()}
          >
            {creating ? 'Creating...' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/main/CreateWorkspaceModal.tsx
git commit -m "feat(workspace): add CreateWorkspaceModal component"
```

## Task 8: Create WorkspaceSettingsModal component

**Files:**
- Create: `frontend/src/components/main/WorkspaceSettingsModal.tsx`
- Modify: `frontend/src/components/main/MainLayout.tsx` (add settings button)

- [ ] **Step 1: Implement WorkspaceSettingsModal**

```tsx
// frontend/src/components/main/WorkspaceSettingsModal.tsx
import { useState } from 'react'
import { updateWorkspaceConnections } from '../../config/api'
import './ProjectPathDialog.css'

interface WorkspaceSettingsModalProps {
  workspaceId: string
  workspaceName: string
  connections: any
  onClose: () => void
  onUpdated: () => void
}

export default function WorkspaceSettingsModal({
  workspaceId,
  workspaceName,
  connections: initialConnections,
  onClose,
  onUpdated
}: WorkspaceSettingsModalProps) {
  const [connections, setConnections] = useState(initialConnections || {})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      await updateWorkspaceConnections(workspaceId, connections)
      onUpdated()
    } catch (e: any) {
      setError(e.message || 'Failed to update connections')
    } finally {
      setSaving(false)
    }
  }

  const updateConnection = (target: string, field: string, value: any) => {
    setConnections((prev: any) => ({
      ...prev,
      [target]: {
        ...(prev[target] || {}),
        [field]: value
      }
    }))
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3>Workspace Settings: {workspaceName}</h3>
        
        {error && <div className="error-message">{error}</div>}
        
        <h4>Dev Connection</h4>
        
        <div className="form-group">
          <label>Type</label>
          <input
            type="text"
            value={connections.dev?.type || ''}
            onChange={(e) => updateConnection('dev', 'type', e.target.value)}
            placeholder="postgres"
            disabled={saving}
          />
        </div>
        
        <div className="form-group">
          <label>Host</label>
          <input
            type="text"
            value={connections.dev?.host || ''}
            onChange={(e) => updateConnection('dev', 'host', e.target.value)}
            placeholder="localhost"
            disabled={saving}
          />
        </div>
        
        <div className="form-group">
          <label>Port</label>
          <input
            type="number"
            value={connections.dev?.port || ''}
            onChange={(e) => updateConnection('dev', 'port', parseInt(e.target.value))}
            placeholder="5432"
            disabled={saving}
          />
        </div>
        
        <div className="form-group">
          <label>Database</label>
          <input
            type="text"
            value={connections.dev?.database || ''}
            onChange={(e) => updateConnection('dev', 'database', e.target.value)}
            placeholder="mydb"
            disabled={saving}
          />
        </div>
        
        <div className="form-group">
          <label>Schema</label>
          <input
            type="text"
            value={connections.dev?.schema || ''}
            onChange={(e) => updateConnection('dev', 'schema', e.target.value)}
            placeholder="public"
            disabled={saving}
          />
        </div>
        
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add settings button to MainLayout**

```tsx
// frontend/src/components/main/MainLayout.tsx (add import)
import WorkspaceSettingsModal from './WorkspaceSettingsModal'

// frontend/src/components/main/MainLayout.tsx (add state)
const [showSettingsModal, setShowSettingsModal] = useState(false)
const [currentWorkspaceId, setCurrentWorkspaceId] = useState<string | null>(null)

// frontend/src/components/main/MainLayout.tsx (add button in sidebar)
{currentWorkspaceId && (
  <button
    className="btn-secondary"
    onClick={() => setShowSettingsModal(true)}
  >
    Settings
  </button>
)}

// frontend/src/components/main/MainLayout.tsx (add modal)
{showSettingsModal && currentWorkspaceId && (
  <WorkspaceSettingsModal
    workspaceId={currentWorkspaceId}
    workspaceName={projectName}
    connections={{}}
    onClose={() => setShowSettingsModal(false)}
    onUpdated={() => {
      setShowSettingsModal(false)
      // Reload project data
    }}
  />
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/main/WorkspaceSettingsModal.tsx frontend/src/components/main/MainLayout.tsx
git commit -m "feat(workspace): add WorkspaceSettingsModal for connection config"
```

## Task 9: Integration testing

**Files:**
- None (manual testing)

- [ ] **Step 1: Start backend and frontend**

```bash
cd backend && uvicorn main:app --reload &
cd frontend && npm run dev &
```

- [ ] **Step 2: Test workspace creation flow**

1. Open browser to http://localhost:5173
2. Click "Create Workspace"
3. Enter name: "test-workspace", adapter: "postgres"
4. Click "Create"
5. Verify workspace appears in list
6. Check backend logs for dbt init success
7. Verify folder created: `USER_DATA_PATH/<sub>/workspaces/<id>/`

- [ ] **Step 3: Test workspace open flow**

1. Click "Open" on the workspace
2. Verify editor loads with dbt project files
3. Verify file tree shows dbt structure (models/, dbt_project.yml, etc.)

- [ ] **Step 4: Test file operations**

1. Create a new file in models/
2. Edit the file
3. Save the file
4. Verify changes persist

- [ ] **Step 5: Test git operations**

1. Stage the new file
2. Commit with message "Add model"
3. Verify commit appears in git log

- [ ] **Step 6: Test workspace deletion**

1. Create a second workspace
2. Delete it
3. Verify it's removed from list
4. Verify folder is deleted

- [ ] **Step 7: Test workspace limit**

1. Create 3 workspaces (max)
2. Try to create 4th
3. Verify error message: "Maximum 3 workspaces allowed"

- [ ] **Step 8: Test connection config**

1. Open workspace
2. Click "Settings"
3. Fill connection details
4. Click "Save"
5. Verify profiles.yml is written to workspace folder
6. Run `dbt debug` to verify connection works

- [ ] **Step 9: Commit any fixes**

```bash
git add -A
git commit -m "fix(workspace): integration test fixes"
```

---

## Summary

This plan implements Personal Workspaces in 9 tasks:

1. **Backend foundation** (Tasks 1-4): workspace utils, API routes, engine_gate extension
2. **Frontend UI** (Tasks 5-8): API functions, ProjectDialog, CreateWorkspaceModal, WorkspaceSettingsModal
3. **Integration testing** (Task 9): end-to-end verification

Each task is self-contained with TDD approach. Total estimated time: 4-6 hours for experienced developer.
