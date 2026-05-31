"""Project Catalog API. Listing is open to any authenticated user;
mutations require the admin role."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, require_role, CurrentUser
from utils import catalog
from utils.audit import audit
from utils.worktree import provision
from utils.profiles import write_profiles, resolve_profile_name
from utils.connections import validate_connections

router = APIRouter()


class CatalogAddRequest(BaseModel):
    name: str
    repo_path: str
    main_branch: str = "main"


class CatalogIdRequest(BaseModel):
    id: str


@router.post("/api/catalog/list")
async def catalog_list(user: CurrentUser = Depends(get_current_user)):
    return catalog.load()


@router.post("/api/catalog/add")
async def catalog_add(req: CatalogAddRequest,
                      user: CurrentUser = Depends(require_role("admin"))):
    entry = catalog.add_entry(req.name, req.repo_path, req.main_branch)
    audit(sub=user.sub, action="catalog_add", target=entry["id"],
          extra={"name": req.name})
    return entry


@router.post("/api/catalog/remove")
async def catalog_remove(req: CatalogIdRequest,
                         user: CurrentUser = Depends(require_role("admin"))):
    catalog.remove_entry(req.id)
    audit(sub=user.sub, action="catalog_remove", target=req.id)
    return {"removed": req.id}


@router.post("/api/open-project")
async def open_project(req: CatalogIdRequest,
                       user: CurrentUser = Depends(get_current_user)):
    entry = catalog.get(req.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Project not found in catalog")
    wt = provision(sub=user.sub, project_id=entry["id"],
                   repo_path=entry["repo_path"], main_branch=entry["main_branch"])
    # Render profiles.yml from the Project's Connection config (issues 11, 12).
    connections = entry.get("connections")
    if connections:
        validate_connections(connections)
        profile_name = resolve_profile_name(wt)
        write_profiles(wt, profile_name, connections)
    audit(sub=user.sub, action="open_project", target=entry["id"])
    return {"path": entry["id"], "worktree": wt, "name": entry.get("name", entry["id"])}
