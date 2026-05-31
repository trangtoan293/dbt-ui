# M2 — Tenancy & Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the secured single-user backend (M1) into real multi-user tenancy: an admin-curated Project Catalog of local repos, per-user worktrees provisioned from the Catalog, three enforced roles, local-only git authored as the Keycloak user, and a diff-reviewed merge of a user's branch into Main.

**Architecture:** A Catalog file lists admin-registered canonical repos on the server (no remote). When a User opens a Catalog Project, the server provisions a git worktree under the user's `sub`-derived root, branched off the Project's Main. Commits are authored from the Keycloak identity. Remote git (clone/push/pull) is removed. Maintainers merge a user branch into Main after reviewing a diff; conflicts surface through the existing 3-way merge handling.

**Tech Stack:** FastAPI, git CLI (worktrees), PyJWT, pytest + httpx, React + Monaco DiffEditor.

**Covers issues:** `docs/issues/06..10`. Glossary: `CONTEXT.md`. Decisions: `docs/adr/0001-multi-user-keycloak-architecture.md`.

---

## HARD DEPENDENCY ON M1

This plan calls these M1 symbols verbatim. **If the M1 implementation named them differently, reconcile before executing M2.**

- `auth.CurrentUser` (fields `sub`, `email`, `roles`) — M2 **adds** a `name` field (Task 4).
- `auth.get_current_user` — request dependency returning `CurrentUser`.
- `auth.require_role(role: str)` — dependency factory, 403 on missing role.
- `utils.user_paths.user_root(sub)` and `resolve_under_root(sub, sub_path)`.
- `utils.audit.audit(sub, action, target, extra)`.
- `tests/conftest.py` fixture `make_token(sub, email, roles, ...)`.

M2 also reuses existing code: `routes/git_routes.py` helpers `get_git_repos_path`, `run_git_command` (from `utils/subprocess_utils.py`), the existing `/api/setup-worktree` logic (repurposed), and `utils/merge_utils.py`.

---

## File Structure

- Create `backend/utils/catalog.py` — Catalog storage (load/list/add/remove), backed by a JSON file at `CATALOG_PATH`.
- Create `backend/utils/worktree.py` — provision/reuse a per-user worktree from a Catalog entry; diff and merge helpers.
- Create `backend/routes/catalog_routes.py` — `/api/catalog/*` (list for all; add/remove admin-only) and `/api/open-project`.
- Modify `backend/auth.py` — add `name` to `CurrentUser`.
- Modify `backend/main.py` — mount `catalog_router`.
- Modify `backend/routes/git_routes.py` — remove clone/push/pull; author commits from Keycloak; add diff + merge-to-Main endpoints.
- Create `backend/tests/conftest_git.py` helper fixture (a real temp git repo) — registered in `conftest.py`.
- Frontend: replace `ProjectPathDialog` with a Catalog picker; add a `DiffMergePanel` using Monaco DiffEditor; remove push/pull/clone UI from `GitModal`.

---

## Task 0: Temp-git-repo test fixture

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add a `git_project` fixture**

Append to `backend/tests/conftest.py`:
```python
import subprocess
import pytest


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


@pytest.fixture
def git_project(tmp_path):
    """A canonical local repo with one commit on 'main'. Returns its path."""
    repo = tmp_path / "canonical" / "demo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "seed@example.com")
    _git(repo, "config", "user.name", "Seed")
    (repo / "dbt_project.yml").write_text("name: demo\nprofile: demo\n")
    (repo / "models").mkdir()
    (repo / "models" / "stg_x.sql").write_text("select 1 as id\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo
```

- [ ] **Step 2: Verify fixture loads**

Run: `cd backend && python -m pytest -q`
Expected: collection succeeds, no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add canonical git_project fixture for M2"
```

---

## Task 1: Catalog storage module (issue 06 core)

**Files:**
- Create: `backend/utils/catalog.py`
- Test: `backend/tests/test_catalog.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_catalog.py`:
```python
import pytest
from fastapi import HTTPException
from utils.catalog import add_entry, remove_entry, load, get


