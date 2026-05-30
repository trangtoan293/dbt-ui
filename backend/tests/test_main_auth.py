import pytest
from fastapi.testclient import TestClient
import auth as auth_mod
from tests.conftest import TEST_ISSUER, TEST_AUDIENCE


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    pub = rsa_key.public_key()
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: pub)
    monkeypatch.setattr(auth_mod, "ISSUER", TEST_ISSUER)
    monkeypatch.setattr(auth_mod, "AUDIENCE", TEST_AUDIENCE)


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_me_requires_auth(client):
    assert client.get("/api/me").status_code == 401


def test_me_returns_identity(client, make_token):
    r = client.get("/api/me", headers={"Authorization": f"Bearer {make_token(sub='me1', roles=['developer'])}"})
    assert r.status_code == 200
    assert r.json()["sub"] == "me1"
    assert "developer" in r.json()["roles"]


def test_protected_route_rejects_no_token(client):
    assert client.post("/api/validate-path", json={"path": "/tmp"}).status_code == 401
