import pytest
from auth import verify_token
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


def test_name_claim_extracted(rsa_key):
    import time, jwt
    now = int(time.time())
    token = jwt.encode({
        "sub": "u1", "email": "a@b.c", "name": "Alice Dev",
        "aud": "account", "iss": "https://portal-pam.hanas.io/realms/sbv-portal",
        "iat": now, "exp": now + 300, "realm_access": {"roles": ["developer"]},
    }, rsa_key, algorithm="RS256", headers={"kid": "test-key-1"})
    user = verify_token(token)
    assert user.name == "Alice Dev"
