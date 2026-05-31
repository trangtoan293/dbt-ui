"""Project Connection config endpoints (issue 12).

Get: any authenticated user. Set: admin only. Set-target: re-renders the calling
user's worktree profiles.yml with a new default target. All config is secret-free.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_user, require_role, CurrentUser
from utils import catalog
from utils.connections import validate_connections, engine_for_target, is_production_engine
from utils.profiles import write_profiles, resolve_profile_name
from utils.input_validation import validate_dbt_target
from utils.user_paths import resolve_under_root
from utils.audit import audit

router = APIRouter()


class ProjectIdRequest(BaseModel):
    id: str


class SetConnectionsRequest(BaseModel):
    id: str
    connections: dict


class SetTargetRequest(BaseModel):
    id: str
    target: str


@router.post("/api/connections/get")
async def get_connections(req: ProjectIdRequest, user: CurrentUser = Depends(get_current_user)):
    entry = catalog.get(req.id)
    if entry is None:
        return {"connections": {}}
    return {"connections": entry.get("connections", {})}


@router.post("/api/connections/set")
async def set_connections(req: SetConnectionsRequest,
                          user: CurrentUser = Depends(require_role("admin"))):
    validate_connections(req.connections)
    entry = catalog.get(req.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="project not in catalog")
    catalog.set_connections(req.id, req.connections)
    audit(sub=user.sub, action="connections_set", target=req.id,
          extra={"targets": list(req.connections.keys())})
    return {"ok": True}


@router.post("/api/connections/set-target")
async def set_target(req: SetTargetRequest, user: CurrentUser = Depends(get_current_user)):
    target = validate_dbt_target(req.target)
    entry = catalog.get(req.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="project not in catalog")
    connections = entry.get("connections", {})
    engine = engine_for_target(connections, target)  # 404 if target unknown
    # Non-maintainers must not make the Production Engine their default target
    # (it would become the implicit engine for untargeted runs/preview).
    if is_production_engine(engine) and "maintainer" not in user.roles:
        raise HTTPException(status_code=403,
                            detail="Only maintainers may set a Production Engine target as default")
    worktree = resolve_under_root(user.sub, req.id)
    profile_name = resolve_profile_name(worktree)
    write_profiles(worktree, profile_name, connections, default_target=target)
    audit(sub=user.sub, action="set_target", target=req.id, extra={"target": target})
    return {"ok": True, "worktree": str(worktree), "target": target}
