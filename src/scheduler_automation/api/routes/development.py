from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scheduler_automation.development import (
    DevelopmentCommandError,
    FileChange,
    apply_changes,
    build_change,
    run_test_command,
)
from scheduler_automation.llm.client import LLMClient, get_llm_config
from scheduler_automation.workspace import Workspace, WorkspaceAccessError

router = APIRouter(prefix="/api/development", tags=["development"])


class DevelopRequest(BaseModel):
    instruction: str
    paths: list[str] = []


class TestFixRequest(BaseModel):
    instruction: str = ""
    paths: list[str] = []
    test_command: str
    test_output: str


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


class TestCommandResponse(BaseModel):
    command: str
    exit_code: int
    output: str


def _workspace() -> Workspace:
    return Workspace(Path(os.environ.get("SCHEDULER_PROJECT_ROOT", "/workspace/project")))


def _sessions_dir() -> Path:
    path = Path.cwd() / "tasks" / ".development_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/propose", response_model=DevelopProposalResponse)
async def propose_development(req: DevelopRequest):
    workspace = _workspace()
    if not workspace.exists():
        raise HTTPException(status_code=404, detail="项目目录未配置或不存在")
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="请输入修改需求")
    return await _create_proposal(workspace, req.instruction.strip(), req.paths)


@router.post("/fix", response_model=DevelopProposalResponse)
async def propose_test_fix(req: TestFixRequest):
    workspace = _workspace()
    if not workspace.exists():
        raise HTTPException(status_code=404, detail="项目目录未配置或不存在")
    if not req.test_output.strip():
        raise HTTPException(status_code=400, detail="缺少测试失败输出")
    instruction = (
        f"原始需求：{req.instruction.strip() or '根据测试失败修复问题'}\n\n"
        f"测试命令：{req.test_command}\n\n"
        f"测试失败输出：\n{req.test_output}"
    )
    return await _create_proposal(workspace, instruction, req.paths)


@router.post("/apply", response_model=ApplyResponse)
def apply_development(req: ApplyRequest):
    session_path = _sessions_dir() / f"{req.session_id}.json"
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="修改会话不存在")
    data = json.loads(session_path.read_text(encoding="utf-8"))
    changes = [FileChange.from_dict(item) for item in data.get("changes", [])]
    try:
        written = apply_changes(_workspace(), changes)
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ApplyResponse(written=written)


@router.post("/test", response_model=TestCommandResponse)
def run_development_test(req: TestCommandRequest):
    workspace = _workspace()
    if not workspace.exists():
        raise HTTPException(status_code=404, detail="项目目录未配置或不存在")
    try:
        result = run_test_command(workspace, req.command)
    except DevelopmentCommandError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="测试命令不存在，请确认项目环境已安装")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="测试命令执行超时")
    return TestCommandResponse(command=result.command, exit_code=result.exit_code, output=result.output)


async def _create_proposal(workspace: Workspace, instruction: str, paths: list[str]) -> DevelopProposalResponse:
    if not paths:
        raise HTTPException(status_code=400, detail="请至少选择一个要修改的文件")

    selected_files: list[dict[str, str | int]] = []
    try:
        for path in paths:
            selected_files.append(workspace.read_file(path))
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    raw = await _ask_llm(instruction, selected_files)
    summary, changes = _parse_llm_changes(workspace, raw)
    session_id = uuid.uuid4().hex
    payload = {
        "session_id": session_id,
        "summary": summary,
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


async def _ask_llm(instruction: str, selected_files: list[dict[str, str | int]]) -> str:
    config = get_llm_config()
    if not config["api_key"]:
        raise HTTPException(status_code=400, detail="请先在系统设置中配置模型 API")

    files_text = "\n\n".join(
        f"## {item['path']}\n\n```text\n{item['content']}\n```"
        for item in selected_files
    )
    messages = [
        {
            "role": "system",
            "content": (
                "你是代码修改代理。你只能基于用户提供的文件内容生成修改。"
                "必须只返回 JSON，不要返回 Markdown。JSON 格式："
                '{"summary":"修改摘要","files":[{"path":"相对路径","content":"完整的新文件内容"}]}。'
                "content 必须是完整文件内容，不是片段。"
            ),
        },
        {
            "role": "user",
            "content": f"修改需求：{instruction}\n\n当前文件：\n\n{files_text}",
        },
    ]
    return await LLMClient(config).chat(messages)


def _parse_llm_changes(workspace: Workspace, raw: str) -> tuple[str, list[FileChange]]:
    text = _extract_json(raw)
    data: dict[str, Any] = json.loads(text)
    summary = str(data.get("summary", "已生成修改方案"))
    changes: list[FileChange] = []
    for item in data.get("files", []):
        path = str(item["path"])
        content = str(item["content"])
        changes.append(build_change(workspace, path, content))
    if not changes:
        raise HTTPException(status_code=400, detail="模型没有返回可应用的文件修改")
    return summary, changes


def _extract_json(raw: str) -> str:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        return fenced.group(1).strip()
    return text
