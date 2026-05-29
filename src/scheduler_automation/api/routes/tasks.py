from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scheduler_automation.agents import LLMRoleProvider, load_agent_results, run_agent_workflow
from scheduler_automation.development import propose_changes, run_test_command
from scheduler_automation.execution import ExecutionRequest, execute_task
from scheduler_automation.orchestration import run_task_orchestration
from scheduler_automation.project_workspace import load_workspace
from scheduler_automation.requirements import generate_requirement_question, generate_requirement_question_with_llm
from scheduler_automation.workflow import STAGES, WorkflowManager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


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


class RequirementMessageResponse(BaseModel):
    role: str
    content: str
    created_at: str


class RequirementSessionResponse(BaseModel):
    status: str
    summary: str
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


@router.post("/{task_id}/requirements/next-question", response_model=RequirementSessionResponse)
async def add_product_manager_question(task_id: str):
    manager = get_manager()
    try:
        session = await generate_requirement_question(manager, task_id, generate_requirement_question_with_llm)
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


@router.post("/{task_id}/orchestrate", response_model=OrchestrateTaskResponse)
async def orchestrate_task(task_id: str, req: ExecuteTaskRequest):
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
        result = await run_task_orchestration(
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
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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
