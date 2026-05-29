from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scheduler_automation.agents import LLMRoleProvider, load_agent_results, run_agent_workflow
from scheduler_automation.development import propose_changes, run_test_command
from scheduler_automation.execution import ExecutionRequest, execute_task
from scheduler_automation.orchestration import run_task_orchestration
from scheduler_automation.project_workspace import load_workspace
from scheduler_automation.requirements import (
    auto_converge_requirements,
    generate_requirement_guidance,
    generate_requirement_guidance_with_llm,
)
from scheduler_automation.workflow import STAGES, WorkflowManager, utc_timestamp

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
_RUNNING_WORKFLOWS: dict[str, asyncio.Task[Any]] = {}


def get_manager() -> WorkflowManager:
    return WorkflowManager(Path.cwd())


class CreateTaskRequest(BaseModel):
    title: str
    request: str = ""
    project_id: str = ""


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
    project_id: str = ""
    requirement_status: str = "drafting"
    requirement_confirmed_at: str = ""


class TaskDetailResponse(BaseModel):
    task_id: str
    title: str
    current_stage: str
    created_at: str
    updated_at: str
    project_id: str = ""
    requirement_status: str = "drafting"
    requirement_confirmed_at: str = ""
    files: dict[str, str]
    journal: str
    workflow_state: dict


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


class ConfirmAndStartRequest(BaseModel):
    summary: str
    instruction: str = ""
    paths: list[str] = []
    test_command: str = ""
    apply_changes: bool = True


class RequirementMessageResponse(BaseModel):
    role: str
    content: str
    created_at: str


class RequirementSessionResponse(BaseModel):
    status: str
    summary: str
    next_action: str
    suggested_summary: str
    messages: list[RequirementMessageResponse]


class ExecuteTaskRequest(BaseModel):
    instruction: str = ""
    paths: list[str] = []
    test_command: str = ""
    apply_changes: bool = True


class ExecuteTaskResponse(BaseModel):
    summary: str
    selected_paths: list[str]
    written: list[str]
    test_command: str
    test_exit_code: int
    test_output: str
    stage: str


class OrchestrateTaskResponse(BaseModel):
    product_status: str
    product_content: str
    product_error: str = ""
    developer_status: str
    developer_content: str
    developer_error: str = ""
    implementation_summary: str
    written: list[str]
    test_command: str
    test_exit_code: int
    test_output: str
    tester_status: str
    tester_content: str
    tester_error: str = ""
    final_stage: str
    release_ready: bool
    fix_rounds: int
    spec_rounds: int
    workflow_state: dict


class WorkflowLaunchResponse(BaseModel):
    task_id: str
    started: bool
    message: str
    workflow_state: dict


def _build_orchestration_response(manager: WorkflowManager, task_id: str, result) -> OrchestrateTaskResponse:
    return OrchestrateTaskResponse(
        product_status=result.product_result.status,
        product_content=result.product_result.content,
        product_error=result.product_result.error,
        developer_status=result.developer_result.status,
        developer_content=result.developer_result.content,
        developer_error=result.developer_result.error,
        implementation_summary=result.execution_result.summary,
        written=result.execution_result.written,
        test_command=result.execution_result.test_command,
        test_exit_code=result.execution_result.test_exit_code,
        test_output=result.execution_result.test_output,
        tester_status=result.tester_result.status,
        tester_content=result.tester_result.content,
        tester_error=result.tester_result.error,
        final_stage=result.final_stage,
        release_ready=result.release_ready,
        fix_rounds=result.fix_rounds,
        spec_rounds=result.spec_rounds,
        workflow_state=asdict(manager.load_workflow_state(task_id)),
    )


async def _run_orchestration(manager: WorkflowManager, task_id: str, req: ExecuteTaskRequest):
    async def _proposal(instruction: str, paths: list[str], project_id: str):
        workspace = load_workspace(Path.cwd(), project_id)
        if workspace is None or not workspace.exists():
            raise ValueError("Project workspace is not configured or does not exist.")
        return await propose_changes(workspace, instruction, paths)

    def _test_runner(project_id: str, command: str):
        workspace = load_workspace(Path.cwd(), project_id)
        if workspace is None or not workspace.exists():
            raise ValueError("Project workspace is not configured or does not exist.")
        return run_test_command(workspace, command)

    return await run_task_orchestration(
        manager,
        task_id,
        LLMRoleProvider(),
        ExecutionRequest(
            instruction=req.instruction,
            paths=req.paths,
            test_command=req.test_command,
            apply_changes=req.apply_changes,
        ),
        _proposal,
        _test_runner,
    )


def _build_launch_response(
    manager: WorkflowManager,
    task_id: str,
    *,
    started: bool,
    message: str,
) -> WorkflowLaunchResponse:
    return WorkflowLaunchResponse(
        task_id=task_id,
        started=started,
        message=message,
        workflow_state=asdict(manager.load_workflow_state(task_id)),
    )


async def _run_orchestration_background(task_id: str, req: ExecuteTaskRequest) -> None:
    manager = get_manager()
    try:
        await _run_orchestration(manager, task_id, req)
    except Exception as exc:
        metadata, _ = manager.get_task(task_id)
        state = manager.load_workflow_state(task_id)
        state.status = "needs_attention"
        state.current_stage = metadata.current_stage
        state.release_ready = False
        state.requires_human_review = True
        state.last_error = str(exc)
        state.release_gate_status = "blocked"
        state.release_gate_reason = str(exc)
        state.updated_at = utc_timestamp()
        manager.save_workflow_state(task_id, state)
        manager.append_log(task_id, metadata.current_stage, f"自动流程后台执行失败：{exc}")
    finally:
        _RUNNING_WORKFLOWS.pop(task_id, None)


