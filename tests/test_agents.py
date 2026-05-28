from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scheduler_automation.agents.provider import AgentProvider, AgentResult, AgentRole
from scheduler_automation.agents.service import load_agent_results, run_agent_workflow
from scheduler_automation.workflow import WorkflowManager


class FakeAgentProvider(AgentProvider):
    async def run(self, role: AgentRole, task_title: str, task_context: str) -> AgentResult:
        return AgentResult(
            role=role,
            status="completed",
            content=f"{role}: {task_title}\n\n{task_context}",
        )


class AgentWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_agent_workflow_persists_results_and_overwrites_core_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Build agent workflow", "Create a real workflow")

            results = await run_agent_workflow(manager, metadata.task_id, FakeAgentProvider())
            loaded = load_agent_results(manager, metadata.task_id)
            _, task_dir = manager.get_task(metadata.task_id)

            self.assertEqual([result.role for result in results], ["product_manager", "developer", "tester"])
            self.assertEqual([result.role for result in loaded], ["product_manager", "developer", "tester"])
            self.assertIn("product_manager: Build agent workflow", (task_dir / "spec.md").read_text(encoding="utf-8"))
            self.assertIn("developer: Build agent workflow", (task_dir / "implementation.md").read_text(encoding="utf-8"))
            self.assertIn("tester: Build agent workflow", (task_dir / "review.md").read_text(encoding="utf-8"))
            self.assertTrue((task_dir / "agents.json").exists())


if __name__ == "__main__":
    unittest.main()
