from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from scheduler_automation.agents.provider import AgentProvider, AgentResult, AgentRole
from scheduler_automation.project_workspace import load_workspace
from scheduler_automation.workspace import Workspace
from scheduler_automation.workflow import WorkflowManager

AGENT_ROLES: tuple[AgentRole, ...] = ("product_manager", "developer", "tester")
ROLE_FILES: dict[AgentRole, str] = {
    "product_manager": "spec.md",
    "developer": "implementation.md",
    "tester": "review.md",
}
ROLE_HEADINGS: dict[AgentRole, str] = {
    "product_manager": "产品经理输出",
    "developer": "开发代理输出",
    "tester": "测试代理输出",
}


def load_agent_results(manager: WorkflowManager, task_id: str) -> list[AgentResult]:
    _, task_dir = manager.get_task(task_id)
    results_path = task_dir / "agents.json"
    if not results_path.exists():
        return []
    data = json.loads(results_path.read_text(encoding="utf-8"))
    return [AgentResult.from_dict(item) for item in data.get("results", [])]


async def run_agent_workflow(
    manager: WorkflowManager,
    task_id: str,
    provider: AgentProvider,
) -> list[AgentResult]:
    metadata, task_dir = manager.get_task(task_id)
    task_context = _task_context(manager, metadata.project_id, task_dir)

    results = await asyncio.gather(*(provider.run(role, metadata.title, task_context) for role in AGENT_ROLES))

    for result in results:
        if result.status == "completed":
            _write_role_artifact(task_dir, result)

    _write_agent_results(task_dir, results)
    manager.append_log(task_id, metadata.current_stage, "Agent workflow finished")
    return list(results)


async def run_agent_roles(
    manager: WorkflowManager,
    task_id: str,
    provider: AgentProvider,
    roles: tuple[AgentRole, ...] | list[AgentRole],
) -> list[AgentResult]:
    metadata, task_dir = manager.get_task(task_id)
    existing = {result.role: result for result in load_agent_results(manager, task_id)}
    results: list[AgentResult] = []

    for role in roles:
        task_context = _task_context(manager, metadata.project_id, task_dir)
        result = await provider.run(role, metadata.title, task_context)
        if result.status == "completed":
            _write_role_artifact(task_dir, result)
        existing[role] = result
        results.append(result)

    ordered = [existing[role] for role in AGENT_ROLES if role in existing]
    _write_agent_results(task_dir, ordered)
    manager.append_log(task_id, metadata.current_stage, f"Agent roles finished: {', '.join(roles)}")
    return results


def _write_agent_results(task_dir: Path, results: list[AgentResult]) -> None:
    (task_dir / "agents.json").write_text(
        json.dumps({"results": [result.to_dict() for result in results]}, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _write_role_artifact(task_dir: Path, result: AgentResult) -> None:
    path = task_dir / ROLE_FILES[result.role]
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    heading = ROLE_HEADINGS[result.role]
    if existing.strip():
        content = existing.rstrip() + f"\n\n## {heading}\n\n{result.content.strip()}\n"
    else:
        content = result.content.strip() + "\n"
    path.write_text(content, encoding="utf-8")


def _task_context(manager: WorkflowManager, project_id: str, task_dir: Path) -> str:
    parts: list[str] = []
    for file_name in ("request.md", "spec.md", "implementation.md", "review.md", "fixes.md"):
        path = task_dir / file_name
        if path.exists():
            parts.append(f"## {file_name}\n\n{path.read_text(encoding='utf-8')}")
    workspace = (
        load_workspace(manager.root, project_id)
        if project_id
        else Workspace(Path(os.environ.get("SCHEDULER_PROJECT_ROOT", "/workspace/project")))
    )
    if workspace is not None and workspace.exists():
        parts.append(f"## Project workspace summary\n\n{workspace.summary()}")
    return "\n\n".join(parts)
