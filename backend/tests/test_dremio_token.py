import pytest
from utils.dremio_token import exchange_for_dremio, TokenExchangeError


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def test_exchange_returns_access_token(monkeypatch):
    def fake_post(url, data=None, timeout=None):
        assert data["grant_type"] == "urn:ietf:params:oauth:grant-type:token-exchange"
        assert data["subject_token"] == "kc-token"
        return _Resp(200, {"access_token": "dremio-token", "expires_in": 3600})

    monkeypatch.setattr("utils.dremio_token.httpx.post", fake_post)
    monkeypatch.setenv("KEYCLOAK_TOKEN_URL", "https://kc/token")
    monkeypatch.setenv("DREMIO_AUDIENCE", "dremio")
    monkeypatch.setenv("DREMIO_EXCHANGE_CLIENT_ID", "dbt-ui")
    token = exchange_for_dremio("kc-token")
    assert token == "dremio-token"


def test_exchange_failure_raises(monkeypatch):
    def fake_post(url, data=None, timeout=None):
        return _Resp(400, {"error": "invalid_grant"})

    monkeypatch.setattr("utils.dremio_token.httpx.post", fake_post)
    monkeypatch.setenv("KEYCLOAK_TOKEN_URL", "https://kc/token")
    monkeypatch.setenv("DREMIO_AUDIENCE", "dremio")
    monkeypatch.setenv("DREMIO_EXCHANGE_CLIENT_ID", "dbt-ui")
    with pytest.raises(TokenExchangeError):
        exchange_for_dremio("kc-token")


def test_missing_config_raises(monkeypatch):
    monkeypatch.delenv("KEYCLOAK_TOKEN_URL", raising=False)
    with pytest.raises(TokenExchangeError):
        exchange_for_dremio("kc-token")
