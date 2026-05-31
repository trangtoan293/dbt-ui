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
