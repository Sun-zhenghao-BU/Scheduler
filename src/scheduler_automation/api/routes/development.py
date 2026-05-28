from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scheduler_automation.development import (
    DevelopmentCommandError,
    FileChange,
    apply_changes,
    propose_changes,
    run_test_command,
)
from scheduler_automation.project_workspace import load_workspace
from scheduler_automation.workspace import Workspace, WorkspaceAccessError

router = APIRouter(prefix="/api/development", tags=["development"])


class DevelopRequest(BaseModel):
    instruction: str
    paths: list[str] = []
    project_id: str = ""


class TestFixRequest(BaseModel):
    instruction: str = ""
    paths: list[str] = []
    test_command: str
    test_output: str
    project_id: str = ""


class FileChangeResponse(BaseModel):
    path: str
    old_content: str
    new_content: str
    diff: str


class DevelopProposalResponse(BaseModel):
    session_id: str
    summary: str
    changes: list[FileChangeResponse]


class ApplyRequest(BaseModel):
    session_id: str


class ApplyResponse(BaseModel):
    written: list[str]


class TestCommandRequest(BaseModel):
    command: str
    project_id: str = ""


class TestCommandResponse(BaseModel):
    command: str
    exit_code: int
    output: str


def _workspace(project_id: str = "") -> Workspace | None:
    return load_workspace(Path.cwd(), project_id)


def _require_workspace(project_id: str = "") -> Workspace:
    try:
        workspace = _workspace(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    if workspace is None or not workspace.exists():
        raise HTTPException(status_code=404, detail="Project workspace is not configured or does not exist.")
    return workspace


def _sessions_dir() -> Path:
    path = Path.cwd() / "tasks" / ".development_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/propose", response_model=DevelopProposalResponse)
async def propose_development(req: DevelopRequest):
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="Instruction is required.")
    workspace = _require_workspace(req.project_id)
    return await _create_proposal(workspace, req.instruction.strip(), req.paths, req.project_id)


@router.post("/fix", response_model=DevelopProposalResponse)
async def propose_test_fix(req: TestFixRequest):
    if not req.test_output.strip():
        raise HTTPException(status_code=400, detail="Test output is required.")
    workspace = _require_workspace(req.project_id)
    instruction = (
        f"Original instruction: {req.instruction.strip() or 'Fix the failure described in the test output.'}\n\n"
        f"Test command: {req.test_command}\n\n"
        f"Failing test output:\n{req.test_output}"
    )
    return await _create_proposal(workspace, instruction, req.paths, req.project_id)


@router.post("/apply", response_model=ApplyResponse)
def apply_development(req: ApplyRequest):
    session_path = _sessions_dir() / f"{req.session_id}.json"
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Development session not found.")
    data = json.loads(session_path.read_text(encoding="utf-8"))
    changes = [FileChange.from_dict(item) for item in data.get("changes", [])]
    workspace = _require_workspace(str(data.get("project_id", "")))
    try:
        written = apply_changes(workspace, changes)
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ApplyResponse(written=written)


@router.post("/test", response_model=TestCommandResponse)
def run_development_test(req: TestCommandRequest):
    workspace = _require_workspace(req.project_id)
    try:
        result = run_test_command(workspace, req.command)
    except DevelopmentCommandError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Test command was not found in the project environment.")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Test command timed out.")
    return TestCommandResponse(command=result.command, exit_code=result.exit_code, output=result.output)


async def _create_proposal(
    workspace: Workspace,
    instruction: str,
    paths: list[str],
    project_id: str = "",
) -> DevelopProposalResponse:
    if not paths:
        raise HTTPException(status_code=400, detail="Select at least one file to modify.")

    selected_files: list[dict[str, str | int]] = []
    try:
        for path in paths:
            selected_files.append(workspace.read_file(path))
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    summary, changes = await propose_changes(workspace, instruction, [str(item["path"]) for item in selected_files])
    session_id = uuid.uuid4().hex
    payload = {
        "session_id": session_id,
        "summary": summary,
        "project_id": project_id,
        "changes": [change.to_dict() for change in changes],
    }
    (_sessions_dir() / f"{session_id}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return DevelopProposalResponse(
        session_id=session_id,
        summary=summary,
        changes=[FileChangeResponse(**change.to_dict()) for change in changes],
    )

