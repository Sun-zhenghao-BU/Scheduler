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


class SequencedProvider:
    def __init__(self, responses: dict[str, list[AgentResult]]) -> None:
        self.responses = responses
        self.calls: dict[str, int] = {role: 0 for role in responses}

    async def run(self, role: str, task_title: str, task_context: str) -> AgentResult:
        _ = task_title
        _ = task_context
        index = self.calls.get(role, 0)
        items = self.responses[role]
        result = items[min(index, len(items) - 1)]
        self.calls[role] = index + 1
        return result


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

            provider = SequencedProvider(
                {
                    "product_manager": [AgentResult("product_manager", "completed", "# 产品规划\n\n详细产品方案")],
                    "developer": [AgentResult("developer", "completed", "# 实施方案\n\n详细实施方案")],
                    "tester": [AgentResult("tester", "completed", "# 测试评审\n\n测试通过，可以发布")],
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
            self.assertEqual(result.fix_rounds, 0)
            self.assertEqual(metadata.current_stage, "release")
            self.assertIn("详细产品方案", (task_dir / "spec.md").read_text(encoding="utf-8"))
            self.assertIn("详细实施方案", (task_dir / "implementation.md").read_text(encoding="utf-8"))
            self.assertIn("测试通过，可以发布", (task_dir / "review.md").read_text(encoding="utf-8"))

    async def test_orchestration_retries_after_failure_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            project_root.mkdir()
            project = ProjectManager(root).create_project("Demo", str(project_root))
            manager = WorkflowManager(root)
            task = manager.create_task("Build login", "Add login", project.project_id)
            manager.confirm_requirements(task.task_id, "Build a minimal login flow.")

            provider = SequencedProvider(
                {
                    "product_manager": [AgentResult("product_manager", "completed", "# 产品规划\n\n详细产品方案")],
                    "developer": [
                        AgentResult("developer", "completed", "# 实施方案\n\n第一版实施方案"),
                        AgentResult("developer", "completed", "# 实施方案\n\n修复后的实施方案"),
                    ],
                    "tester": [
                        AgentResult("tester", "completed", "# 测试评审\n\n发现失败用例，需要修复"),
                        AgentResult("tester", "completed", "# 测试评审\n\n复测通过，可以发布"),
                    ],
                }
            )

            attempt = {"count": 0}

            async def propose(instruction: str, _paths: list[str], _project_id: str):
                attempt["count"] += 1
                if attempt["count"] == 1:
                    self.assertNotIn("Fix round", instruction)
                    return (
                        "Implemented login flow",
                        [
                            FileChange("pyproject.toml", "", "[project]\nname='demo'\n", ""),
                            FileChange("src/app.py", "", "def login() -> str:\n    return 'broken'\n", ""),
                            FileChange("tests/test_app.py", "", "def test_login() -> None:\n    assert False\n", ""),
                        ],
                    )
                self.assertIn("Fix round 1", instruction)
                self.assertIn("发现失败用例，需要修复", instruction)
                return (
                    "Fixed login flow",
                    [
                        FileChange("src/app.py", "def login() -> str:\n    return 'broken'\n", "def login() -> str:\n    return 'ok'\n", ""),
                        FileChange("tests/test_app.py", "def test_login() -> None:\n    assert False\n", "def test_login() -> None:\n    assert True\n", ""),
                    ],
                )

            def run_test(_project_id: str, command: str) -> TestRunResult:
                if attempt["count"] == 1:
                    return TestRunResult(command=command, exit_code=1, output="1 failed")
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
            self.assertEqual(result.fix_rounds, 1)
            self.assertEqual(metadata.current_stage, "release")
            self.assertIn("第一版实施方案", (task_dir / "implementation.md").read_text(encoding="utf-8"))
            self.assertIn("修复后的实施方案", (task_dir / "implementation.md").read_text(encoding="utf-8"))
            self.assertIn("Fix Round 1", (task_dir / "fixes.md").read_text(encoding="utf-8"))
            self.assertIn("自动流程确认本任务满足当前发布条件", (task_dir / "release.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
