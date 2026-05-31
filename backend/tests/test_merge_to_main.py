import subprocess
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import auth as auth_mod
from utils.worktree import provision


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALOG_PATH", str(tmp_path / "catalog.json"))
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    from main import app
    return TestClient(app)


def _setup_project_with_commit(client, make_token, git_project):
    admin = make_token(sub="admin1", roles=["admin"])
    pid = client.post("/api/catalog/add",
                      json={"name": "Demo", "repo_path": str(git_project), "main_branch": "main"},
                      headers={"Authorization": f"Bearer {admin}"}).json()["id"]
    t = make_token(sub="maint1", email="m@corp.io", roles=["maintainer"])
    h = {"Authorization": f"Bearer {t}"}
    wt = client.post("/api/open-project", json={"id": pid}, headers=h).json()["worktree"]
    (Path(wt) / "models" / "new.sql").write_text("select 42\n")
    client.post("/api/git-stage", json={"path": pid, "files": ["models/new.sql"]}, headers=h)
    client.post("/api/git-commit", json={"path": pid, "message": "add new"}, headers=h)
    return pid, t


def test_developer_cannot_merge(client, make_token, git_project):
    pid, _ = _setup_project_with_commit(client, make_token, git_project)
    dev = make_token(sub="dev1", roles=["developer"])
    r = client.post("/api/merge-to-main", json={"id": pid},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 403


def test_maintainer_merges_clean(client, make_token, git_project):
    pid, maint = _setup_project_with_commit(client, make_token, git_project)
    r = client.post("/api/merge-to-main", json={"id": pid},
                    headers={"Authorization": f"Bearer {maint}"})
    assert r.status_code == 200
    assert r.json()["merged"] is True

    log = subprocess.run(["git", "-C", str(git_project), "log", "main", "--oneline"],
                         capture_output=True, text=True)
    assert "add new" in log.stdout


def test_diff_shows_changes(client, make_token, git_project):
    pid, maint = _setup_project_with_commit(client, make_token, git_project)
    r = client.post("/api/project-diff", json={"id": pid},
                    headers={"Authorization": f"Bearer {maint}"})
    assert r.status_code == 200
    assert "new.sql" in r.json()["diff"]
