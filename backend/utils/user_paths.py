"""Server-derived, per-user path authority.

A User may only touch paths under GIT_REPOS_PATH/<sub>. The client never
supplies a trusted absolute path; it supplies a sub-path that is resolved and
checked to be inside the user's own root. See ADR 0001 section 3.
"""
import os
import re
from pathlib import Path
from fastapi import HTTPException

_SUB_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def git_repos_path() -> Path:
    return Path(os.environ.get("GIT_REPOS_PATH", str(Path.home() / "git-repos"))).resolve()


def user_data_path() -> Path:
    """Root directory for user-specific data (workspaces, etc.)."""
    return Path(os.environ.get("USER_DATA_PATH", str(git_repos_path() / "users"))).resolve()


def user_root(sub: str) -> Path:
    """The worktree root for a user, derived from their Keycloak sub."""
    if not sub or not _SUB_RE.match(sub):
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
