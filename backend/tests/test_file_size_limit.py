import pytest
from fastapi.testclient import TestClient
import auth as auth_mod
from tests.conftest import TEST_ISSUER, TEST_AUDIENCE

MAX = 5 * 1024 * 1024


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())
    monkeypatch.setattr(auth_mod, "ISSUER", TEST_ISSUER)
    monkeypatch.setattr(auth_mod, "AUDIENCE", TEST_AUDIENCE)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    proj = tmp_path / "user-a" / "proj"
    proj.mkdir(parents=True)
    (proj / "big.sql").write_bytes(b"x" * (MAX + 1))
    from main import app
    return TestClient(app)


def test_oversized_file_rejected(client, make_token):
    t = make_token(sub="user-a")
    r = client.post("/api/read-file",
                    json={"projectPath": "proj", "filePath": "big.sql"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 413
