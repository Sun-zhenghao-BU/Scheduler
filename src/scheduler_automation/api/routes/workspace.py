from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scheduler_automation.project_workspace import load_workspace
from scheduler_automation.workspace import Workspace, WorkspaceAccessError

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


class WorkspaceInfo(BaseModel):
    configured: bool
    root: str


class WorkspaceItemResponse(BaseModel):
    path: str
    name: str
    type: str


class WorkspaceFileResponse(BaseModel):
    path: str
    content: str
    size: int


def get_workspace(project_id: str = "") -> Workspace | None:
    return load_workspace(Path.cwd(), project_id)


@router.get("/", response_model=WorkspaceInfo)
def workspace_info(project_id: str = ""):
    try:
        workspace = get_workspace(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    if workspace is None:
        return WorkspaceInfo(configured=False, root="")
    return WorkspaceInfo(configured=workspace.exists(), root=str(workspace.root))


@router.get("/tree", response_model=list[WorkspaceItemResponse])
def workspace_tree(project_id: str = ""):
    try:
        workspace = get_workspace(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    if workspace is None or not workspace.exists():
        return []
    return [WorkspaceItemResponse(**item) for item in workspace.tree()]


@router.get("/file", response_model=WorkspaceFileResponse)
def workspace_file(path: str, project_id: str = ""):
    try:
        workspace = get_workspace(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    if workspace is None or not workspace.exists():
        raise HTTPException(status_code=404, detail="Project workspace is not configured or does not exist.")
    try:
        return WorkspaceFileResponse(**workspace.read_file(path))
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
