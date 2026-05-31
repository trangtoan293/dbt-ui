import pytest
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALOG_PATH", str(tmp_path / "catalog.json"))
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    from main import app
    return TestClient(app)


def test_developer_cannot_add_to_catalog(client, make_token, git_project):
    t = make_token(sub="dev1", roles=["developer"])
    r = client.post("/api/catalog/add",
                    json={"name": "Demo", "repo_path": str(git_project), "main_branch": "main"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403


def test_admin_can_add_and_anyone_can_list(client, make_token, git_project):
    admin = make_token(sub="admin1", roles=["admin"])
    r = client.post("/api/catalog/add",
                    json={"name": "Demo", "repo_path": str(git_project), "main_branch": "main"},
                    headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 200

    dev = make_token(sub="dev1", roles=["developer"])
    r2 = client.post("/api/catalog/list", headers={"Authorization": f"Bearer {dev}"})
    assert r2.status_code == 200
    assert len(r2.json()) == 1
