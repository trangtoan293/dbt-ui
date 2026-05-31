"""Project Catalog API. Listing is open to any authenticated user;
mutations require the admin role."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user, require_role, CurrentUser
from utils import catalog
from utils.audit import audit

router = APIRouter()


class CatalogAddRequest(BaseModel):
    name: str
    repo_path: str
    main_branch: str = "main"


class CatalogIdRequest(BaseModel):
    id: str


@router.post("/api/catalog/list")
async def catalog_list(user: CurrentUser = Depends(get_current_user)):
    return catalog.list_entries()


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
