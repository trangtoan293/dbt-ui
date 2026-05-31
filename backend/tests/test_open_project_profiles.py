import pytest
import yaml
from pathlib import Path
from fastapi.testclient import TestClient
import auth as auth_mod
from main import app


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


def test_open_project_writes_profiles(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    r = client.post("/api/open-project", json={"id": "p1"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    wt = Path(r.json()["worktree"])
    profile = yaml.safe_load((wt / "profiles.yml").read_text())
    assert profile["demo"]["outputs"]["dev"]["type"] == "duckdb"
