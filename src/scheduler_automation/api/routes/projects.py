from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
