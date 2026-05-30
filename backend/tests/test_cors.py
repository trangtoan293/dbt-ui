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
def client():
    from main import app
    return TestClient(app)


def test_cors_preflight_restricts_methods(client):
    r = client.options("/api/me", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
    })
    allow = r.headers.get("access-control-allow-methods", "")
    # Only GET, POST, OPTIONS should be allowed — not DELETE, PUT, PATCH
    assert "POST" in allow
    assert "DELETE" not in allow
    assert "PUT" not in allow
    assert "PATCH" not in allow
