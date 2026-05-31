# M1 — Secure Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dbt-ui safe to deploy: every request is an authenticated Keycloak User, paths are server-derived per user, dbt output cannot leak across users, and production hardening (CORS, cookies, rate limit, audit, file-size) is in place.

**Architecture:** A BFF (oauth2-proxy) terminates the Keycloak OIDC flow and forwards the real access token as `Authorization: Bearer` to FastAPI. FastAPI independently validates the JWT against Keycloak JWKS and resolves a `CurrentUser` (sub, email, roles). All file/git/dbt endpoints stop trusting client-supplied absolute paths and instead resolve a sub-path under a worktree root derived from the User's `sub`. The in-memory dbt status dict is keyed by `(sub, path)` and secrets are scrubbed from output.

**Tech Stack:** FastAPI, PyJWT (with PyJWKClient), pytest + httpx, oauth2-proxy (BFF, infra), Keycloak (realm `sbv-portal`).

**Covers issues:** `docs/issues/01..05`. Glossary: `CONTEXT.md`. Decisions: `docs/adr/0001-multi-user-keycloak-architecture.md`.

**Keycloak environment (provided):**
```
KEYCLOAK_ISSUER=https://portal-pam.hanas.io/realms/sbv-portal
KEYCLOAK_JWKS_URI=https://portal-pam.hanas.io/realms/sbv-portal/protocol/openid-connect/certs
KEYCLOAK_AUDIENCE=account
```
> Caveat: `account` is Keycloak's default audience. It is accepted here to unblock M1, but a dedicated client + audience mapper should replace it later so the token is scoped to dbt-ui specifically. Tracked as a follow-up, not part of M1.

---

## Out-of-band prerequisites (HITL — human, not an agent)

These are infra steps for issue 01. Do them before/around Task 7 (the BFF is only needed for live login; the JWT-validation tasks are testable without it).

1. In realm `sbv-portal`, create an OIDC client for dbt-ui (confidential), redirect URI of the deployed app, standard flow enabled.
2. Deploy oauth2-proxy in front of the API with:
   - `--provider=oidc`, `--oidc-issuer-url=https://portal-pam.hanas.io/realms/sbv-portal`
   - `--pass-authorization-header=true` (forward `Authorization: Bearer <access_token>` to the backend)
   - `--pass-access-token=true`, `--set-authorization-header=true`
   - cookie secret, client id/secret from step 1, `--cookie-secure=true`, `--cookie-samesite=lax`
3. Verify end-to-end: log in via Keycloak, hit `/api/me` through the proxy, see your `sub`/email/roles (Task 6 makes `/api/me` exist).

---

## File Structure

- Create `backend/auth.py` rewrite — JWT validation + `CurrentUser` + `get_current_user` + role guards. (Replaces HTTP Basic.)
- Create `backend/utils/user_paths.py` — derive worktree root from `sub`, resolve+authorize a sub-path under it.
- Create `backend/utils/secret_scrub.py` — redact secrets from dbt output/logs.
- Create `backend/utils/rate_limit.py` — per-user in-memory rate limiter.
- Create `backend/utils/audit.py` — structured audit logging.
- Modify `backend/main.py` — JWT auth dependency on all routers, tighten CORS, mount `/api/me`.
- Modify `backend/routes/file_routes.py`, `git_routes.py`, `dbt_routes.py`, `env_routes.py`, `venv_routes.py` — use `CurrentUser` + `user_paths` instead of trusting `request.path`.
- Modify `backend/routes/dbt_routes.py` — key `dbt_command_status` by `(sub, path)`, scrub output, rate-limit, audit.
- Create `backend/tests/` — pytest suite with a fake-JWKS token factory.
- Modify `backend/pyproject.toml` — add `pyjwt[crypto]`, and dev deps `pytest`, `httpx`.

---

## Task 0: Test infrastructure + fake-JWKS token factory

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Add dependencies**

In `backend/pyproject.toml`, add to `dependencies`:
```toml
    "pyjwt[crypto]>=2.8.0",
```
Add a dev group:
```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
]
```

- [ ] **Step 2: Install**

