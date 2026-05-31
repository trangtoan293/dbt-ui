import pytest
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@pytest.mark.parametrize("route", ["/api/clone-git-repo", "/api/git-push", "/api/git-pull"])
def test_remote_routes_removed(client, make_token, route):
    t = make_token(sub="u1")
    r = client.post(route, json={}, headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 404
