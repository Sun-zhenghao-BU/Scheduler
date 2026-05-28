from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scheduler_automation.development import FileChange, TestRunResult
from scheduler_automation.execution import ExecutionRequest, execute_task
from scheduler_automation.projects import ProjectManager
from scheduler_automation.workflow import WorkflowManager


class ExecutionWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_task_requires_confirmed_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            project_root.mkdir()
            (project_root / "app.py").write_text("print('old')\n", encoding="utf-8")
            project = ProjectManager(root).create_project("Calculator", str(project_root))
            task = WorkflowManager(root).create_task("Calculator", "Need a calculator", project.project_id)

            async def propose(_instruction: str, _paths: list[str], _project_id: str):
                return "summary", [FileChange(path="app.py", old_content="print('old')\n", new_content="print('new')\n", diff="")]

            def run_test(_project_id: str, command: str) -> TestRunResult:
                return TestRunResult(command=command, exit_code=0, output="ok")

            with self.assertRaisesRegex(ValueError, "Requirements must be confirmed"):
                await execute_task(WorkflowManager(root), task.task_id, ExecutionRequest(), propose, run_test)

    async def test_execute_task_requires_bound_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = ProjectManager(root).create_project("Calculator")
            manager = WorkflowManager(root)
            task = manager.create_task("Calculator", "Need a calculator", project.project_id)
            manager.confirm_requirements(task.task_id, "Build a calculator.")

            async def propose(_instruction: str, _paths: list[str], _project_id: str):
                return "summary", []

            def run_test(_project_id: str, command: str) -> TestRunResult:
                return TestRunResult(command=command, exit_code=0, output="ok")

            with self.assertRaisesRegex(ValueError, "root_path"):
                await execute_task(manager, task.task_id, ExecutionRequest(), propose, run_test)

    async def test_execute_task_applies_changes_runs_tests_and_writes_task_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            src_dir = project_root / "src"
            tests_dir = project_root / "tests"
            src_dir.mkdir(parents=True)
            tests_dir.mkdir()
            (project_root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (src_dir / "app.py").write_text("print('old')\n", encoding="utf-8")
            project = ProjectManager(root).create_project("Calculator", str(project_root))
            manager = WorkflowManager(root)
            task = manager.create_task("Calculator", "Need a calculator", project.project_id)
            manager.confirm_requirements(task.task_id, "Build a calculator with a frontend.")

            async def propose(_instruction: str, _paths: list[str], _project_id: str):
                return (
                    "Implemented calculator flow",
                    [FileChange(path="src/app.py", old_content="print('old')\n", new_content="print('new')\n", diff="")],
                )

            def run_test(_project_id: str, command: str) -> TestRunResult:
                return TestRunResult(command=command, exit_code=0, output="2 passed")

            result = await execute_task(manager, task.task_id, ExecutionRequest(), propose, run_test)

            self.assertEqual(result.stage, "implement")
            self.assertEqual(result.written, ["src/app.py"])
            self.assertEqual((src_dir / "app.py").read_text(encoding="utf-8"), "print('new')\n")
            _, task_dir = manager.get_task(task.task_id)
            implementation = (task_dir / "implementation.md").read_text(encoding="utf-8")
            review = (task_dir / "review.md").read_text(encoding="utf-8")
            journal = (task_dir / "journal.md").read_text(encoding="utf-8")
            self.assertIn("Execution Summary", implementation)
            self.assertIn("Implemented calculator flow", implementation)
            self.assertIn("Execution Test Result", review)
            self.assertIn("2 passed", review)
            self.assertIn("Execution started", journal)
            self.assertIn("Execution finished", journal)

    async def test_execute_task_bootstraps_minimal_scaffold_when_workspace_has_no_candidate_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "empty-project"
            project_root.mkdir()
            project = ProjectManager(root).create_project("New Project", str(project_root))
            manager = WorkflowManager(root)
            task = manager.create_task("Build login flow", "Need a minimal login flow", project.project_id)
            manager.confirm_requirements(task.task_id, "Create the smallest workable login flow implementation.")

            seen_paths: list[str] = []

            async def propose(_instruction: str, paths: list[str], _project_id: str):
                seen_paths.extend(paths)
                return (
                    "Bootstrapped a minimal Python scaffold and implemented login flow",
                    [
                        FileChange(
                            path="pyproject.toml",
                            old_content="",
                            new_content="[project]\nname='new-project'\nversion='0.1.0'\n",
                            diff="",
                        ),
                        FileChange(
                            path="src/app.py",
                            old_content="",
                            new_content="def login(username: str) -> str:\n    return f'hello {username}'\n",
                            diff="",
                        ),
                        FileChange(
                            path="tests/test_app.py",
                            old_content="",
                            new_content=(
                                "from src.app import login\n\n\n"
                                "def test_login() -> None:\n"
                                "    assert login('alice') == 'hello alice'\n"
                            ),
                            diff="",
                        ),
                    ],
                )

            def run_test(_project_id: str, command: str) -> TestRunResult:
                return TestRunResult(command=command, exit_code=0, output="1 passed")

            result = await execute_task(manager, task.task_id, ExecutionRequest(), propose, run_test)

            self.assertEqual(
                seen_paths,
                ["pyproject.toml", "src/app.py", "tests/test_app.py"],
            )
            self.assertEqual(sorted(result.written), ["pyproject.toml", "src/app.py", "tests/test_app.py"])
            self.assertEqual(result.test_command, "python -m pytest")
            self.assertTrue((project_root / "src" / "app.py").exists())
            self.assertTrue((project_root / "tests" / "test_app.py").exists())
            self.assertTrue((project_root / "pyproject.toml").exists())


if __name__ == "__main__":
    unittest.main()
