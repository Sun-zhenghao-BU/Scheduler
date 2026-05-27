from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Protocol

from scheduler_automation.llm.client import LLMClient

AgentRole = Literal["product_manager", "developer", "tester"]
AgentStatus = Literal["completed", "failed"]


@dataclass
class AgentResult:
    role: AgentRole
    status: AgentStatus
    content: str
    error: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "AgentResult":
        return cls(
            role=data["role"],  # type: ignore[arg-type]
            status=data["status"],  # type: ignore[arg-type]
            content=data.get("content", ""),
            error=data.get("error", ""),
        )


class AgentProvider(Protocol):
    async def run(self, role: AgentRole, task_title: str, task_context: str) -> AgentResult:
        ...


ROLE_PROMPTS: dict[AgentRole, str] = {
    "product_manager": (
        "你是资深产品经理。请使用简体中文输出产品规划，包含：目标、用户流程、范围、"
        "验收标准、风险和发布说明。内容要具体、简洁、可执行。"
    ),
    "developer": (
        "你是资深软件开发工程师。请使用简体中文输出实施方案，包含：架构、需要修改的文件、"
        "API/数据契约、分步实施方案和回滚说明。内容要具体、可执行。"
    ),
    "tester": (
        "你是资深测试工程师。请使用简体中文输出测试方案，包含：功能测试、API 测试、"
        "回归风险、边界场景、手工验收和 Docker 部署检查。内容要具体、可执行。"
    ),
}


class LLMRoleProvider:
    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or LLMClient()

    async def run(self, role: AgentRole, task_title: str, task_context: str) -> AgentResult:
        messages = [
            {"role": "system", "content": ROLE_PROMPTS[role]},
            {
                "role": "user",
                "content": f"# Task\n\n{task_title}\n\n# Current context\n\n{task_context}",
            },
        ]
        try:
            content = await self.client.chat(messages)
            return AgentResult(role=role, status="completed", content=content or "")
        except Exception as exc:
            return AgentResult(role=role, status="failed", content="", error=str(exc))
