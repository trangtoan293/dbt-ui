"""Personal workspace management.

Each user can create up to _max_workspaces() isolated dbt projects.
Workspaces are stored under the user's own root: user_root(<sub>)/workspaces/.
This is the same root the file/dbt/git routes resolve against, so a workspace
opened with the relative path "workspaces/<id>" reaches the same directory.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import yaml
from fastapi import HTTPException
from utils.user_paths import user_root


def _max_workspaces() -> int:
    return int(os.environ.get("DBT_UI__MAX_WORKSPACES", "3"))


def _workspaces_file(sub: str) -> Path:
    return user_root(sub) / "workspaces.json"


def _load(sub: str) -> list:
    f = _workspaces_file(sub)
    if not f.exists():
        return []
    return json.loads(f.read_text() or "[]")


def _save(sub: str, workspaces: list) -> None:
    f = _workspaces_file(sub)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(workspaces, indent=2))


_PUBLIC_FIELDS = ("id", "name", "adapter", "created_at")


def _public_view(ws: dict) -> dict:
    """Strip secrets (connections, owner_sub, absolute path) before sending to client."""
    return {k: ws.get(k) for k in _PUBLIC_FIELDS}


def list_workspaces(sub: str) -> list:
    """List all workspaces for a user, without connection secrets."""
    return [_public_view(ws) for ws in _load(sub)]


def get_workspace(sub: str, workspace_id: str) -> dict | None:
    """Get workspace by ID, verify ownership."""
    for ws in _load(sub):
        if ws["id"] == workspace_id and ws["owner_sub"] == sub:
            return ws
    return None


def create_workspace(sub: str, name: str, adapter: str) -> dict:
    """Create new workspace with dbt init."""
    workspaces = _load(sub)

    max_ws = _max_workspaces()
    if len(workspaces) >= max_ws:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_ws} workspaces allowed"
        )

    workspace_id = uuid.uuid4().hex[:8]
    ws_path = user_root(sub) / "workspaces" / workspace_id
    ws_path.mkdir(parents=True, exist_ok=True)

    safe_name = name.replace("-", "_").replace(" ", "_")
    dbt_project_yaml = {
        "name": safe_name,
        "version": "1.0.0",
        "profile": safe_name,
    }
    (ws_path / "dbt_project.yml").write_text(yaml.safe_dump(dbt_project_yaml, sort_keys=False))
    (ws_path / "models").mkdir(exist_ok=True)

    subprocess.run(["git", "init"], cwd=str(ws_path), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(ws_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial dbt project"],
        cwd=str(ws_path),
        capture_output=True
    )

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


def delete_workspace(sub: str, workspace_id: str) -> None:
    """Delete workspace and remove from metadata."""
    ws = get_workspace(sub, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ws_path = Path(ws["path"])
    if ws_path.exists():
        shutil.rmtree(ws_path)

    workspaces = [w for w in _load(sub) if w["id"] != workspace_id]
    _save(sub, workspaces)


def _write_workspace_profiles(ws_path: Path, profile_name: str, connections: dict) -> None:
    """Write profiles.yml for a workspace using raw connection configs."""
    outputs = {}
    for target, cfg in connections.items():
        outputs[target] = dict(cfg)
    profile = {
        profile_name: {
            "target": next(iter(connections)),
            "outputs": outputs,
        }
    }
    (ws_path / "profiles.yml").write_text(yaml.safe_dump(profile, sort_keys=False))


def update_connections(sub: str, workspace_id: str, connections: dict) -> None:
    """Update workspace connections and write profiles.yml."""
    ws = get_workspace(sub, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not connections:
        raise HTTPException(status_code=400, detail="At least one connection required")

    workspaces = _load(sub)
    for w in workspaces:
        if w["id"] == workspace_id:
            w["connections"] = connections
            break
    _save(sub, workspaces)

    ws_path = Path(ws["path"])
    profile_name = ws["name"].replace("-", "_").replace(" ", "_")
    _write_workspace_profiles(ws_path, profile_name, connections)
