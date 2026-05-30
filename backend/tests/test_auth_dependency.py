import pytest
from fastapi import HTTPException
from starlette.requests import Request
from auth import get_current_user, require_role
import auth as auth_mod
from tests.conftest import TEST_ISSUER, TEST_AUDIENCE


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    pub = rsa_key.public_key()
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: pub)
    monkeypatch.setattr(auth_mod, "ISSUER", TEST_ISSUER)
    monkeypatch.setattr(auth_mod, "AUDIENCE", TEST_AUDIENCE)


def _req(headers):
    scope = {"type": "http", "headers": [(k.lower().encode(), v.encode())
                                         for k, v in headers.items()]}
    return Request(scope)


def test_missing_header_401():
    with pytest.raises(HTTPException) as e:
        get_current_user(_req({}))
    assert e.value.status_code == 401


def test_bearer_header_returns_user(make_token):
    user = get_current_user(_req({"Authorization": f"Bearer {make_token(sub='zz')}"}))
    assert user.sub == "zz"


def test_require_role_allows(make_token):
    user = get_current_user(_req({"Authorization": f"Bearer {make_token(roles=['maintainer'])}"}))
    guard = require_role("maintainer")
    assert guard(user) is user


def test_require_role_blocks(make_token):
    user = get_current_user(_req({"Authorization": f"Bearer {make_token(roles=['developer'])}"}))
    guard = require_role("maintainer")
    with pytest.raises(HTTPException) as e:
        guard(user)
    assert e.value.status_code == 403
