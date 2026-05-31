from pathlib import Path

from utils.venv_utils import get_venv_dbt_path
from utils.dbt_utils import get_dbt_env
from utils.subprocess_utils import run_command


def _sqlfluff_bin(worktree: Path) -> str:
    try:
        dbt = Path(get_venv_dbt_path(worktree))
        candidate = dbt.parent / "sqlfluff"
        return str(candidate) if candidate.exists() else "sqlfluff"
    except FileNotFoundError:
        return "sqlfluff"


def format_sql(worktree: Path, content: str) -> dict:
    """Format SQL text. Returns {ok, formatted?} or {ok: False, error}."""
    bin_path = _sqlfluff_bin(worktree)
    env = get_dbt_env(worktree)
    result = run_command(
        [bin_path, "format", "-"],
        worktree, timeout=60, env=env, input=content,
    )
    if result.success:
        return {"ok": True, "formatted": result.stdout}
    return {"ok": False, "error": (result.error or result.stderr or "format failed")}
