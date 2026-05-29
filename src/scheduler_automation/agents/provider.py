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
        "你是资深产品经理。请使用简体中文输出产品规划，内容至少包含：目标、用户流程、范围、非目标、验收标准、风险。"
        "内容要具体、简洁、可执行，直接用于写入 spec.md。"
    ),
    "developer": (
        "你是资深软件开发工程师。请使用简体中文输出实施方案，内容至少包含：涉及文件、实现策略、关键技术决策、"
        "测试方案、回滚说明。内容要具体、可执行，直接用于写入 implementation.md。"
    ),
    "tester": (
        "你是资深测试工程师。先输出一个 JSON 对象，再补充简短中文说明。"
        'JSON 格式固定为：{"summary":"...","blocking":true,"severity":"low|medium|high",'
        '"recommended_action":"release|fix|spec","issues":[{"title":"...","severity":"low|medium|high","blocking":true,'
        '"category":"functionality|regression|requirements|test_env","evidence":"..."}]}. '
        "issues 可以为空数组。blocking 表示是否阻塞发布。recommended_action 表示建议流转方向。"
        "如果存在高风险问题，请明确写进 issues。JSON 后面可以补充少量中文评审说明，供写入 review.md。"
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