Run: `cd backend && uv pip install -e . && uv pip install pytest httpx pyjwt[crypto]`
Expected: installs without error.

- [ ] **Step 3: Create the token factory fixture**

Create `backend/tests/__init__.py` (empty file).

Create `backend/tests/conftest.py`:
```python
"""Shared test fixtures: a local RSA keypair that stands in for Keycloak's JWKS."""
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import jwt

TEST_ISSUER = "https://portal-pam.hanas.io/realms/sbv-portal"
TEST_AUDIENCE = "account"
TEST_KID = "test-key-1"


@pytest.fixture(scope="session")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def public_pem(rsa_key):
    return rsa_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


@pytest.fixture
def make_token(rsa_key):
    """Build a signed JWT with the given claims, defaulting to a valid token."""
    def _make(sub="user-abc", email="dev@example.com", roles=None,
              aud=TEST_AUDIENCE, iss=TEST_ISSUER, exp_delta=300):
        now = int(time.time())
        claims = {
            "sub": sub,
            "email": email,
            "aud": aud,
            "iss": iss,
            "iat": now,
            "exp": now + exp_delta,
            "realm_access": {"roles": roles or ["developer"]},
        }
        return jwt.encode(claims, rsa_key, algorithm="RS256",
                          headers={"kid": TEST_KID})
    return _make
```

- [ ] **Step 4: Verify pytest collects**

Run: `cd backend && python -m pytest -q`
Expected: `no tests ran` (exit 5) — collection works, no errors.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/tests/__init__.py backend/tests/conftest.py
git commit -m "test: add pytest infra and fake-JWKS token factory"
```

---

## Task 1: JWT validation core (`verify_token`)

**Files:**
- Create: `backend/auth.py` (overwrites the HTTP Basic version)
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_auth.py`:
```python
import pytest
from auth import verify_token, CurrentUser
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    """Make verify_token use the test RSA public key instead of live JWKS."""
    pub = rsa_key.public_key()
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: pub)


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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: FAIL — `ImportError: cannot import name 'verify_token'`.

- [ ] **Step 3: Implement `auth.py`**

Overwrite `backend/auth.py`:
```python
"""Keycloak JWT authentication."""
import os
from dataclasses import dataclass, field
from typing import List

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request, status

ISSUER = os.environ.get("KEYCLOAK_ISSUER", "")
JWKS_URI = os.environ.get("KEYCLOAK_JWKS_URI", "")
AUDIENCE = os.environ.get("KEYCLOAK_AUDIENCE", "account")

_jwks_client: PyJWKClient | None = None


@dataclass(frozen=True)
class CurrentUser:
    sub: str
    email: str
    roles: List[str] = field(default_factory=list)


def _get_signing_key(token: str):
    """Fetch the RSA signing key for this token from Keycloak JWKS (cached)."""
    global _jwks_client
    if _jwks_client is None:
        if not JWKS_URI:
            raise HTTPException(status_code=500, detail="JWKS URI not configured")
        _jwks_client = PyJWKClient(JWKS_URI)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_token(token: str) -> CurrentUser:
    """Validate a Keycloak access token and return the CurrentUser."""
    try:
        key = _get_signing_key(token)
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iss", "sub"]},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(
        sub=claims["sub"],
        email=claims.get("email", ""),
        roles=claims.get("realm_access", {}).get("roles", []),
    )
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py backend/tests/test_auth.py
git commit -m "feat(auth): validate Keycloak JWT against JWKS"
```

---

## Task 2: `get_current_user` request dependency + role guards

**Files:**
- Modify: `backend/auth.py`
- Test: `backend/tests/test_auth_dependency.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_auth_dependency.py`:
```python
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from auth import get_current_user, require_role
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    pub = rsa_key.public_key()
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: pub)


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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_auth_dependency.py -v`
Expected: FAIL — `cannot import name 'get_current_user'`.

- [ ] **Step 3: Append to `auth.py`**

Append to `backend/auth.py`:
```python
def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency: extract and validate the Bearer token."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(header[len("Bearer "):])


