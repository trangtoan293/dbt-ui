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


def _load() -> list:
    p = _catalog_path()
    if not p.exists():
        return []
    return json.loads(p.read_text() or "[]")


def _save(entries: list) -> None:
    p = _catalog_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, indent=2))


def list_entries() -> list:
    return _load()


def get_entry(entry_id: str) -> dict:
    for e in _load():
        if e["id"] == entry_id:
            return e
    raise HTTPException(status_code=404, detail="Project not found in catalog")


def add_entry(name: str, repo_path: str, main_branch: str = "main") -> dict:
    repo = Path(repo_path).resolve()
    if not (repo / ".git").exists():
        raise HTTPException(status_code=400,
                            detail="repo_path is not a git repository")
    entry = {"id": uuid.uuid4().hex, "name": name,
             "repo_path": str(repo), "main_branch": main_branch}
    entries = _load()
    entries.append(entry)
    _save(entries)
    return entry


def remove_entry(entry_id: str) -> None:
    entries = [e for e in _load() if e["id"] != entry_id]
    _save(entries)
