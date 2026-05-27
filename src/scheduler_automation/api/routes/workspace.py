from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


def get_workspace() -> Workspace:
    root = os.environ.get("SCHEDULER_PROJECT_ROOT", "/workspace/project")
    return Workspace(Path(root))


@router.get("/", response_model=WorkspaceInfo)
def workspace_info():
    workspace = get_workspace()
    return WorkspaceInfo(configured=workspace.exists(), root=str(workspace.root))


@router.get("/tree", response_model=list[WorkspaceItemResponse])
def workspace_tree():
    workspace = get_workspace()
    if not workspace.exists():
        return []
    return [WorkspaceItemResponse(**item) for item in workspace.tree()]


@router.get("/file", response_model=WorkspaceFileResponse)
def workspace_file(path: str):
    workspace = get_workspace()
    if not workspace.exists():
        raise HTTPException(status_code=404, detail="项目目录未配置或不存在")
    try:
        return WorkspaceFileResponse(**workspace.read_file(path))
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
