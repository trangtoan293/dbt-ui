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


def _set_default_prod(client, tok):
    # set-target requires maintainer for a prod default, so do it as maintainer.
    client.post("/api/connections/set-target", json={"id": "p1", "target": "prod"},
                headers={"Authorization": f"Bearer {tok}"})


def test_developer_preview_blocked_when_default_is_prod(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    maint = make_token(sub="user-a", email="a@x.io", roles=["maintainer"])
    _open(client, maint)
    _set_default_prod(client, maint)  # default target now 'prod' (dremio)

    # Same user/worktree, but now acting as a developer token → must be blocked.
    dev = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    r = client.post("/api/dbt-show-model",
                    json={"path": "p1", "model": "stg_x", "limit": 5},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 403
