import shutil
import pytest
from pathlib import Path
from utils.worktree import provision
from utils.profiles import write_profiles, resolve_profile_name

pytestmark = pytest.mark.skipif(shutil.which("dbt") is None and shutil.which("uv") is None,
                                reason="dbt/uv not available in this environment")


def test_dbt_run_against_duckdb(git_project, tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_REPOS_PATH", str(tmp_path / "users"))
    wt = Path(provision(sub="user-a", project_id="p1",
                         repo_path=str(git_project), main_branch="main"))
    conn = {"dev": {"engine": "duckdb", "path": "dev.duckdb", "schema": "main"}}
    write_profiles(wt, resolve_profile_name(wt), conn, default_target="dev")

    import subprocess
    # Use a one-off venv with dbt-duckdb (mirrors _recreate_venv_sync, trimmed).
    subprocess.run(["uv", "venv", str(wt / ".dbt-ui-venv")], check=True)
    py = wt / ".dbt-ui-venv" / "bin" / "python"
    subprocess.run(["uv", "pip", "install", "dbt-core", "dbt-duckdb",
                    "--python", str(py)], check=True)
    dbt = wt / ".dbt-ui-venv" / "bin" / "dbt"
    r = subprocess.run([str(dbt), "run", "--project-dir", str(wt),
                        "--profiles-dir", str(wt), "--target", "dev"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
