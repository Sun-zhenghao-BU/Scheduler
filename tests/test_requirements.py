from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scheduler_automation.requirements import generate_requirement_question
from scheduler_automation.workflow import WorkflowManager


class RequirementQuestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_requirement_question_appends_product_manager_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            task = manager.create_task("Build chat flow", "Need a chat workflow")

            async def ask(_title: str, _session):
                return "这个功能需要支持哪些失败场景？"

            session = await generate_requirement_question(manager, task.task_id, ask)

            self.assertEqual(session.messages[-1].role, "product_manager")
            self.assertEqual(session.messages[-1].content, "这个功能需要支持哪些失败场景？")

    async def test_generate_requirement_question_rejects_confirmed_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            task = manager.create_task("Build chat flow", "Need a chat workflow")
            manager.confirm_requirements(task.task_id, "Build a PM-led requirement confirmation flow.")

            async def ask(_title: str, _session):
                return "这个问题不应该再被调用"

            with self.assertRaisesRegex(ValueError, "already confirmed"):
                await generate_requirement_question(manager, task.task_id, ask)


if __name__ == "__main__":
    unittest.main()
