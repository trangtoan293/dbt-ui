import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALOG_PATH", str(tmp_path / "catalog.json"))
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    from main import app
    return TestClient(app)


def test_open_project_provisions_worktree(client, make_token, git_project):
    admin = make_token(sub="admin1", roles=["admin"])
    add = client.post("/api/catalog/add",
                      json={"name": "Demo", "repo_path": str(git_project), "main_branch": "main"},
                      headers={"Authorization": f"Bearer {admin}"})
    pid = add.json()["id"]

    dev = make_token(sub="dev1", roles=["developer"])
    r = client.post("/api/open-project", json={"id": pid},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 200
    body = r.json()
    assert body["path"] == pid
    assert Path(body["worktree"]).exists()
