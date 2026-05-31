"""Project Catalog: admin-registered local repos. JSON-file backed.

A Catalog entry points at a canonical git repo living on the server. There is no
remote (ADR 0001 section 2). Users may only open Projects from this Catalog.
"""
import json
import os
import uuid
from pathlib import Path
from fastapi import HTTPException
from utils.input_validation import validate_git_branch_name
from utils.user_paths import git_repos_path


def _catalog_path() -> Path:
    return Path(os.environ.get("CATALOG_PATH", str(Path.home() / "catalog.json")))


def load() -> list:
    p = _catalog_path()
    if not p.exists():
        return []
    return json.loads(p.read_text() or "[]")


def _save(entries: list) -> None:
    p = _catalog_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, indent=2))


def get(entry_id: str) -> dict | None:
    for e in load():
        if e["id"] == entry_id:
            return e
    return None


def add_entry(name: str, repo_path: str, main_branch: str = "main") -> dict:
    repo = Path(repo_path).resolve()
    # Confine canonical repos to GIT_REPOS_PATH so admins cannot register
    # arbitrary server paths and expose them to all users.
    try:
        repo.relative_to(git_repos_path())
    except ValueError:
        raise HTTPException(status_code=400,
                            detail="repo_path must be under GIT_REPOS_PATH")
    if not (repo / ".git").exists():
        raise HTTPException(status_code=400,
                            detail="repo_path is not a git repository")
    # Validate branch name to prevent git argument injection.
    validated_branch = validate_git_branch_name(main_branch)
    entry = {"id": uuid.uuid4().hex, "name": name,
             "repo_path": str(repo), "main_branch": validated_branch}
    entries = load()
    entries.append(entry)
    _save(entries)
    return entry


def remove_entry(entry_id: str) -> None:
    entries = [e for e in load() if e["id"] != entry_id]
    _save(entries)


def set_connections(project_id: str, connections: dict) -> None:
    """Persist a connections block onto an existing Catalog entry."""
    entries = load()
    for entry in entries:
        if entry["id"] == project_id:
            entry["connections"] = connections
            _save(entries)
            return
    raise KeyError(project_id)