def require_role(role: str):
    """Dependency factory: require the user to have a given realm role."""
    def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if role not in user.roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {role}")
        return user
    return _guard
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_auth_dependency.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py backend/tests/test_auth_dependency.py
git commit -m "feat(auth): get_current_user dependency and role guard"
```

---

## Task 3: `/api/me` endpoint + auth mandatory on all routers (issues 01, 02)

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/test_main_auth.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_main_auth.py`:
```python
import pytest
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    pub = rsa_key.public_key()
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: pub)


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_me_requires_auth(client):
    assert client.get("/api/me").status_code == 401


def test_me_returns_identity(client, make_token):
    r = client.get("/api/me", headers={"Authorization": f"Bearer {make_token(sub='me1', roles=['developer'])}"})
    assert r.status_code == 200
    assert r.json()["sub"] == "me1"
    assert "developer" in r.json()["roles"]


def test_protected_route_rejects_no_token(client):
    # any state-changing API route must 401 without a token
    assert client.post("/api/validate-path", json={"path": "/tmp"}).status_code == 401
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_main_auth.py -v`
Expected: FAIL — `/api/me` 404 and protected route 200.

- [ ] **Step 3: Rewrite the auth wiring in `main.py`**

In `backend/main.py`, replace the imports and the auth-dependency block:

Replace:
```python
from auth import verify_credentials, is_auth_enabled
```
with:
```python
from auth import get_current_user, CurrentUser
from fastapi import Request
```

Replace:
```python
# Include routers with authentication dependency if auth is enabled
auth_dependency = [Depends(verify_credentials)] if is_auth_enabled() else []

app.include_router(file_router, dependencies=auth_dependency)
app.include_router(git_router, dependencies=auth_dependency)
app.include_router(dbt_router, dependencies=auth_dependency)
app.include_router(venv_router, dependencies=auth_dependency)
app.include_router(env_router, dependencies=auth_dependency)

# Only include MetaDV router if the feature is enabled
if is_metadv_enabled():
    app.include_router(metadv_router, dependencies=auth_dependency)
```
with:
```python
# Authentication is mandatory on every router. No optional/disabled path.
auth_dependency = [Depends(get_current_user)]

app.include_router(file_router, dependencies=auth_dependency)
app.include_router(git_router, dependencies=auth_dependency)
app.include_router(dbt_router, dependencies=auth_dependency)
app.include_router(venv_router, dependencies=auth_dependency)
app.include_router(env_router, dependencies=auth_dependency)

if is_metadv_enabled():
    app.include_router(metadv_router, dependencies=auth_dependency)


@app.get("/api/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    return {"sub": user.sub, "email": user.email, "roles": user.roles}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_main_auth.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_main_auth.py
git commit -m "feat(auth): mandatory auth on all routers, add /api/me"
```

---

## Task 4: Worktree-root path authority helper (issue 03 core)

**Files:**
- Create: `backend/utils/user_paths.py`
- Test: `backend/tests/test_user_paths.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_user_paths.py`:
```python
import pytest
from pathlib import Path
from fastapi import HTTPException
from utils.user_paths import user_root, resolve_under_root


def test_user_root_embeds_sub(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    root = user_root("user-xyz")
    assert root == (tmp_path / "user-xyz").resolve()


def test_resolve_inside_root_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    (tmp_path / "user-xyz" / "proj").mkdir(parents=True)
    p = resolve_under_root("user-xyz", "proj")
    assert p == (tmp_path / "user-xyz" / "proj").resolve()


def test_resolve_escapes_root_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    (tmp_path / "user-a").mkdir()
    (tmp_path / "user-b").mkdir()
    with pytest.raises(HTTPException) as e:
        resolve_under_root("user-a", "../user-b")
    assert e.value.status_code == 403


def test_absolute_path_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    with pytest.raises(HTTPException) as e:
        resolve_under_root("user-a", "/etc/passwd")
    assert e.value.status_code == 403
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_user_paths.py -v`
Expected: FAIL — `No module named 'utils.user_paths'`.

- [ ] **Step 3: Implement `user_paths.py`**

