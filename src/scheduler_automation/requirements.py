from __future__ import annotations

from typing import Awaitable, Callable

from scheduler_automation.llm.client import LLMClient, get_llm_config
from scheduler_automation.workflow import RequirementSession, WorkflowManager

QuestionFunc = Callable[[str, RequirementSession], Awaitable[str]]


async def generate_requirement_question(
    manager: WorkflowManager,
    task_id: str,
    question_func: QuestionFunc,
) -> RequirementSession:
    metadata, _ = manager.get_task(task_id)
    if metadata.requirement_status == "confirmed":
        raise ValueError("Requirements are already confirmed.")

    session = manager.load_requirement_session(task_id)
    question = (await question_func(metadata.title, session)).strip()
    if not question:
        raise ValueError("Product manager did not return a requirement question.")
    return manager.append_requirement_message(task_id, "product_manager", question)


async def generate_requirement_question_with_llm(task_title: str, session: RequirementSession) -> str:
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
                "你是资深产品经理。请基于当前需求对话，只输出一个下一步最关键的澄清问题。"
                "如果信息已经足够，不要继续发散，直接输出：需求信息已经足够，请确认摘要。"
                "只输出简体中文正文，不要加标题、编号或解释。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"# 任务标题\n{task_title}\n\n"
                f"# 当前摘要\n{summary}\n\n"
                f"# 当前需求对话\n{conversation}\n\n"
                "请给出一个下一步最关键的问题。"
            ),
        },
    ]
    response = await client.chat(messages)
    return (response or "").strip()
