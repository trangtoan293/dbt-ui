"""Exchange a user's Keycloak access token for a short-lived Dremio token.

RFC 8693 token exchange, performed at dbt job START while the Keycloak token is
still valid (ADR 0001 §6). The result is short-lived, held only in the job's
subprocess env, never persisted, and scrubbed from logs. If a job outlives the
Dremio token, dbt fails — token refresh is out of scope.
"""
import os
import httpx

GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"


class TokenExchangeError(Exception):
    """Raised when the Keycloak->Dremio token exchange fails or is misconfigured."""


def exchange_for_dremio(keycloak_token: str) -> str:
    token_url = os.environ.get("KEYCLOAK_TOKEN_URL")
    audience = os.environ.get("DREMIO_AUDIENCE")
    client_id = os.environ.get("DREMIO_EXCHANGE_CLIENT_ID")
    if not (token_url and audience and client_id):
        raise TokenExchangeError(
            "Dremio token exchange not configured "
            "(KEYCLOAK_TOKEN_URL / DREMIO_AUDIENCE / DREMIO_EXCHANGE_CLIENT_ID)"
        )

    data = {
        "grant_type": GRANT,
        "client_id": client_id,
        "subject_token": keycloak_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": audience,
        "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
    }
    client_secret = os.environ.get("DREMIO_EXCHANGE_CLIENT_SECRET")
    if client_secret:
        data["client_secret"] = client_secret

    try:
        resp = httpx.post(token_url, data=data, timeout=15)
    except Exception as e:  # network errors must not leak the token
        raise TokenExchangeError("token exchange request failed") from e

    if resp.status_code != 200:
        raise TokenExchangeError(f"token exchange rejected (status {resp.status_code})")

    token = resp.json().get("access_token")
    if not token:
        raise TokenExchangeError("token exchange response had no access_token")
    return token