Create `backend/utils/user_paths.py`:
```python
"""Server-derived, per-user path authority.

A User may only touch paths under GIT_REPOS_PATH/<sub>. The client never
supplies a trusted absolute path; it supplies a sub-path that is resolved and
checked to be inside the user's own root. See ADR 0001 section 3.
"""
import os
from pathlib import Path
from fastapi import HTTPException


def git_repos_path() -> Path:
    return Path(os.environ.get("GIT_REPOS_PATH", str(Path.home() / "git-repos"))).resolve()


def user_root(sub: str) -> Path:
    """The worktree root for a user, derived from their Keycloak sub."""
    if not sub or "/" in sub or ".." in sub:
        raise HTTPException(status_code=400, detail="Invalid user identifier")
    return (git_repos_path() / sub).resolve()


def resolve_under_root(sub: str, sub_path: str) -> Path:
    """Resolve sub_path under the user's root, rejecting anything outside it."""
    root = user_root(sub)
    candidate = (root / sub_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside user workspace")
    return candidate
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_user_paths.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/user_paths.py backend/tests/test_user_paths.py
git commit -m "feat(security): server-derived per-user path authority helper"
```

---

## Task 5: Apply path authority to file/git/dbt/env/venv routes (issue 03)

**Files:**
- Modify: `backend/routes/file_routes.py`
- Modify: `backend/routes/git_routes.py`
- Modify: `backend/routes/dbt_routes.py`
- Modify: `backend/routes/env_routes.py`
- Modify: `backend/routes/venv_routes.py`
- Test: `backend/tests/test_path_authority_routes.py`

> Pattern for every endpoint: add `user: CurrentUser = Depends(get_current_user)`,
> and replace `Path(request.path).expanduser().resolve()` with
> `resolve_under_root(user.sub, request.path)`. The request's `path` field becomes
> a **sub-path relative to the user root**, not an absolute path. Each endpoint
> below follows this identical transformation.

- [ ] **Step 1: Write failing cross-user isolation test**

Create `backend/tests/test_path_authority_routes.py`:
```python
import pytest
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    # user-a owns a dbt project; user-b must not reach it
    proj = tmp_path / "user-a" / "proj"
    proj.mkdir(parents=True)
    (proj / "dbt_project.yml").write_text("name: demo\n")
    from main import app
    return TestClient(app)


def test_owner_can_validate_own_project(client, make_token):
    t = make_token(sub="user-a")
    r = client.post("/api/validate-path", json={"path": "proj"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200


def test_other_user_cannot_reach_foreign_path(client, make_token):
    t = make_token(sub="user-b")
    r = client.post("/api/validate-path", json={"path": "../user-a/proj"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_path_authority_routes.py -v`
Expected: FAIL — `test_other_user_cannot_reach_foreign_path` returns 200 or 404, not 403 (path is still client-trusted).

- [ ] **Step 3: Refactor `validate_path` in `file_routes.py`**

In `backend/routes/file_routes.py`, add imports near the top:
```python
from fastapi import Depends
from auth import get_current_user, CurrentUser
from utils.user_paths import resolve_under_root
```
Replace the `validate_path` endpoint:
```python
@router.post("/api/validate-path")
async def validate_path(project_path: ProjectPath,
                        user: CurrentUser = Depends(get_current_user)):
    """Validate that the user's sub-path is a dbt project."""
    path = resolve_under_root(user.sub, project_path.path)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    if not (path / "dbt_project.yml").exists():
        raise HTTPException(status_code=400,
                            detail="Not a valid dbt project (dbt_project.yml not found)")
    return {"valid": True, "path": str(path), "name": path.name}
```

- [ ] **Step 4: Refactor every remaining path-taking endpoint**

Apply the same transformation (inject `user`, swap to `resolve_under_root(user.sub, <field>)`) to each endpoint that currently does `Path(<field>).expanduser().resolve()`. Work through them with grep:

Run: `cd backend && grep -rn "expanduser().resolve()" routes/`

For each hit, edit the endpoint so it:
1. adds the parameter `user: CurrentUser = Depends(get_current_user)`,
2. replaces `Path(<field>).expanduser().resolve()` with `resolve_under_root(user.sub, <field>)`,
3. removes any now-unused `expanduser` logic.