@pytest.fixture(autouse=True)
def catalog_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALOG_PATH", str(tmp_path / "catalog.json"))


def test_add_and_list(git_project):
    add_entry(name="Demo", repo_path=str(git_project), main_branch="main")
    entries = load()
    assert len(entries) == 1
    assert entries[0]["name"] == "Demo"
    assert entries[0]["id"]


def test_add_rejects_non_git_path(tmp_path):
    with pytest.raises(HTTPException) as e:
        add_entry(name="Bad", repo_path=str(tmp_path / "nope"), main_branch="main")
    assert e.value.status_code == 400


def test_get_by_id(git_project):
    e = add_entry(name="Demo", repo_path=str(git_project), main_branch="main")
    assert get(e["id"])["repo_path"] == str(git_project)


def test_remove_entry(git_project):
    e = add_entry(name="Demo", repo_path=str(git_project), main_branch="main")
    remove_entry(e["id"])
    assert load() == []


def test_get_missing_returns_none():
    # get() is a soft lookup (returns None); callers raise 404 when needed.
    assert get("does-not-exist") is None
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_catalog.py -v`
Expected: FAIL — `No module named 'utils.catalog'`.

- [ ] **Step 3: Implement `catalog.py`**

Create `backend/utils/catalog.py`:
```python
"""Project Catalog: admin-registered local repos. JSON-file backed.

A Catalog entry points at a canonical git repo living on the server. There is no
remote (ADR 0001 section 2). Users may only open Projects from this Catalog.
"""
import json
import os
import uuid
from pathlib import Path
from fastapi import HTTPException


def _catalog_path() -> Path:
    return Path(os.environ.get("CATALOG_PATH", str(Path.home() / "catalog.json")))


def load() -> list:
    """Load all Catalog entries (public — M3's connection helpers reuse this)."""
    p = _catalog_path()
    if not p.exists():
        return []
    return json.loads(p.read_text() or "[]")


def _save(entries: list) -> None:
    p = _catalog_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, indent=2))


def get(entry_id: str) -> dict | None:
    """Soft lookup by id. Returns None if absent — callers raise 404 if needed.
    (M3 relies on the None return to treat 'no connections configured' softly.)"""
    for e in load():
        if e["id"] == entry_id:
            return e
    return None


def add_entry(name: str, repo_path: str, main_branch: str = "main") -> dict:
    repo = Path(repo_path).resolve()
    if not (repo / ".git").exists():
        raise HTTPException(status_code=400,
                            detail="repo_path is not a git repository")
    entry = {"id": uuid.uuid4().hex, "name": name,
             "repo_path": str(repo), "main_branch": main_branch}
    entries = load()
    entries.append(entry)
    _save(entries)
    return entry


def remove_entry(entry_id: str) -> None:
    entries = [e for e in load() if e["id"] != entry_id]
    _save(entries)
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_catalog.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/catalog.py backend/tests/test_catalog.py
git commit -m "feat(catalog): admin-registered local-repo project catalog"
```

---

## Task 2: Catalog endpoints with RBAC (issues 06, 08)

**Files:**
- Create: `backend/routes/catalog_routes.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_catalog_routes.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_catalog_routes.py`:
```python
import pytest
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALOG_PATH", str(tmp_path / "catalog.json"))
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    from main import app
    return TestClient(app)


