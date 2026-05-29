from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scheduler_automation.requirements import RequirementGuidance, auto_converge_requirements, generate_requirement_guidance
from scheduler_automation.workflow import WorkflowManager


class RequirementQuestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_requirement_guidance_appends_product_manager_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            task = manager.create_task("Build chat flow", "Need a chat workflow")

            async def ask(_title: str, _session):
                return RequirementGuidance(
                    question="这个功能需要支持哪些失败场景？",
                    next_action="ask",
                    suggested_summary="",
                )

            session = await generate_requirement_guidance(manager, task.task_id, ask)

            self.assertEqual(session.messages[-1].role, "product_manager")
            self.assertEqual(session.messages[-1].content, "这个功能需要支持哪些失败场景？")
            self.assertEqual(session.next_action, "ask")
            self.assertEqual(session.suggested_summary, "")

    async def test_generate_requirement_guidance_can_mark_ready_to_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            task = manager.create_task("Build chat flow", "Need a chat workflow")

            async def ask(_title: str, _session):
                return RequirementGuidance(
                    question="需求信息已经足够，请确认摘要。",
                    next_action="confirm",
                    suggested_summary="先做产品经理追问，再确认需求，再进入自动流程。",
                )

            session = await generate_requirement_guidance(manager, task.task_id, ask)

            self.assertEqual(session.next_action, "confirm")
            self.assertIn("先做产品经理追问", session.suggested_summary)

    async def test_generate_requirement_guidance_rejects_confirmed_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            task = manager.create_task("Build chat flow", "Need a chat workflow")
            manager.confirm_requirements(task.task_id, "Build a PM-led requirement confirmation flow.")

            async def ask(_title: str, _session):
                return RequirementGuidance(
                    question="这个问题不应该再被调用",
                    next_action="ask",
                    suggested_summary="",
                )

            with self.assertRaisesRegex(ValueError, "already confirmed"):
                await generate_requirement_guidance(manager, task.task_id, ask)

    async def test_auto_converge_requirements_stops_when_ready_to_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            task = manager.create_task("Build chat flow", "Need a chat workflow")
            calls = {"count": 0}

            async def ask(_title: str, _session):
                calls["count"] += 1
                if calls["count"] == 1:
                    return RequirementGuidance(
                        question="需要支持哪些失败场景？",
                        next_action="ask",
                        suggested_summary="",
                    )
                return RequirementGuidance(
                    question="需求信息已经足够，请确认摘要。",
                    next_action="confirm",
                    suggested_summary="先完成需求确认，再自动进入开发测试流程。",
                )

            session = await auto_converge_requirements(manager, task.task_id, ask)

            self.assertEqual(calls["count"], 2)
            self.assertEqual(session.next_action, "confirm")
            self.assertIn("自动进入开发测试流程", session.suggested_summary)
            self.assertEqual(session.messages[-1].content, "需求信息已经足够，请确认摘要。")


if __name__ == "__main__":
    unittest.main()