Endpoints to convert (file_routes): `list_directory_shallow`, `read_file`, `save_file`, `create_file`, `rename_file`, `delete_file`, `restore_file`, and any other in that file. (git_routes): every endpoint taking a repo/project path. (dbt_routes): `dbt_command`, `dbt_compile_model`, `dbt_run_model`, `dbt_seed`, `dbt_test_model`, status/show endpoints. (env_routes, venv_routes): every path-taking endpoint.

> The env-var cookie name is keyed on the path string (`get_env_vars_from_cookie`).
> Since the resolved path now lives under the user root, the cookie is already
> per-user-scoped — no extra change needed there.

- [ ] **Step 5: Run the full suite, verify green**

Run: `cd backend && python -m pytest -v`
Expected: all pass, including both path-authority route tests.

- [ ] **Step 6: Grep to confirm no client-trusted absolute paths remain**

Run: `cd backend && grep -rn "expanduser().resolve()" routes/`
Expected: no output (all converted).

- [ ] **Step 7: Commit**

```bash
git add backend/routes/ backend/tests/test_path_authority_routes.py
git commit -m "feat(security): resolve all route paths under per-user root"
```

---

## Task 6: Namespace dbt status by (sub, path) (issue 04)

**Files:**
- Modify: `backend/routes/dbt_routes.py`
- Test: `backend/tests/test_status_isolation.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_status_isolation.py`:
```python
import pytest
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path))
    for u in ("user-a", "user-b"):
        p = tmp_path / u / "proj"
        p.mkdir(parents=True)
        (p / "dbt_project.yml").write_text("name: demo\n")
    from main import app
    import routes.dbt_routes as dbt
    # seed a fake completed status for user-a under their resolved path
    from utils.user_paths import resolve_under_root
    a_path = str(resolve_under_root("user-a", "proj"))
    dbt.dbt_command_status[("user-a", a_path)] = {"status": "completed", "output": "A-SECRET-OUTPUT"}
    return TestClient(app)


def test_user_b_cannot_read_user_a_status(client, make_token):
    t = make_token(sub="user-b")
    r = client.post("/api/dbt-command-status", json={"path": "../user-a/proj"},
                    headers={"Authorization": f"Bearer {t}"})
    # path is rejected (403) — B can never even name A's path
    assert r.status_code == 403
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_status_isolation.py -v`
Expected: FAIL — `dbt_command_status` is keyed by path string only, so the seed line raises or the lookup mismatches.

- [ ] **Step 3: Change the status dict key to (sub, path)**

In `backend/routes/dbt_routes.py`:

Change the declaration:
```python
dbt_command_status: Dict[str, Dict[str, any]] = {}
```
to:
```python
# Keyed by (user_sub, resolved_path) so one user can never read another's output.
dbt_command_status: Dict[tuple, Dict[str, any]] = {}
```

In the status endpoint, inject the user and resolve the path, then key by `(user.sub, path_str)`:
```python
@router.post("/api/dbt-command-status")
async def get_dbt_command_status(project_path: ProjectPath,
                                 user: CurrentUser = Depends(get_current_user)):
    path = resolve_under_root(user.sub, project_path.path)
    key = (user.sub, str(path))
    if key not in dbt_command_status:
        return {"status": "idle"}
    return dbt_command_status[key]
```

In `run_dbt_command_task`, accept `sub` and key every write by `(sub, path_str)`:
```python
def run_dbt_command_task(sub: str, path: Path, command: str, selector: str = "",
                         target: str = "", full_refresh: bool = False, env_vars: dict = None):
    path_str = str(path)
    key = (sub, path_str)
    dbt_command_status[key] = {"status": "running", ...}   # keep existing fields, swap key
    # ... replace every `dbt_command_status[path_str] = {...}` with `dbt_command_status[key] = {...}`
```

