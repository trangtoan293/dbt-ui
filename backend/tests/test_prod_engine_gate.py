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


def test_developer_blocked_from_prod_engine(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    dev = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, dev)
    r = client.post("/api/dbt-command",
                    json={"path": "p1", "command": "run", "target": "prod", "selector": ""},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 403


def test_maintainer_prod_run_exchanges_token(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    maint = make_token(sub="user-m", email="m@x.io", roles=["maintainer"])
    _open(client, maint)
    captured = {}

    def fake_task(sub, path, command, selector="", target="", full_refresh=False, env_vars=None):
        captured["env"] = env_vars or {}

    with patch("routes.dbt_routes.exchange_for_dremio", return_value="dremio-tok"), \
         patch("routes.dbt_routes.run_dbt_command_task", side_effect=fake_task):
        r = client.post("/api/dbt-command",
                        json={"path": "p1", "command": "run", "target": "prod", "selector": ""},
                        headers={"Authorization": f"Bearer {maint}"})
    assert r.status_code == 200
    assert captured["env"].get("DREMIO_TOKEN") == "dremio-tok"


def test_dev_target_no_token(catalog_with_conn, make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    client = TestClient(app)
    dev = make_token(sub="user-a", email="a@x.io", roles=["developer"])
    _open(client, dev)
    captured = {}

    def fake_task(sub, path, command, selector="", target="", full_refresh=False, env_vars=None):
        captured["env"] = env_vars or {}

    with patch("routes.dbt_routes.run_dbt_command_task", side_effect=fake_task):
        r = client.post("/api/dbt-command",
                        json={"path": "p1", "command": "run", "target": "dev", "selector": ""},
                        headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 200
    assert "DREMIO_TOKEN" not in captured["env"]