def test_developer_cannot_add_to_catalog(client, make_token, git_project):
    t = make_token(sub="dev1", roles=["developer"])
    r = client.post("/api/catalog/add",
                    json={"name": "Demo", "repo_path": str(git_project), "main_branch": "main"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403


def test_admin_can_add_and_anyone_can_list(client, make_token, git_project):
    admin = make_token(sub="admin1", roles=["admin"])
    r = client.post("/api/catalog/add",
                    json={"name": "Demo", "repo_path": str(git_project), "main_branch": "main"},
                    headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 200

    dev = make_token(sub="dev1", roles=["developer"])
    r2 = client.post("/api/catalog/list", headers={"Authorization": f"Bearer {dev}"})
    assert r2.status_code == 200
    assert len(r2.json()) == 1
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_catalog_routes.py -v`
Expected: FAIL — routes 404.

- [ ] **Step 3: Implement `catalog_routes.py`**

Create `backend/routes/catalog_routes.py`:
```python
"""Project Catalog API. Listing is open to any authenticated user;
mutations require the admin role."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user, require_role, CurrentUser
from utils import catalog
from utils.audit import audit

router = APIRouter()


class CatalogAddRequest(BaseModel):
    name: str
    repo_path: str
    main_branch: str = "main"


class CatalogIdRequest(BaseModel):
    id: str


@router.post("/api/catalog/list")
async def catalog_list(user: CurrentUser = Depends(get_current_user)):
    return catalog.load()


@router.post("/api/catalog/add")
async def catalog_add(req: CatalogAddRequest,
                      user: CurrentUser = Depends(require_role("admin"))):
    entry = catalog.add_entry(req.name, req.repo_path, req.main_branch)
    audit(sub=user.sub, action="catalog_add", target=entry["id"],
          extra={"name": req.name})
    return entry


@router.post("/api/catalog/remove")
async def catalog_remove(req: CatalogIdRequest,
                         user: CurrentUser = Depends(require_role("admin"))):
    catalog.remove_entry(req.id)
    audit(sub=user.sub, action="catalog_remove", target=req.id)
    return {"removed": req.id}
```

- [ ] **Step 4: Mount the router in `main.py`**

In `backend/main.py`, add the import with the other router imports:
```python
from routes.catalog_routes import router as catalog_router
```
And include it with the auth dependency (next to the others):
```python
app.include_router(catalog_router, dependencies=auth_dependency)
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_catalog_routes.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/catalog_routes.py backend/main.py backend/tests/test_catalog_routes.py
git commit -m "feat(catalog): catalog endpoints with admin RBAC"
```

---

## Task 3: Worktree provisioning helper (issue 07 core)

**Files:**
- Create: `backend/utils/worktree.py`
- Test: `backend/tests/test_worktree.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_worktree.py`:
```python
import pytest
from pathlib import Path
from utils.worktree import provision


@pytest.fixture(autouse=True)
def repos(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))


def test_provision_creates_worktree(git_project):
    wt = provision(sub="user-a", project_id="p1",
                    repo_path=str(git_project), main_branch="main")
    assert Path(wt).exists()
    assert (Path(wt) / "dbt_project.yml").exists()


def test_provision_is_idempotent(git_project):
    a = provision(sub="user-a", project_id="p1",
                  repo_path=str(git_project), main_branch="main")
    b = provision(sub="user-a", project_id="p1",
                  repo_path=str(git_project), main_branch="main")
    assert a == b


def test_two_users_get_isolated_worktrees(git_project):
    a = provision(sub="user-a", project_id="p1",
                  repo_path=str(git_project), main_branch="main")
    b = provision(sub="user-b", project_id="p1",
                  repo_path=str(git_project), main_branch="main")
    assert a != b
    assert "user-a" in a and "user-b" in b
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_worktree.py -v`
Expected: FAIL — `No module named 'utils.worktree'`.

- [ ] **Step 3: Implement `worktree.py`**

Create `backend/utils/worktree.py`:
```python
"""Provision and manage per-user git worktrees from a Catalog repo.

Each (User, Project) gets one worktree under the user's sub-derived root,
branched off the Project's Main. No remote is involved (ADR 0001 section 2).
"""
import subprocess
from pathlib import Path
from fastapi import HTTPException

from utils.user_paths import user_root


def _git(repo: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def _branch_name(sub: str) -> str:
    return f"dbtui/{sub}"


def provision(sub: str, project_id: str, repo_path: str, main_branch: str = "main") -> str:
    """Create or reuse the user's worktree for this project. Returns its path."""
    repo = Path(repo_path).resolve()
    wt_path = (user_root(sub) / project_id).resolve()

    if wt_path.exists():
        return str(wt_path)

    wt_path.parent.mkdir(parents=True, exist_ok=True)
    branch = _branch_name(sub)

    # Create the user branch off main if it does not yet exist.
    exists = _git(repo, "rev-parse", "--verify", branch)
    if exists.returncode != 0:
        created = _git(repo, "branch", branch, main_branch)
        if created.returncode != 0:
            raise HTTPException(status_code=500,
                                detail=f"Failed to create branch: {created.stderr}")

    added = _git(repo, "worktree", "add", str(wt_path), branch)
    if added.returncode != 0:
        raise HTTPException(status_code=500,
                            detail=f"Failed to add worktree: {added.stderr}")
    return str(wt_path)


def diff_against_main(repo_path: str, sub: str, main_branch: str = "main") -> str:
    """Unified diff of the user's branch vs Main."""
    repo = Path(repo_path).resolve()
    r = _git(repo, "diff", f"{main_branch}...{_branch_name(sub)}")
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=f"diff failed: {r.stderr}")
    return r.stdout


def merge_into_main(repo_path: str, sub: str, main_branch: str = "main") -> dict:
    """Merge the user's branch into Main on the canonical repo.
    Returns {merged: bool, conflicts: [...]}. Aborts on conflict."""
    repo = Path(repo_path).resolve()
    _git(repo, "checkout", main_branch)
    r = _git(repo, "merge", "--no-ff", _branch_name(sub))
    if r.returncode != 0:
        status = _git(repo, "diff", "--name-only", "--diff-filter=U")
        conflicts = [f for f in status.stdout.splitlines() if f]
        _git(repo, "merge", "--abort")
        return {"merged": False, "conflicts": conflicts}
    return {"merged": True, "conflicts": []}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_worktree.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/worktree.py backend/tests/test_worktree.py
git commit -m "feat(worktree): per-user worktree provisioning + diff/merge helpers"
```

---

## Task 4: Add `name` to CurrentUser (M1 extension for git author)

**Files:**
- Modify: `backend/auth.py`
- Test: `backend/tests/test_auth_name.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_auth_name.py`:
```python
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
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_auth_name.py -v`
Expected: FAIL — `CurrentUser` has no `name`.

- [ ] **Step 3: Add `name` to `CurrentUser` and extraction**

In `backend/auth.py`, add to the dataclass:
```python
@dataclass(frozen=True)
class CurrentUser:
    sub: str
    email: str
    roles: List[str] = field(default_factory=list)
    name: str = ""
```
In `verify_token`, set name (prefer `name`, fallback `preferred_username`, then email):
```python
    return CurrentUser(
        sub=claims["sub"],
        email=claims.get("email", ""),
        roles=claims.get("realm_access", {}).get("roles", []),
        name=claims.get("name") or claims.get("preferred_username") or claims.get("email", ""),
    )
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_auth_name.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py backend/tests/test_auth_name.py
git commit -m "feat(auth): extract display name from Keycloak token"
```

---

## Task 5: `/api/open-project` endpoint (issue 07)

**Files:**
- Modify: `backend/routes/catalog_routes.py`
- Test: `backend/tests/test_open_project.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_open_project.py`:
```python
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import auth as auth_mod


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALOG_PATH", str(tmp_path / "catalog.json"))
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    from main import app
    return TestClient(app)


def test_open_project_provisions_worktree(client, make_token, git_project):
    admin = make_token(sub="admin1", roles=["admin"])
    add = client.post("/api/catalog/add",
                      json={"name": "Demo", "repo_path": str(git_project), "main_branch": "main"},
                      headers={"Authorization": f"Bearer {admin}"})
    pid = add.json()["id"]

    dev = make_token(sub="dev1", roles=["developer"])
    r = client.post("/api/open-project", json={"id": pid},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 200
    body = r.json()
    assert body["path"] == pid           # sub-path the frontend uses thereafter
    assert Path(body["worktree"]).exists()
```

> Note: the endpoint returns `path` = the project_id, which is the **sub-path**
> all subsequent file/dbt calls send (resolved under the user root by M1's
> `resolve_under_root`). The absolute `worktree` is returned for display only.

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_open_project.py -v`
Expected: FAIL — `/api/open-project` 404.

- [ ] **Step 3: Add the endpoint to `catalog_routes.py`**

Append to `backend/routes/catalog_routes.py`:
```python
from fastapi import HTTPException
from utils.worktree import provision


@router.post("/api/open-project")
async def open_project(req: CatalogIdRequest,
                       user: CurrentUser = Depends(get_current_user)):
    entry = catalog.get(req.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Project not found in catalog")
    wt = provision(sub=user.sub, project_id=entry["id"],
                   repo_path=entry["repo_path"], main_branch=entry["main_branch"])
    audit(sub=user.sub, action="open_project", target=entry["id"])
    return {"path": entry["id"], "worktree": wt, "name": entry.get("name", entry["id"])}
```

> `entry.get("name", ...)` (not `entry["name"]`) so a Catalog entry written
> without a `name` — e.g. M3's connection test fixtures — won't KeyError.

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_open_project.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/catalog_routes.py backend/tests/test_open_project.py
git commit -m "feat(project): open-project provisions per-user worktree"
```

---

## Task 6: Remove remote git (clone/push/pull) (issue 09)

**Files:**
- Modify: `backend/routes/git_routes.py`
- Test: `backend/tests/test_no_remote.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_no_remote.py`:
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


@pytest.mark.parametrize("route", ["/api/clone-git-repo", "/api/git-push", "/api/git-pull"])
def test_remote_routes_removed(client, make_token, route):
    t = make_token(sub="u1")
    r = client.post(route, json={}, headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_no_remote.py -v`
Expected: FAIL — these routes still exist (return 4xx other than 404 / or 200).

- [ ] **Step 3: Delete the remote endpoints**

In `backend/routes/git_routes.py`, delete the three endpoint functions and their decorators entirely:
- `@router.post("/api/clone-git-repo")` / `clone_git_repo`
- `@router.post("/api/git-push")` / `git_push`
- `@router.post("/api/git-pull")` / `git_pull`

Remove any imports left unused by these deletions (e.g. `GitRepoUrl`, `GitPushPullRequest` if now unused — verify with grep before removing).

- [ ] **Step 4: Run test + full suite**

Run: `cd backend && python -m pytest tests/test_no_remote.py -v && python -m pytest -q`
Expected: parametrized test passes; full suite green.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/git_routes.py backend/tests/test_no_remote.py
git commit -m "feat(git): remove clone/push/pull — local-only version control"
```

---

## Task 7: Commit authored as the Keycloak user (issue 09)

**Files:**
- Modify: `backend/routes/git_routes.py`
- Test: `backend/tests/test_commit_author.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_commit_author.py`:
```python
import subprocess
import pytest
from fastapi.testclient import TestClient
import auth as auth_mod
from utils.worktree import provision


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    from main import app
    return TestClient(app)


def test_commit_uses_keycloak_identity(client, make_token, git_project, tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    wt = provision(sub="dev1", project_id="p1", repo_path=str(git_project), main_branch="main")
    (wt_file := __import__("pathlib").Path(wt) / "models" / "new.sql").write_text("select 2\n")

    t = make_token(sub="dev1", email="dev1@corp.io", roles=["developer"])
    headers = {"Authorization": f"Bearer {t}"}
    client.post("/api/git-stage", json={"path": "p1", "files": ["models/new.sql"]}, headers=headers)
    r = client.post("/api/git-commit", json={"path": "p1", "message": "add model"}, headers=headers)
    assert r.status_code == 200

    log = subprocess.run(["git", "-C", wt, "log", "-1", "--format=%an <%ae>"],
                         capture_output=True, text=True)
    assert "dev1@corp.io" in log.stdout
```

> Adjust the `git-stage` / `git-commit` request field names to the real request
> models in `models.py` if they differ. The `path` field is the project sub-path
> (resolved under the user root by M1).

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_commit_author.py -v`
Expected: FAIL — commit author is the server/seed identity, not the Keycloak user.

- [ ] **Step 3: Set author in `git_commit`**

In `backend/routes/git_routes.py`, change `git_commit` to inject the user and pass author env to the commit. Add the parameter and build the git env:
```python
@router.post("/api/git-commit")
async def git_commit(request: GitCommitRequest,
                     user: CurrentUser = Depends(get_current_user)):
    ...
    # When invoking the commit, pass identity via env:
    commit_env = {
        "GIT_AUTHOR_NAME": user.name or user.email,
        "GIT_AUTHOR_EMAIL": user.email,
        "GIT_COMMITTER_NAME": user.name or user.email,
        "GIT_COMMITTER_EMAIL": user.email,
    }
```
Pass `commit_env` through `run_git_command` (merge into its environment). If `run_git_command` does not accept an env override, add an `env: dict | None = None` parameter to it in `utils/subprocess_utils.py` that updates `os.environ.copy()` before running, then pass `env=commit_env` from `git_commit`.

Ensure `from auth import get_current_user, CurrentUser` is imported in `git_routes.py`.

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_commit_author.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/git_routes.py backend/utils/subprocess_utils.py backend/tests/test_commit_author.py
git commit -m "feat(git): author commits as the Keycloak user"
```

---

## Task 8: Diff + merge-to-Main endpoints, maintainer-gated (issue 10)

**Files:**
- Modify: `backend/routes/git_routes.py`
- Test: `backend/tests/test_merge_to_main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_merge_to_main.py`:
```python
import subprocess
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import auth as auth_mod
from utils.worktree import provision


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_key):
    monkeypatch.setattr(auth_mod, "_get_signing_key", lambda token: rsa_key.public_key())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALOG_PATH", str(tmp_path / "catalog.json"))
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    from main import app
    return TestClient(app)


def _setup_project_with_commit(client, make_token, git_project):
    admin = make_token(sub="admin1", roles=["admin"])
    pid = client.post("/api/catalog/add",
                      json={"name": "Demo", "repo_path": str(git_project), "main_branch": "main"},
                      headers={"Authorization": f"Bearer {admin}"}).json()["id"]
    t = make_token(sub="maint1", email="m@corp.io", roles=["maintainer"])
    h = {"Authorization": f"Bearer {t}"}
    wt = client.post("/api/open-project", json={"id": pid}, headers=h).json()["worktree"]
    (Path(wt) / "models" / "new.sql").write_text("select 42\n")
    client.post("/api/git-stage", json={"path": pid, "files": ["models/new.sql"]}, headers=h)
    client.post("/api/git-commit", json={"path": pid, "message": "add new"}, headers=h)
    return pid, t


def test_developer_cannot_merge(client, make_token, git_project):
    pid, _ = _setup_project_with_commit(client, make_token, git_project)
    dev = make_token(sub="dev1", roles=["developer"])
    r = client.post("/api/merge-to-main", json={"id": pid},
                    headers={"Authorization": f"Bearer {dev}"})
    assert r.status_code == 403


def test_maintainer_merges_clean(client, make_token, git_project):
    pid, maint = _setup_project_with_commit(client, make_token, git_project)
    r = client.post("/api/merge-to-main", json={"id": pid},
                    headers={"Authorization": f"Bearer {maint}"})
    assert r.status_code == 200
    assert r.json()["merged"] is True

    log = subprocess.run(["git", "-C", str(git_project), "log", "main", "--oneline"],
                         capture_output=True, text=True)
    assert "add new" in log.stdout


def test_diff_shows_changes(client, make_token, git_project):
    pid, maint = _setup_project_with_commit(client, make_token, git_project)
    r = client.post("/api/project-diff", json={"id": pid},
                    headers={"Authorization": f"Bearer {maint}"})
    assert r.status_code == 200
    assert "new.sql" in r.json()["diff"]
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_merge_to_main.py -v`
Expected: FAIL — `/api/project-diff` and `/api/merge-to-main` 404.

- [ ] **Step 3: Add diff + merge endpoints**

In `backend/routes/git_routes.py`, add imports:
```python
from auth import require_role
from utils import catalog
from utils.worktree import diff_against_main, merge_into_main
from utils.audit import audit
from pydantic import BaseModel


class ProjectIdRequest(BaseModel):
    id: str
```
Add the endpoints:
```python
@router.post("/api/project-diff")
async def project_diff(req: ProjectIdRequest,
                       user: CurrentUser = Depends(get_current_user)):
    entry = catalog.get(req.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Project not found in catalog")
    diff = diff_against_main(entry["repo_path"], user.sub, entry["main_branch"])
    return {"diff": diff}


@router.post("/api/merge-to-main")
async def merge_to_main(req: ProjectIdRequest,
                        user: CurrentUser = Depends(require_role("maintainer"))):
    entry = catalog.get(req.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Project not found in catalog")
    result = merge_into_main(entry["repo_path"], user.sub, entry["main_branch"])
    audit(sub=user.sub, action="merge_to_main", target=req.id,
          extra={"merged": result["merged"], "conflicts": result["conflicts"]})
    return result
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd backend && python -m pytest tests/test_merge_to_main.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run full suite**

Run: `cd backend && python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/git_routes.py backend/tests/test_merge_to_main.py
git commit -m "feat(git): diff and maintainer-gated merge into Main"
```

---

## Task 9: Frontend — Catalog picker replaces free-path selection (issues 06, 07)

**Files:**
- Create: `frontend/src/components/main/ProjectCatalogDialog.tsx`
- Modify: `frontend/src/components/main/MainLayout.tsx`
- Modify/Remove: `frontend/src/components/main/ProjectPathDialog.tsx` (free-path entry removed)

> No frontend test infra exists in this repo; verify these tasks manually in the
> dev server. Use `apiFetch(apiUrl('/api/...'), ...)` for every call.

- [ ] **Step 1: Build the Catalog dialog**

Create `frontend/src/components/main/ProjectCatalogDialog.tsx`: a dialog that
calls `POST /api/catalog/list`, renders the projects as a selectable list, and on
selection calls `POST /api/open-project` with `{ id }`. Store the returned `path`
(the project id) as the active project path; show `name`. Admins (role from
`/api/me`) additionally see add/remove controls calling `/api/catalog/add` and
`/api/catalog/remove`.

- [ ] **Step 2: Wire into MainLayout**

In `MainLayout.tsx`, replace the free-path `ProjectPathDialog` flow with
`ProjectCatalogDialog`. The active project path becomes the project id returned by
`open-project`; all existing file/dbt calls continue to send that as `path`.

- [ ] **Step 3: Remove free-path entry**

Remove the manual path text-entry / folder-browse path-typing from
`ProjectPathDialog` (or delete the component if fully replaced). Keep nothing that
lets a user type an arbitrary server path.

- [ ] **Step 4: Manual verification**

Run: `cd frontend && npm run dev`
Verify: a developer sees only Catalog projects; selecting one opens it; an admin
can add/remove a Catalog entry; no free-path text box remains.

- [ ] **Step 5: Typecheck + lint + commit**

```bash
cd frontend && npm run typecheck && npm run lint
cd .. && git add frontend/src/components/main/
git commit -m "feat(ui): project catalog picker replaces free-path selection"
```

---

## Task 10: Frontend — diff viewer + merge UI, remove push/pull (issues 09, 10)

**Files:**
- Create: `frontend/src/components/git/DiffMergePanel.tsx`
- Modify: `frontend/src/components/git/GitModal.tsx`

- [ ] **Step 1: Build the diff + merge panel**

Create `frontend/src/components/git/DiffMergePanel.tsx`: calls
`POST /api/project-diff` with `{ id }` and renders the unified diff using Monaco
`DiffEditor` (original = Main, modified = working branch). A "Merge into Main"
button calls `POST /api/merge-to-main`; it is shown only to maintainers (role from
`/api/me`). On a conflict response (`merged: false`), list `conflicts` and do not
claim success.

- [ ] **Step 2: Remove push/pull/clone from GitModal**

In `GitModal.tsx`, remove the Clone, Push, and Pull controls and any calls to the
deleted endpoints. Keep stage, commit, branch, and history.

- [ ] **Step 3: Manual verification**

Run: `cd frontend && npm run dev`
Verify: a maintainer can review a diff and merge into Main; a developer sees the
diff but no merge button; clone/push/pull are gone from the UI.

- [ ] **Step 4: Typecheck + lint + commit**

```bash
cd frontend && npm run typecheck && npm run lint
cd .. && git add frontend/src/components/git/
git commit -m "feat(ui): diff viewer + maintainer merge, remove remote git UI"
```

---

## Task 11: M2 verification gate

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite green**

Run: `cd backend && python -m pytest -v`
Expected: all pass (M1 + M2 tests).

- [ ] **Step 2: No remote git endpoints remain**

Run: `cd backend && grep -rn "clone-git-repo\|git-push\|git-pull" routes/`
Expected: no output.

- [ ] **Step 3: Frontend builds**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: success.

- [ ] **Step 4: Manual multi-user walk-through (HITL)**

With two Keycloak users (one maintainer, one developer): both open the same
Catalog project, each gets an isolated worktree; developer edits + commits (author
= their Keycloak identity) but cannot merge; maintainer reviews the diff and merges
into Main; the developer's later open reflects updated Main.

- [ ] **Step 5: security-reviewer pass**

Run the security-reviewer agent over the M2 diff. Focus: RBAC bypasses on
catalog/merge, path authority still holding on the new endpoints, no remote
credential surface reintroduced. Resolve CRITICAL/HIGH before declaring M2 done.

---

## Self-Review notes

- **Issue 06 (Catalog):** Tasks 1–2 (storage + admin endpoints) + Task 9 (UI). ✅
- **Issue 07 (worktree provisioning):** Tasks 3, 5 (helper + open-project) + Task 9 wiring. ✅
- **Issue 08 (RBAC):** admin gate (Task 2), maintainer gate on merge (Task 8). Production-engine gate is deferred to M3/issue 13 (engine work) — noted, not a gap in M2. ✅
- **Issue 09 (local git author + remove remote):** Tasks 6 (remove remote) + 7 (author) + Task 10 (UI). ✅
- **Issue 10 (diff + merge to Main):** Tasks 3 (helpers) + 8 (endpoints) + Task 10 (UI). ✅
- **M1 coupling:** Symbols listed in "HARD DEPENDENCY ON M1". Task 4 additively extends `CurrentUser` with `name`. If M1 shipped with different names, reconcile those references before running.
- **Merge model:** `merge_into_main` checks out Main on the canonical repo and merges the user branch there. Conflicts abort cleanly and are reported; resolving conflicts in-UI is out of M2 scope (surface only) — consistent with issue 10 ("surface conflicts using existing handling").
