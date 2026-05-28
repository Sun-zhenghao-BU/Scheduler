from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scheduler_automation.open_roots import configured_open_roots, list_open_root_children
from scheduler_automation.projects import ProjectManager
from scheduler_automation.workflow import WorkflowManager

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_project_manager() -> ProjectManager:
    return ProjectManager(Path.cwd())


def get_workflow_manager() -> WorkflowManager:
    return WorkflowManager(Path.cwd())


class CreateProjectRequest(BaseModel):
    name: str
    root_path: str = ""


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    root_path: str
    created_at: str
    updated_at: str


class ProjectTaskResponse(BaseModel):
    task_id: str
    title: str
    current_stage: str
    created_at: str
    updated_at: str
    project_id: str = ""
    requirement_status: str = "drafting"
    requirement_confirmed_at: str = ""


class PickFolderResponse(BaseModel):
    selected: bool
    path: str


class OpenRootResponse(BaseModel):
    root_id: str
    label: str
    path: str


class OpenRootChildResponse(BaseModel):
    name: str
    path: str
    relative_path: str
    type: str


def pick_windows_folder() -> str:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError("PowerShell is not available.")

    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dialog.Description = '选择项目文件夹'; "
        "$dialog.UseDescriptionForTitle = $true; "
        "$result = $dialog.ShowDialog(); "
        "if ($result -eq [System.Windows.Forms.DialogResult]::OK) { "
        "[Console]::Out.Write($dialog.SelectedPath) }"
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "Folder picker failed.").strip())
    return (completed.stdout or "").strip()


@router.get("/", response_model=list[ProjectResponse])
def list_projects():
    return [ProjectResponse(**asdict(project)) for project in get_project_manager().list_projects()]


@router.post("/", response_model=ProjectResponse)
def create_project(req: CreateProjectRequest):
    try:
        project = get_project_manager().create_project(req.name, req.root_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ProjectResponse(**asdict(project))


@router.post("/pick-folder", response_model=PickFolderResponse)
def pick_folder():
    try:
        selected_path = pick_windows_folder()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return PickFolderResponse(selected=bool(selected_path), path=selected_path)


@router.get("/open-roots", response_model=list[OpenRootResponse])
def open_roots():
    return [OpenRootResponse(**asdict(root)) for root in configured_open_roots()]


@router.get("/open-roots/{root_id}/children", response_model=list[OpenRootChildResponse])
def open_root_children(root_id: str, relative_path: str = ""):
    try:
        children = list_open_root_children(root_id, relative_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Open root '{root_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [OpenRootChildResponse(**item) for item in children]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str):
    try:
        project = get_project_manager().get_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return ProjectResponse(**asdict(project))


@router.get("/{project_id}/tasks", response_model=list[ProjectTaskResponse])
def list_project_tasks(project_id: str):
    try:
        get_project_manager().get_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    tasks = get_workflow_manager().list_tasks(project_id=project_id)
    return [ProjectTaskResponse(**asdict(task)) for task in tasks]
