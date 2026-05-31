"""Validate and classify Project Connection config (CONTEXT.md -> Connection).

A Connection is secret-free, admin-owned, and per-Project. It is stored in the
Catalog entry under "connections": {target_name: {engine, ...non-secret fields}}.
Per-User credentials (Dremio token) are runtime and NEVER part of this config.
"""
from fastapi import HTTPException

DEV_ENGINES = {"duckdb", "spark"}
PROD_ENGINES = {"dremio"}
ALL_ENGINES = DEV_ENGINES | PROD_ENGINES

# Keys that would carry a secret — forbidden in Connection config.
SECRET_KEYS = {"password", "token", "pat", "secret", "client_secret",
               "private_key", "private_key_path", "access_token", "api_key"}


def validate_connections(block: dict) -> None:
    """Raise HTTPException(400) if the connections block is malformed or holds
    any secret. A valid block maps target_name -> {engine: <known>, ...}."""
    if not isinstance(block, dict) or not block:
        raise HTTPException(status_code=400, detail="connections must be a non-empty object")

    for target, cfg in block.items():
        if not isinstance(cfg, dict):
            raise HTTPException(status_code=400, detail=f"target '{target}' must be an object")
        engine = cfg.get("engine")
        if engine not in ALL_ENGINES:
            raise HTTPException(
                status_code=400,
                detail=f"target '{target}': unknown engine '{engine}' "
                       f"(allowed: {sorted(ALL_ENGINES)})",
            )
        leaked = {k for k in cfg if k.lower() in SECRET_KEYS}
        if leaked:
            raise HTTPException(
                status_code=400,
                detail=f"target '{target}': connection config must not contain "
                       f"secrets {sorted(leaked)} — credentials are per-user and runtime",
            )


def engine_for_target(block: dict, target: str) -> str:
    cfg = block.get(target)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"target '{target}' not configured")
    return cfg["engine"]


def is_production_engine(engine: str) -> bool:
    return engine in PROD_ENGINES
