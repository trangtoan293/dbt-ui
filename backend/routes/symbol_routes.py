"""Autocomplete symbol endpoint (issue 16): model/source/macro names from the
Project's manifest.json."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user, CurrentUser
from utils.user_paths import resolve_under_root
from utils.dbt_utils import parse_dbt_manifest
from utils.manifest_symbols import extract_symbols

router = APIRouter()


class ProjectPathRequest(BaseModel):
    path: str


@router.post("/api/manifest-symbols")
async def manifest_symbols(req: ProjectPathRequest, user: CurrentUser = Depends(get_current_user)):
    worktree = resolve_under_root(user.sub, req.path)
    manifest = parse_dbt_manifest(worktree)
    if not manifest:
        return {"models": [], "sources": [], "macros": [], "compiled": False}
    return {**extract_symbols(manifest), "compiled": True}
