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
    for u in ("user-a", "user-b"):
        p = tmp_path / u / "proj"
        p.mkdir(parents=True)
        (p / "dbt_project.yml").write_text("name: demo\n")
    from main import app
    import routes.dbt_routes as dbt
    from utils.user_paths import resolve_under_root
    a_path = str(resolve_under_root("user-a", "proj"))
    dbt.dbt_command_status[("user-a", a_path)] = {"status": "completed", "output": "A-SECRET-OUTPUT"}
    return TestClient(app)


def test_user_b_cannot_read_user_a_status(client, make_token):
    t = make_token(sub="user-b")
    r = client.post("/api/dbt-command-status", json={"path": "../user-a/proj"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403
