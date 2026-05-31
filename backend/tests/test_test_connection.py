import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
import auth as auth_mod
from main import app


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


def _open(client, tok):
    client.post("/api/open-project", json={"id": "p1"},
                headers={"Authorization": f"Bearer {tok}"})


def test_duckdb_connection_test_runs_dbt_debug(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, tok)

    class _R:
        success = True
        stdout = "All checks passed!"
        stderr = ""
        error = ""

    with patch("routes.connection_routes.run_command", return_value=_R()):
        r = client.post("/api/connections/test", json={"id": "p1", "target": "dev"},
                        headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_dremio_connection_test_requires_maintainer(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    dev = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, dev)
    r = client.post("/api/connections/test", json={"id": "p1", "target": "prod"},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 403
