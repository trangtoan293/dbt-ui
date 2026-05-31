import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
import auth as auth_mod
from main import app


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


def _open_dir(sub, tmp_path):
    # Path authority resolves <user_root>/<sub_path>; create it so it exists.
    from utils.user_paths import resolve_under_root
    p = resolve_under_root(sub, "p1")
    p.mkdir(parents=True, exist_ok=True)
    return p


def test_format_returns_formatted_buffer(make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    _open_dir("user-a", tmp_path)
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])

    class _R:
        success = True
        stdout = "select 1\n"
        stderr = ""
        error = ""

    with patch("utils.sql_format.run_command", return_value=_R()):
        r = client.post("/api/format-sql",
                        json={"path": "p1", "file_path": "models/x.sql", "content": "SELECT     1"},
                        headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["formatted"] == "select 1\n"


def test_format_failure_returns_ok_false(make_token, monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    _open_dir("user-a", tmp_path)
    client = TestClient(app)
    tok = make_token(sub="user-a", email="a@x.io", roles=["developer"])

    class _R:
        success = False
        stdout = ""
        stderr = "Parsing error at line 1"
        error = "Parsing error at line 1"

    with patch("utils.sql_format.run_command", return_value=_R()):
        r = client.post("/api/format-sql",
                        json={"path": "p1", "file_path": "models/x.sql", "content": "SELECT ("},
                        headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "formatted" not in r.json() or r.json().get("formatted") is None
