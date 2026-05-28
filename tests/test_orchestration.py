from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scheduler_automation.agents.provider import AgentResult
from scheduler_automation.development import FileChange, TestRunResult
from scheduler_automation.execution import ExecutionRequest
from scheduler_automation.orchestration import run_task_orchestration
from scheduler_automation.projects import ProjectManager
from scheduler_automation.workflow import WorkflowManager


class StaticProvider:
    def __init__(self, responses: dict[str, AgentResult]) -> None:
        self.responses = responses

    async def run(self, role: str, task_title: str, task_context: str) -> AgentResult:
        _ = task_title
        _ = task_context
        return self.responses[role]


class OrchestrationWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_orchestration_generates_spec_and_implementation_before_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            project_root.mkdir()
            project = ProjectManager(root).create_project("Demo", str(project_root))
            manager = WorkflowManager(root)
            task = manager.create_task("Build login", "Add login", project.project_id)
            manager.confirm_requirements(task.task_id, "Build a minimal login flow.")

            provider = StaticProvider(
                {
                    "product_manager": AgentResult("product_manager", "completed", "# 产品规划\n\n详细产品方案"),
                    "developer": AgentResult("developer", "completed", "# 实施方案\n\n详细实施方案"),
                    "tester": AgentResult("tester", "completed", "# 测试评审\n\n测试通过，可以发布"),
                }
            )

            async def propose(_instruction: str, _paths: list[str], _project_id: str):
                return (
                    "Implemented login flow",
                    [
                        FileChange("pyproject.toml", "", "[project]\nname='demo'\n", ""),
                        FileChange("src/app.py", "", "def login() -> str:\n    return 'ok'\n", ""),
                        FileChange("tests/test_app.py", "", "def test_login() -> None:\n    assert True\n", ""),
                    ],
                )

            def run_test(_project_id: str, command: str) -> TestRunResult:
                return TestRunResult(command=command, exit_code=0, output="1 passed")

            result = await run_task_orchestration(
                manager,
                task.task_id,
                provider,
                ExecutionRequest(),
                propose,
                run_test,
            )

            metadata, task_dir = manager.get_task(task.task_id)
            self.assertTrue(result.release_ready)
            self.assertEqual(result.final_stage, "release")
            self.assertEqual(metadata.current_stage, "release")
            self.assertIn("详细产品方案", (task_dir / "spec.md").read_text(encoding="utf-8"))
            self.assertIn("详细实施方案", (task_dir / "implementation.md").read_text(encoding="utf-8"))
            self.assertIn("测试通过，可以发布", (task_dir / "review.md").read_text(encoding="utf-8"))

    async def test_orchestration_moves_to_fix_when_test_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            project_root.mkdir()
            project = ProjectManager(root).create_project("Demo", str(project_root))
            manager = WorkflowManager(root)
            task = manager.create_task("Build login", "Add login", project.project_id)
            manager.confirm_requirements(task.task_id, "Build a minimal login flow.")

            provider = StaticProvider(
                {
                    "product_manager": AgentResult("product_manager", "completed", "# 产品规划\n\n详细产品方案"),
                    "developer": AgentResult("developer", "completed", "# 实施方案\n\n详细实施方案"),
                    "tester": AgentResult("tester", "completed", "# 测试评审\n\n发现失败用例，需要修复"),
                }
            )

            async def propose(_instruction: str, _paths: list[str], _project_id: str):
                return (
                    "Implemented login flow",
                    [
                        FileChange("pyproject.toml", "", "[project]\nname='demo'\n", ""),
                        FileChange("src/app.py", "", "def login() -> str:\n    return 'broken'\n", ""),
                        FileChange("tests/test_app.py", "", "def test_login() -> None:\n    assert False\n", ""),
                    ],
                )

            def run_test(_project_id: str, command: str) -> TestRunResult:
                return TestRunResult(command=command, exit_code=1, output="1 failed")

            result = await run_task_orchestration(
                manager,
                task.task_id,
                provider,
                ExecutionRequest(),
                propose,
                run_test,
            )

            metadata, _ = manager.get_task(task.task_id)
            self.assertFalse(result.release_ready)
            self.assertEqual(result.final_stage, "fix")
            self.assertEqual(metadata.current_stage, "fix")


if __name__ == "__main__":
    unittest.main()