In `dbt_command` (the submit endpoint), pass `user.sub` into the task:
```python
background_tasks.add_task(run_dbt_command_task, user.sub, path, command,
                          selector, target, action.full_refresh, env_vars)
```
Ensure `dbt_command` and its wrappers inject `user: CurrentUser = Depends(get_current_user)` (done in Task 5).

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_status_isolation.py -v`
Expected: 1 passed.

- [ ] **Step 5: Run full suite**

Run: `cd backend && python -m pytest -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/dbt_routes.py backend/tests/test_status_isolation.py
git commit -m "feat(security): isolate dbt command status per user"
```

---

## Task 7: Scrub secrets from dbt output (issue 04)

**Files:**
- Create: `backend/utils/secret_scrub.py`
- Modify: `backend/routes/dbt_routes.py`
- Test: `backend/tests/test_secret_scrub.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_secret_scrub.py`:
```python
from utils.secret_scrub import scrub


def test_redacts_bearer_token():
    assert "REDACTED" in scrub("Authorization: Bearer abc.def.ghi")
    assert "abc.def.ghi" not in scrub("Authorization: Bearer abc.def.ghi")


def test_redacts_password_kv():
    out = scrub("password=SuperSecret123 host=dremio")
    assert "SuperSecret123" not in out
    assert "host=dremio" in out


def test_redacts_url_credentials():
    out = scrub("postgres://user:p4ss@db:5432/x")
    assert "p4ss" not in out


def test_plain_text_unchanged():
    assert scrub("Completed 5 models in 3.2s") == "Completed 5 models in 3.2s"
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_secret_scrub.py -v`
Expected: FAIL — `No module named 'utils.secret_scrub'`.

- [ ] **Step 3: Implement `secret_scrub.py`**

Create `backend/utils/secret_scrub.py`:
```python
"""Redact secrets from dbt output before it is stored, returned, or logged."""
import re

_PATTERNS = [
    re.compile(r"(?i)(authorization:\s*bearer\s+)\S+"),
    re.compile(r"(?i)\b(password|token|secret|api[-_]?key)\s*[=:]\s*\S+"),
    re.compile(r"(?i)(://[^:/\s]+:)[^@/\s]+(@)"),  # url credentials
]
_REPL = ["\\1<REDACTED>", "\\1=<REDACTED>", "\\1<REDACTED>\\2"]


def scrub(text: str) -> str:
    if not text:
        return text
    for pat, repl in zip(_PATTERNS, _REPL):
        text = pat.sub(repl, text)
    return text
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_secret_scrub.py -v`
Expected: 4 passed.

- [ ] **Step 5: Apply scrub to dbt output**

In `backend/routes/dbt_routes.py`, import at top:
```python
from utils.secret_scrub import scrub
```
In `run_dbt_command_task`, wrap captured stdout/stderr before storing. Wherever output is assigned into the status dict (e.g. `"output": result.stdout`), change to:
```python
"output": scrub(result.stdout),
"error": scrub(result.stderr),
```
Apply to every status write that contains command output.

- [ ] **Step 6: Run full suite**

Run: `cd backend && python -m pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/utils/secret_scrub.py backend/routes/dbt_routes.py backend/tests/test_secret_scrub.py
git commit -m "feat(security): scrub secrets from dbt output"
```

---

## Task 8: Tighten CORS + secure cookies (issue 05)

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/routes/env_routes.py` (cookie flags) and `backend/routes/git_routes.py` (git creds cookie)
- Test: `backend/tests/test_cors.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_cors.py`:
```python
import pytest
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_cors_preflight_does_not_allow_wildcard_methods(client):
    r = client.options("/api/me", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
    })
    allow = r.headers.get("access-control-allow-methods", "")
    assert "*" not in allow
    assert "POST" in allow
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_cors.py -v`
Expected: FAIL — allow-methods is `*`.

- [ ] **Step 3: Restrict CORS in `main.py`**

Replace the `app.add_middleware(CORSMiddleware, ...)` block:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

- [ ] **Step 4: Set Secure + SameSite on cookies**

In `backend/routes/env_routes.py` and `backend/routes/git_routes.py`, every `response.set_cookie(...)` call must include:
```python
response.set_cookie(
    ...,                       # existing key/value/httponly
    secure=True,
    samesite="lax",
)
```
Run to find them: `cd backend && grep -rn "set_cookie" routes/`
Add `secure=True, samesite="lax"` to each.

- [ ] **Step 5: Run tests, verify green**

Run: `cd backend && python -m pytest tests/test_cors.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/routes/env_routes.py backend/routes/git_routes.py backend/tests/test_cors.py
git commit -m "feat(security): restrict CORS and set secure cookies"
```

