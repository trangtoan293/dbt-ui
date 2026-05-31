import pytest
import yaml
from pathlib import Path
from fastapi.testclient import TestClient
import auth as auth_mod
from main import app


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


def _open(client, tok):
    client.post("/api/open-project", json={"id": "p1"},
                headers={"Authorization": f"Bearer {tok}"})


def test_get_connections_any_user(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    tok = make_token(sub="u", email="u@x.io", roles=["developer"])
    r = client.post("/api/connections/get", json={"id": "p1"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert "prod" in r.json()["connections"]


def test_set_connections_requires_admin(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    dev = make_token(sub="d", email="d@x.io", roles=["developer"])
    r = client.post("/api/connections/set",
                    json={"id": "p1", "connections": {"dev": {"engine": "duckdb"}}},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 403


def test_set_connections_rejects_secret(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    admin = make_token(sub="a", email="a@x.io", roles=["admin"])
    r = client.post("/api/connections/set",
                    json={"id": "p1",
                          "connections": {"prod": {"engine": "dremio", "token": "leak"}}},
                    headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 400


def test_set_target_rerenders_profiles(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, tok)
    r = client.post("/api/connections/set-target", json={"id": "p1", "target": "dev"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    wt = Path(r.json()["worktree"])
    profile = yaml.safe_load((wt / "profiles.yml").read_text())
    assert profile["demo"]["target"] == "dev"
