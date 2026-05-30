import pytest
from fastapi.testclient import TestClient
import auth as auth_mod
from tests.conftest import TEST_ISSUER, TEST_AUDIENCE


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())
    monkeypatch.setattr(auth_mod, "ISSUER", TEST_ISSUER)
    monkeypatch.setattr(auth_mod, "AUDIENCE", TEST_AUDIENCE)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    # user-a owns a dbt project; user-b must not reach it
    proj = tmp_path / "user-a" / "proj"
    proj.mkdir(parents=True)
    (proj / "dbt_project.yml").write_text("name: demo\n")
    from main import app
    return TestClient(app)


def test_owner_can_validate_own_project(client, make_token):
    t = make_token(sub="user-a")
    r = client.post("/api/validate-path", json={"path": "proj"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200


def test_other_user_cannot_reach_foreign_path(client, make_token):
    t = make_token(sub="user-b")
    r = client.post("/api/validate-path", json={"path": "../user-a/proj"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403
