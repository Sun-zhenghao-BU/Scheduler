from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from scheduler_automation.llm.client import LLMClient, get_llm_config
from scheduler_automation.workflow import RequirementSession, WorkflowManager


@dataclass
class RequirementGuidance:
    question: str
    next_action: str
    suggested_summary: str


GuidanceFunc = Callable[[str, RequirementSession], Awaitable[RequirementGuidance]]


async def generate_requirement_guidance(
    manager: WorkflowManager,
    task_id: str,
    guidance_func: GuidanceFunc,
) -> RequirementSession:
    metadata, _ = manager.get_task(task_id)
    if metadata.requirement_status == "confirmed":
        raise ValueError("Requirements are already confirmed.")

    session = manager.load_requirement_session(task_id)
    guidance = await guidance_func(metadata.title, session)
    question = guidance.question.strip()
    if not question:
        raise ValueError("Product manager did not return a requirement question.")

    updated = manager.append_requirement_message(task_id, "product_manager", question)
    return manager.update_requirement_guidance(
        task_id,
        next_action=guidance.next_action or "ask",
        suggested_summary=guidance.suggested_summary,
    )


async def generate_requirement_guidance_with_llm(task_title: str, session: RequirementSession) -> RequirementGuidance:
    config = get_llm_config()
    client = LLMClient(config)
    ok, message = client.validate_config()
    if not ok:
        raise ValueError(message)

    conversation = "\n".join(f"- {item.role}: {item.content}" for item in session.messages) or "- 暂无需求对话"
    summary = session.summary or "暂无确认摘要"
    messages = [
        {
            "role": "system",
            "content": (
                "你是资深产品经理。请判断当前需求是继续追问，还是已经足够确认。"
                '先输出 JSON：{"next_action":"ask|confirm","question":"...","suggested_summary":"..."}。'
                "如果 next_action 是 ask，question 必须是下一个最关键的问题，suggested_summary 可以为空。"
                "如果 next_action 是 confirm，question 必须明确告诉用户信息已足够，可以确认摘要，"
                "同时 suggested_summary 必须给出一段可直接确认的中文摘要。"
                "JSON 后面不要追加任何解释。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"# 任务标题\n{task_title}\n\n"
                f"# 当前摘要\n{summary}\n\n"
                f"# 当前需求对话\n{conversation}\n\n"
                "请给出下一步建议。"
            ),
        },
    ]
    response = (await client.chat(messages) or "").strip()
    return _parse_requirement_guidance(response)


def _parse_requirement_guidance(content: str) -> RequirementGuidance:
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return RequirementGuidance(question=content.strip(), next_action="ask", suggested_summary="")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return RequirementGuidance(question=content.strip(), next_action="ask", suggested_summary="")

    next_action = str(data.get("next_action", "ask")).strip() or "ask"
    if next_action not in {"ask", "confirm"}:
        next_action = "ask"
    question = str(data.get("question", "")).strip()
    suggested_summary = str(data.get("suggested_summary", "")).strip()
    return RequirementGuidance(
        question=question,
        next_action=next_action,
        suggested_summary=suggested_summary,
    )
