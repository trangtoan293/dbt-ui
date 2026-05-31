import subprocess
import pytest
from fastapi.testclient import TestClient
import auth as auth_mod
from utils.worktree import provision


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    from main import app
    return TestClient(app)


def test_commit_uses_keycloak_identity(client, make_token, git_project, tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    wt = provision(sub="dev1", project_id="p1", repo_path=str(git_project), main_branch="main")
    (import_pathlib := __import__("pathlib").Path(wt) / "models" / "new.sql").write_text("select 2\n")

    t = make_token(sub="dev1", email="dev1@corp.io", roles=["developer"])
    headers = {"Authorization": f"Bearer {t}"}
    client.post("/api/git-stage", json={"path": "p1", "files": ["models/new.sql"]}, headers=headers)
    r = client.post("/api/git-commit",
                    json={"path": "p1", "message": "add model",
                          "user_name": "ignored", "user_email": "ignored@ignored.com"},
                    headers=headers)
    assert r.status_code == 200

    log = subprocess.run(["git", "-C", wt, "log", "-1", "--format=%an <%ae>"],
                         capture_output=True, text=True)
    assert "dev1@corp.io" in log.stdout
