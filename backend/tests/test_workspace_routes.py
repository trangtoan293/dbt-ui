import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_DATA_PATH", str(tmp_path))
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "git-repos"))
    from main import app
    return TestClient(app)


def test_workspace_list_empty(client, make_token):
    t = make_token(sub="user-123", roles=["developer"])
    response = client.post(
        "/api/workspace/list",
        json={},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert response.status_code == 200
    assert response.json() == []


def test_workspace_create_success(client, make_token):
    t = make_token(sub="user-123", roles=["developer"])
    response = client.post(
        "/api/workspace/create",
        json={"name": "my-project", "adapter": "postgres"},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "my-project"
    assert data["adapter"] == "postgres"
    assert data["owner_sub"] == "user-123"


def test_workspace_create_then_list(client, make_token):
    t = make_token(sub="user-123", roles=["developer"])
    client.post(
        "/api/workspace/create",
        json={"name": "ws-a", "adapter": "postgres"},
        headers={"Authorization": f"Bearer {t}"}
    )
    client.post(
        "/api/workspace/create",
        json={"name": "ws-b", "adapter": "duckdb"},
        headers={"Authorization": f"Bearer {t}"}
    )

    response = client.post(
        "/api/workspace/list",
        json={},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_workspace_create_exceeds_limit(client, make_token, monkeypatch):
    monkeypatch.setenv("DBT_UI__MAX_WORKSPACES", "1")
    t = make_token(sub="user-123", roles=["developer"])

    r1 = client.post(
        "/api/workspace/create",
        json={"name": "ws-1", "adapter": "postgres"},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/workspace/create",
        json={"name": "ws-2", "adapter": "postgres"},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert r2.status_code == 400
    assert "Maximum" in r2.json()["detail"]


def test_workspace_delete_success(client, make_token):
    t = make_token(sub="user-123", roles=["developer"])
    create_r = client.post(
        "/api/workspace/create",
        json={"name": "to-delete", "adapter": "postgres"},
        headers={"Authorization": f"Bearer {t}"}
    )
    ws_id = create_r.json()["id"]

    response = client.post(
        "/api/workspace/delete",
        json={"id": ws_id},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert response.status_code == 200
    assert response.json() == {"deleted": ws_id}

    list_r = client.post(
        "/api/workspace/list",
        json={},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert len(list_r.json()) == 0


def test_workspace_delete_not_found(client, make_token):
    t = make_token(sub="user-123", roles=["developer"])
    response = client.post(
        "/api/workspace/delete",
        json={"id": "nonexistent"},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert response.status_code == 404


def test_workspace_open_success(client, make_token):
    t = make_token(sub="user-123", roles=["developer"])
    create_r = client.post(
        "/api/workspace/create",
        json={"name": "my-project", "adapter": "postgres"},
        headers={"Authorization": f"Bearer {t}"}
    )
    ws_id = create_r.json()["id"]

    response = client.post(
        "/api/workspace/open",
        json={"id": ws_id},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == f"workspaces/{ws_id}"
    assert data["name"] == "my-project"


def test_workspace_open_not_found(client, make_token):
    t = make_token(sub="user-123", roles=["developer"])
    response = client.post(
        "/api/workspace/open",
        json={"id": "nonexistent"},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert response.status_code == 404


def test_workspace_update_connections_success(client, make_token):
    t = make_token(sub="user-123", roles=["developer"])
    create_r = client.post(
        "/api/workspace/create",
        json={"name": "my-project", "adapter": "postgres"},
        headers={"Authorization": f"Bearer {t}"}
    )
    ws_id = create_r.json()["id"]

    connections = {
        "dev": {
            "type": "postgres",
            "host": "localhost",
            "port": 5432
        }
    }
    response = client.post(
        "/api/workspace/update-connections",
        json={"id": ws_id, "connections": connections},
        headers={"Authorization": f"Bearer {t}"}
    )
    assert response.status_code == 200
    assert response.json() == {"success": True}


def test_workspace_owner_isolation(client, make_token):
    t1 = make_token(sub="user-1", roles=["developer"])
    create_r = client.post(
        "/api/workspace/create",
        json={"name": "ws-1", "adapter": "postgres"},
        headers={"Authorization": f"Bearer {t1}"}
    )
    ws_id = create_r.json()["id"]

    t2 = make_token(sub="user-2", roles=["developer"])
    r = client.post(
        "/api/workspace/open",
        json={"id": ws_id},
        headers={"Authorization": f"Bearer {t2}"}
    )
    assert r.status_code == 404