def _start_orchestration_background(task_id: str, req: ExecuteTaskRequest) -> bool:
    running = _RUNNING_WORKFLOWS.get(task_id)
    if running is not None and not running.done():
        return False

    manager = get_manager()
    metadata, _ = manager.get_task(task_id)
    state = manager.load_workflow_state(task_id)
    state.status = "queued"
    state.current_stage = metadata.current_stage
    state.release_ready = False
    state.requires_human_review = False
    state.last_error = ""
    state.updated_at = utc_timestamp()
    manager.save_workflow_state(task_id, state)
    manager.append_log(task_id, metadata.current_stage, "自动流程已在后台启动")
    _RUNNING_WORKFLOWS[task_id] = asyncio.create_task(_run_orchestration_background(task_id, req))
    return True


@router.get("/", response_model=list[TaskResponse])
def list_tasks():
    manager = get_manager()
    tasks = manager.list_tasks()
    return [TaskResponse(**asdict(t)) for t in tasks]


@router.post("/", response_model=TaskResponse)
def create_task(req: CreateTaskRequest):
    manager = get_manager()
    metadata = manager.create_task(req.title, req.request, project_id=req.project_id)
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
        project_id=metadata.project_id,
        requirement_status=metadata.requirement_status,
        requirement_confirmed_at=metadata.requirement_confirmed_at,
        files=files,
        journal=journal,
        workflow_state=asdict(manager.load_workflow_state(task_id)),
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
        next_action=session.next_action,
        suggested_summary=session.suggested_summary,
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
        next_action=session.next_action,
        suggested_summary=session.suggested_summary,
        messages=[RequirementMessageResponse(**asdict(message)) for message in session.messages],
    )


@router.post("/{task_id}/requirements/next-question", response_model=RequirementSessionResponse)
async def add_product_manager_question(task_id: str):
    manager = get_manager()
    try:
        session = await generate_requirement_guidance(manager, task_id, generate_requirement_guidance_with_llm)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RequirementSessionResponse(
        status=session.status,
        summary=session.summary,
        next_action=session.next_action,
        suggested_summary=session.suggested_summary,
        messages=[RequirementMessageResponse(**asdict(message)) for message in session.messages],
    )


@router.post("/{task_id}/requirements/auto-refine", response_model=RequirementSessionResponse)
async def auto_refine_requirements(task_id: str):
    manager = get_manager()
    try:
        session = await auto_converge_requirements(manager, task_id, generate_requirement_guidance_with_llm)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RequirementSessionResponse(
        status=session.status,
        summary=session.summary,
        next_action=session.next_action,
        suggested_summary=session.suggested_summary,
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


@router.post("/{task_id}/requirements/confirm-and-start", response_model=WorkflowLaunchResponse)
async def confirm_requirements_and_start(task_id: str, req: ConfirmAndStartRequest):
    manager = get_manager()
    try:
        manager.confirm_requirements(task_id, req.summary)
        started = _start_orchestration_background(
            task_id,
            ExecuteTaskRequest(
                instruction=req.instruction,
                paths=req.paths,
                test_command=req.test_command,
                apply_changes=req.apply_changes,
            ),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _build_launch_response(
        manager,
        task_id,
        started=started,
        message="需求已确认，自动流程已在后台启动。" if started else "自动流程已在后台运行，请等待当前执行完成。",
    )


@router.post("/{task_id}/requirements/reopen", response_model=TaskResponse)
def reopen_requirements(task_id: str):
    manager = get_manager()
    try:
        metadata = manager.reopen_requirements(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
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


@router.post("/{task_id}/execute", response_model=ExecuteTaskResponse)
async def execute_task_implementation(task_id: str, req: ExecuteTaskRequest):
    manager = get_manager()

    async def _proposal(instruction: str, paths: list[str], project_id: str):
        workspace = load_workspace(Path.cwd(), project_id)
        if workspace is None or not workspace.exists():
            raise ValueError("Project workspace is not configured or does not exist.")
        return await propose_changes(workspace, instruction, paths)

    def _test_runner(project_id: str, command: str):
        workspace = load_workspace(Path.cwd(), project_id)
        if workspace is None or not workspace.exists():
            raise ValueError("Project workspace is not configured or does not exist.")
        return run_test_command(workspace, command)

    try:
        result = await execute_task(
            manager,
            task_id,
            ExecutionRequest(
                instruction=req.instruction,
                paths=req.paths,
                test_command=req.test_command,
                apply_changes=req.apply_changes,
            ),
            _proposal,
            _test_runner,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ExecuteTaskResponse(
        summary=result.summary,
        selected_paths=result.selected_paths,
        written=result.written,
        test_command=result.test_command,
        test_exit_code=result.test_exit_code,
        test_output=result.test_output,
        stage=result.stage,
    )


@router.post("/{task_id}/orchestrate", response_model=WorkflowLaunchResponse)
async def orchestrate_task(task_id: str, req: ExecuteTaskRequest):
    manager = get_manager()
    try:
        started = _start_orchestration_background(task_id, req)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _build_launch_response(
        manager,
        task_id,
        started=started,
        message="自动流程已在后台启动。" if started else "自动流程已在后台运行，请等待当前执行完成。",
    )
