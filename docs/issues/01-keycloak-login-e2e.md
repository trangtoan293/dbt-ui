# 01 — Keycloak login end-to-end

## What to build

Put a BFF (oauth2-proxy or nginx-OIDC) in front of the API. The BFF performs the
Keycloak OIDC Authorization Code flow, keeps tokens in a server-side session, and
forwards the **actual access token** to FastAPI (it must not strip it — later
slices need the real token for Dremio passthrough). FastAPI validates the JWT
against Keycloak's JWKS (signature, issuer, audience, expiry) and exposes the
authenticated identity through an `/api/me` endpoint returning the User's
Keycloak `sub`, email, and realm roles. The frontend shows the logged-in user.

This is the first tracer bullet: one real identity flowing through every layer to
one endpoint. Everything else builds on it.

## Acceptance criteria

- [ ] Visiting the app unauthenticated redirects to Keycloak login
- [ ] After login, the BFF holds a server-side session and forwards the access token to FastAPI
- [ ] FastAPI validates the JWT via JWKS and rejects expired / wrong-audience / wrong-issuer tokens
- [ ] `/api/me` returns the authenticated `sub`, email, and realm roles
- [ ] `/api/me` without a valid token returns 401
- [ ] UI displays the current logged-in user

## Blocked by

None — can start immediately. (HITL: requires a Keycloak realm + client config and a decision between oauth2-proxy and nginx-OIDC.)