---

## Task 9: File-size limit on reads (issue 05)

**Files:**
- Modify: `backend/routes/file_routes.py`
- Test: `backend/tests/test_file_size_limit.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_file_size_limit.py`:
```python
import pytest
from fastapi.testclient import TestClient
import auth as auth_mod

MAX = 5 * 1024 * 1024


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


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
    r = client.post("/api/read-file", json={"path": "proj/big.sql"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 413
```

> Adjust the request body field names to match the real `read_file` endpoint
> signature if they differ (check `models.py` for the read-file request model).

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_file_size_limit.py -v`
Expected: FAIL — returns 200 with full content.

- [ ] **Step 3: Add the size guard**

In `backend/routes/file_routes.py`, add near the top:
```python
MAX_READ_BYTES = 5 * 1024 * 1024  # 5 MB
```
In the `read_file` endpoint, after resolving the path and before reading content:
```python
    if path.is_file() and path.stat().st_size > MAX_READ_BYTES:
        raise HTTPException(status_code=413, detail="File too large to open")
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_file_size_limit.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/file_routes.py backend/tests/test_file_size_limit.py
git commit -m "feat(security): cap file read size"
```

---

## Task 10: Per-user rate limit on dbt commands (issue 05)

**Files:**
- Create: `backend/utils/rate_limit.py`
- Modify: `backend/routes/dbt_routes.py`
- Test: `backend/tests/test_rate_limit.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_rate_limit.py`:
```python
import pytest
from fastapi import HTTPException
from utils.rate_limit import RateLimiter


def test_allows_up_to_limit():
    rl = RateLimiter(max_calls=3, window_seconds=60, now=lambda: 1000.0)
    for _ in range(3):
        rl.check("user-a")  # no raise


def test_blocks_over_limit():
    rl = RateLimiter(max_calls=3, window_seconds=60, now=lambda: 1000.0)
    for _ in range(3):
        rl.check("user-a")
    with pytest.raises(HTTPException) as e:
        rl.check("user-a")
    assert e.value.status_code == 429


def test_window_resets():
    t = {"v": 1000.0}
    rl = RateLimiter(max_calls=1, window_seconds=10, now=lambda: t["v"])
    rl.check("user-a")
    t["v"] = 1011.0
    rl.check("user-a")  # window passed, allowed again


def test_users_isolated():
    rl = RateLimiter(max_calls=1, window_seconds=60, now=lambda: 1000.0)
    rl.check("user-a")
    rl.check("user-b")  # different user, allowed
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_rate_limit.py -v`
Expected: FAIL — `No module named 'utils.rate_limit'`.

- [ ] **Step 3: Implement `rate_limit.py`**

Create `backend/utils/rate_limit.py`:
```python
"""In-memory per-user sliding-window rate limiter."""
import time
from collections import defaultdict, deque
from fastapi import HTTPException


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float, now=time.time):
        self._max = max_calls
        self._window = window_seconds
        self._now = now
        self._calls = defaultdict(deque)

    def check(self, key: str) -> None:
        now = self._now()
        q = self._calls[key]
        while q and q[0] <= now - self._window:
            q.popleft()
        if len(q) >= self._max:
            raise HTTPException(status_code=429, detail="Too many requests")
        q.append(now)
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_rate_limit.py -v`
Expected: 4 passed.

- [ ] **Step 5: Wire into dbt submit endpoint**

In `backend/routes/dbt_routes.py`, add near the top:
```python
from utils.rate_limit import RateLimiter

_dbt_rate_limiter = RateLimiter(max_calls=10, window_seconds=60)
```
In `dbt_command` (the submit endpoint), before acquiring the lock / starting the task:
```python
    _dbt_rate_limiter.check(user.sub)
```

- [ ] **Step 6: Run full suite**

Run: `cd backend && python -m pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/utils/rate_limit.py backend/routes/dbt_routes.py backend/tests/test_rate_limit.py
git commit -m "feat(security): per-user rate limit on dbt commands"
```

---

## Task 11: Audit log for state-changing endpoints (issue 05)

**Files:**
- Create: `backend/utils/audit.py`
- Modify: `backend/routes/dbt_routes.py`, `backend/routes/file_routes.py`, `backend/routes/git_routes.py`
- Test: `backend/tests/test_audit.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_audit.py`:
```python
import json
import logging
from utils.audit import audit


