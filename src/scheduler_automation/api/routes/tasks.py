from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scheduler_automation.agents import LLMRoleProvider, load_agent_results, run_agent_workflow
from scheduler_automation.workflow import STAGES, WorkflowManager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_manager() -> WorkflowManager:
    return WorkflowManager(Path.cwd())


class CreateTaskRequest(BaseModel):
    title: str
    request: str = ""


class AdvanceTaskRequest(BaseModel):
    stage: str


class LogTaskRequest(BaseModel):
    stage: str
    message: str


class TaskResponse(BaseModel):
    task_id: str
    title: str
    current_stage: str
    created_at: str
    updated_at: str
    requirement_status: str = "drafting"
    requirement_confirmed_at: str = ""


class TaskDetailResponse(BaseModel):
    task_id: str
    title: str
    current_stage: str
    created_at: str
    updated_at: str
    files: dict[str, str]
    journal: str


class AgentResultResponse(BaseModel):
    role: str
    status: str
    content: str
    error: str = ""


class RequirementMessageRequest(BaseModel):
    role: str
    content: str


class RequirementConfirmRequest(BaseModel):
    summary: str


class RequirementMessageResponse(BaseModel):
    role: str
    content: str
    created_at: str


class RequirementSessionResponse(BaseModel):
    status: str
    summary: str
    messages: list[RequirementMessageResponse]


@router.get("/", response_model=list[TaskResponse])
def list_tasks():
    manager = get_manager()
    tasks = manager.list_tasks()
    return [TaskResponse(**asdict(t)) for t in tasks]


@router.post("/", response_model=TaskResponse)
def create_task(req: CreateTaskRequest):
    manager = get_manager()
    metadata = manager.create_task(req.title, req.request)
    return TaskResponse(**asdict(metadata))


@router.get("/{task_id}", response_model=TaskDetailResponse)
def get_task(task_id: str):
    manager = get_manager()
    try:
        metadata, task_dir = manager.get_task(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    files: dict[str, str] = {}
    for f in sorted(task_dir.iterdir()):
        if f.is_file() and f.name != "metadata.json" and f.name != "journal.md":
            files[f.name] = f.read_text(encoding="utf-8")

    journal_path = task_dir / "journal.md"
    journal = journal_path.read_text(encoding="utf-8") if journal_path.exists() else ""

    return TaskDetailResponse(
        task_id=metadata.task_id,
        title=metadata.title,
        current_stage=metadata.current_stage,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
        files=files,
        journal=journal,
    )


@router.get("/{task_id}/agents", response_model=list[AgentResultResponse])
def get_agents(task_id: str):
    manager = get_manager()
    try:
        results = load_agent_results(manager, task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return [AgentResultResponse(**result.to_dict()) for result in results]


@router.get("/{task_id}/requirements", response_model=RequirementSessionResponse)
def get_requirements(task_id: str):
    manager = get_manager()
    try:
        session = manager.load_requirement_session(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return RequirementSessionResponse(
        status=session.status,
        summary=session.summary,
        messages=[RequirementMessageResponse(**asdict(message)) for message in session.messages],
    )


@router.post("/{task_id}/requirements/messages", response_model=RequirementSessionResponse)
def add_requirement_message(task_id: str, req: RequirementMessageRequest):
    manager = get_manager()
    try:
        session = manager.append_requirement_message(task_id, req.role, req.content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RequirementSessionResponse(
        status=session.status,
        summary=session.summary,
        messages=[RequirementMessageResponse(**asdict(message)) for message in session.messages],
    )


@router.post("/{task_id}/requirements/confirm", response_model=TaskResponse)
def confirm_requirements(task_id: str, req: RequirementConfirmRequest):
    manager = get_manager()
    try:
        metadata = manager.confirm_requirements(task_id, req.summary)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return TaskResponse(**asdict(metadata))


@router.post("/{task_id}/agents/run", response_model=list[AgentResultResponse])
async def run_agents(task_id: str):
    manager = get_manager()
    try:
        manager.get_task(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    results = await run_agent_workflow(manager, task_id, LLMRoleProvider())
    return [AgentResultResponse(**result.to_dict()) for result in results]


@router.post("/{task_id}/advance", response_model=TaskResponse)
def advance_task(task_id: str, req: AdvanceTaskRequest):
    manager = get_manager()
    if req.stage not in STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage '{req.stage}'. Expected: {', '.join(STAGES)}")
    try:
        metadata = manager.advance_task(task_id, req.stage)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return TaskResponse(**asdict(metadata))


@router.post("/{task_id}/log", response_model=TaskResponse)
def log_task(task_id: str, req: LogTaskRequest):
    manager = get_manager()
    if req.stage not in STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage '{req.stage}'. Expected: {', '.join(STAGES)}")
    try:
        manager.append_log(task_id, req.stage, req.message)
        metadata, _ = manager.get_task(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return TaskResponse(**asdict(metadata))


@router.put("/{task_id}/files/{file_name}")
def update_task_file(task_id: str, file_name: str, body: dict[str, str]):
    manager = get_manager()
    try:
        _, task_dir = manager.get_task(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    safe_name = Path(file_name).name  # prevent path traversal
    file_path = task_dir / safe_name
    file_path.write_text(body.get("content", ""), encoding="utf-8")
    return {"status": "ok"}
