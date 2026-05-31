"""Render a dbt profiles.yml from a Project's secret-free Connection block.

dbt-ui OWNS profiles.yml: it is generated into each worktree from the Catalog
connections (admin-set). For Dev Engines the output is complete. For the
Production Engine (Dremio) the credential is supplied at runtime via the
DREMIO_TOKEN env var (token exchange at job start, ADR 0001 §6) — the file only
references it, never embeds it.
"""
from pathlib import Path
import yaml

# env var name the dbt subprocess reads the exchanged Dremio token from.
DREMIO_TOKEN_ENV = "DREMIO_TOKEN"


def _output_for(target_cfg: dict) -> dict:
    engine = target_cfg["engine"]
    if engine == "duckdb":
        out = {"type": "duckdb", "path": target_cfg.get("path", "dev.duckdb")}
        if "schema" in target_cfg:
            out["schema"] = target_cfg["schema"]
        return out
    if engine == "spark":
        return {
            "type": "spark",
            "method": target_cfg.get("method", "thrift"),
            "host": target_cfg["host"],
            "port": target_cfg.get("port", 10000),
            "schema": target_cfg.get("schema", "default"),
        }
    if engine == "dremio":
        # Production Engine: identity supplied at runtime via env var.
        out = {
            "type": "dremio",
            "host": target_cfg["host"],
            "port": target_cfg.get("port", 9047),
            "token": "{{ env_var('" + DREMIO_TOKEN_ENV + "') }}",
            "use_ssl": target_cfg.get("use_ssl", True),
        }
        for k in ("database", "schema", "object_storage_source",
                  "object_storage_path", "dremio_space"):
            if k in target_cfg:
                out[k] = target_cfg[k]
        return out
    raise ValueError(f"unsupported engine: {engine}")


def build_profile(profile_name: str, connections: dict, default_target: str | None = None) -> dict:
    """Build the profiles.yml dict for one Project."""
    outputs = {t: _output_for(cfg) for t, cfg in connections.items()}
    target = default_target or next(iter(connections))
    return {profile_name: {"target": target, "outputs": outputs}}


def write_profiles(worktree: Path, profile_name: str, connections: dict,
                   default_target: str | None = None) -> Path:
    """Render and write profiles.yml into the worktree. Overwrites any existing."""
    worktree = Path(worktree)
    profile = build_profile(profile_name, connections, default_target)
    dest = worktree / "profiles.yml"
    dest.write_text(yaml.safe_dump(profile, sort_keys=False))
    return dest


def resolve_profile_name(worktree: Path) -> str:
    """Read the profile name from dbt_project.yml (profile: -> name: fallback)."""
    dbt_project = Path(worktree) / "dbt_project.yml"
    if not dbt_project.exists():
        raise FileNotFoundError("dbt_project.yml not found")
    data = yaml.safe_load(dbt_project.read_text()) or {}
    name = data.get("profile") or data.get("name")
    if not name:
        raise ValueError("no profile name in dbt_project.yml")
    return name


def read_default_target(worktree: Path, profile_name: str) -> str | None:
    """The active target in the worktree's profiles.yml (None if no file/target).
    Used by the engine gate to resolve the effective target when none is explicit."""
    pf = Path(worktree) / "profiles.yml"
    if not pf.exists():
        return None
    data = yaml.safe_load(pf.read_text()) or {}
    return (data.get(profile_name) or {}).get("target")