def test_audit_emits_structured_record(caplog):
    with caplog.at_level(logging.INFO, logger="dbt_ui.audit"):
        audit(sub="user-a", action="dbt_run", target="proj", extra={"selector": "stg_x"})
    rec = [r for r in caplog.records if r.name == "dbt_ui.audit"][-1]
    payload = json.loads(rec.getMessage())
    assert payload["sub"] == "user-a"
    assert payload["action"] == "dbt_run"
    assert payload["target"] == "proj"
    assert payload["selector"] == "stg_x"
    assert "ts" in payload
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_audit.py -v`
Expected: FAIL — `No module named 'utils.audit'`.

- [ ] **Step 3: Implement `audit.py`**

Create `backend/utils/audit.py`:
```python
"""Structured audit logging: who did what, when."""
import json
import logging
import time

_logger = logging.getLogger("dbt_ui.audit")


def audit(sub: str, action: str, target: str = "", extra: dict | None = None) -> None:
    record = {"ts": time.time(), "sub": sub, "action": action, "target": target}
    if extra:
        record.update(extra)
    _logger.info(json.dumps(record))
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_audit.py -v`
Expected: 1 passed.

- [ ] **Step 5: Emit audit records on state-changing actions**

In `backend/routes/dbt_routes.py`, in `dbt_command`, after the rate-limit check:
```python
    from utils.audit import audit
    audit(sub=user.sub, action=f"dbt_{command}", target=str(path),
          extra={"selector": selector, "target_env": target})
```
In `file_routes.py` add `audit(...)` to `save_file`, `create_file`, `rename_file`, `delete_file` (action = the operation name, target = resolved path).
In `git_routes.py` add `audit(...)` to commit and branch-creating endpoints.

- [ ] **Step 6: Run full suite**

Run: `cd backend && python -m pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/utils/audit.py backend/routes/ backend/tests/test_audit.py
git commit -m "feat(security): structured audit log for state-changing endpoints"
```

---

## Task 12: M1 verification gate

**Files:** none (verification only)

- [ ] **Step 1: Full suite green**

Run: `cd backend && python -m pytest -v`
Expected: every test passes.

- [ ] **Step 2: No client-trusted absolute paths remain**

Run: `cd backend && grep -rn "expanduser().resolve()" routes/`
Expected: no output.

- [ ] **Step 3: No optional-auth path remains**

Run: `cd backend && grep -rn "is_auth_enabled\|verify_credentials\|HTTPBasic" backend/ ; grep -rn "is_auth_enabled\|verify_credentials" .`
Expected: no output (HTTP Basic fully removed).

- [ ] **Step 4: Manual live check through the BFF (HITL)**

With oauth2-proxy + Keycloak running: log in, confirm `/api/me` returns your real `sub`/email/roles; confirm a request without the proxy/token gets 401.

- [ ] **Step 5: security-reviewer pass**

Run the security-reviewer agent over the M1 diff. Resolve any CRITICAL/HIGH before declaring M1 done.

---

## Self-Review notes

- **Issue 01 (login E2E):** Tasks 1–3 (JWT validate, dependency, `/api/me`) + out-of-band BFF/Keycloak client setup + Task 12 Step 4 live check. ✅
- **Issue 02 (auth mandatory):** Task 3 Step 3 + Task 12 Step 3. ✅
- **Issue 03 (path authority):** Tasks 4–5. ✅
- **Issue 04 (status isolation + scrub):** Tasks 6–7. ✅
- **Issue 05 (hardening):** Tasks 8 (CORS+cookies), 9 (file size), 10 (rate limit), 11 (audit). ✅
- **Dependency on slice 06/07 (worktree provisioning):** M1 assumes a worktree dir already exists under the user root; actual provisioning is issue 07 (M2). M1 tests create the dir directly. This is intentional — M1 secures the mechanism; M2 builds the provisioning flow on top.
