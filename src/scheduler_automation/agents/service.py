from __future__ import annotations

import asyncio
import json

from scheduler_automation.agents.provider import AgentProvider, AgentResult, AgentRole
from scheduler_automation.workflow import WorkflowManager

AGENT_ROLES: tuple[AgentRole, ...] = ("product_manager", "developer", "tester")
ROLE_FILES: dict[AgentRole, str] = {
    "product_manager": "spec.md",
    "developer": "implementation.md",
    "tester": "review.md",
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
    task_context = _task_context(task_dir)

    results = await asyncio.gather(
        *(provider.run(role, metadata.title, task_context) for role in AGENT_ROLES)
    )

    for result in results:
        if result.status == "completed":
            (task_dir / ROLE_FILES[result.role]).write_text(result.content, encoding="utf-8")

    (task_dir / "agents.json").write_text(
        json.dumps({"results": [result.to_dict() for result in results]}, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    manager.append_log(task_id, metadata.current_stage, "代理工作流已完成")
    return list(results)


def _task_context(task_dir) -> str:
    parts: list[str] = []
    for file_name in ("request.md", "spec.md", "implementation.md", "review.md"):
        path = task_dir / file_name
        if path.exists():
            parts.append(f"## {file_name}\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)
