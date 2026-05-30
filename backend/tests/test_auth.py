import pytest
from auth import verify_token, CurrentUser
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    """Make verify_token use the test RSA public key instead of live JWKS."""
    from tests.conftest import TEST_ISSUER, TEST_AUDIENCE
    pub = rsa_key.public_key()
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: pub)
    monkeypatch.setattr(auth_mod, "ISSUER", TEST_ISSUER)
    monkeypatch.setattr(auth_mod, "AUDIENCE", TEST_AUDIENCE)


def test_valid_token_returns_user(make_token):
    user = verify_token(make_token(sub="u1", email="a@b.c", roles=["maintainer"]))
    assert isinstance(user, CurrentUser)
    assert user.sub == "u1"
    assert user.email == "a@b.c"
    assert "maintainer" in user.roles


def test_expired_token_rejected(make_token):
    with pytest.raises(Exception):
        verify_token(make_token(exp_delta=-10))


def test_wrong_issuer_rejected(make_token):
    with pytest.raises(Exception):
        verify_token(make_token(iss="https://evil.example/realms/x"))


def test_wrong_audience_rejected(make_token):
    with pytest.raises(Exception):
        verify_token(make_token(aud="some-other-client"))
