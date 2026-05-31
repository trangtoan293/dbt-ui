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
    Returns {merged: bool, conflicts: [...]}. Aborts on conflict.

    Caller must hold operation_lock(repo_path) before calling this function
    to prevent concurrent checkout+merge on the shared canonical repo.
    """
    repo = Path(repo_path).resolve()
    _git(repo, "checkout", main_branch)
    r = _git(repo, "merge", "--no-ff", _branch_name(sub))
    if r.returncode != 0:
        status = _git(repo, "diff", "--name-only", "--diff-filter=U")
        conflicts = [f for f in status.stdout.splitlines() if f]
        _git(repo, "merge", "--abort")
        return {"merged": False, "conflicts": conflicts}
    return {"merged": True, "conflicts": []}
