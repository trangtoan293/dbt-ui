"""Workspace API routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user, CurrentUser
from utils import workspace

router = APIRouter()


class CreateWorkspaceRequest(BaseModel):
    name: str
    adapter: str


class WorkspaceIdRequest(BaseModel):
    id: str


class UpdateConnectionsRequest(BaseModel):
    id: str
    connections: dict


@router.post("/api/workspace/list")
async def workspace_list(user: CurrentUser = Depends(get_current_user)):
    return workspace.list_workspaces(user.sub)


@router.post("/api/workspace/create")
async def workspace_create(
    req: CreateWorkspaceRequest,
    user: CurrentUser = Depends(get_current_user)
):
    ws = workspace.create_workspace(user.sub, req.name, req.adapter)
    return ws


@router.post("/api/workspace/get")
async def workspace_get(
    req: WorkspaceIdRequest,
    user: CurrentUser = Depends(get_current_user)
):
    ws = workspace.get_workspace(user.sub, req.id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "id": ws["id"],
        "name": ws["name"],
        "adapter": ws.get("adapter"),
        "connections": ws.get("connections", {}),
    }


@router.post("/api/workspace/open")
async def workspace_open(
    req: WorkspaceIdRequest,
    user: CurrentUser = Depends(get_current_user)
):
    ws = workspace.get_workspace(user.sub, req.id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    relative_path = f"workspaces/{ws['id']}"
    return {
        "path": relative_path,
        "name": ws["name"]
    }


@router.post("/api/workspace/delete")
async def workspace_delete(
    req: WorkspaceIdRequest,
    user: CurrentUser = Depends(get_current_user)
):
    workspace.delete_workspace(user.sub, req.id)
    return {"deleted": req.id}


@router.post("/api/workspace/update-connections")
async def workspace_update_connections(
    req: UpdateConnectionsRequest,
    user: CurrentUser = Depends(get_current_user)
):
    workspace.update_connections(user.sub, req.id, req.connections)
    return {"success": True}
