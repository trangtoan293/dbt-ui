import pytest
from pathlib import Path
from utils import workspace


def test_list_workspaces_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    result = workspace.list_workspaces("user-123")
    assert result == []


def test_list_workspaces_returns_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
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


def test_get_workspace_found(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
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
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    result = workspace.get_workspace("user-123", "ws-999")
    assert result is None


def test_get_workspace_wrong_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    ws_data = {
        "id": "ws-1",
        "name": "test-ws",
        "adapter": "postgres",
        "owner_sub": "user-123",
        "path": str(tmp_path / "user-123" / "workspaces" / "ws-1"),
        "created_at": "2026-05-31T10:00:00Z"
    }
    workspace._save("user-123", [ws_data])

    result = workspace.get_workspace("user-456", "ws-1")
    assert result is None


def test_create_workspace_success(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    monkeypatch.setenv("DBT_UI__MAX_WORKSPACES", "3")

    result = workspace.create_workspace("user-123", "my-project", "postgres")

    assert result["name"] == "my-project"
    assert result["adapter"] == "postgres"
    assert result["owner_sub"] == "user-123"
    assert Path(result["path"]).exists()
    assert (Path(result["path"]) / "dbt_project.yml").exists()
    assert (Path(result["path"]) / ".git").exists()


def test_create_workspace_exceeds_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    monkeypatch.setenv("DBT_UI__MAX_WORKSPACES", "2")

    workspace.create_workspace("user-123", "ws-1", "postgres")
    workspace.create_workspace("user-123", "ws-2", "postgres")

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        workspace.create_workspace("user-123", "ws-3", "postgres")
    assert exc.value.status_code == 400
    assert "Maximum" in str(exc.value.detail)


def test_delete_workspace_success(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))

    ws = workspace.create_workspace("user-123", "test-ws", "postgres")
    ws_path = Path(ws["path"])
    assert ws_path.exists()

    workspace.delete_workspace("user-123", ws["id"])

    assert not ws_path.exists()
    assert workspace.get_workspace("user-123", ws["id"]) is None


def test_delete_workspace_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        workspace.delete_workspace("user-123", "ws-999")
    assert exc.value.status_code == 404


def test_update_connections_success(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))

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

    updated = workspace.get_workspace("user-123", ws["id"])
    assert updated["connections"] == connections

    profiles_path = Path(ws["path"]) / "profiles.yml"
    assert profiles_path.exists()
