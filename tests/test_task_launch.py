from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scheduler_automation.api.routes import tasks as task_routes
from scheduler_automation.execution import ExecutionRequest
from scheduler_automation.projects import ProjectManager
from scheduler_automation.workflow import WorkflowManager


class _DummyBackgroundTask:
    def done(self) -> bool:
        return False


def _fake_create_task(coro):
    coro.close()
    return _DummyBackgroundTask()


class TaskLaunchTests(unittest.TestCase):
    def setUp(self) -> None:
        task_routes._RUNNING_WORKFLOWS.clear()

    def tearDown(self) -> None:
        task_routes._RUNNING_WORKFLOWS.clear()

    def test_start_orchestration_marks_workflow_queued(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            project_root.mkdir()
            project = ProjectManager(root).create_project("Demo", str(project_root))
            manager = WorkflowManager(root)
            task = manager.create_task("Build login", "Add login", project.project_id)
            manager.confirm_requirements(task.task_id, "Build a minimal login flow.")

            with patch("scheduler_automation.api.routes.tasks.get_manager", return_value=manager):
                with patch(
                    "scheduler_automation.api.routes.tasks.asyncio.create_task",
                    side_effect=_fake_create_task,
                ):
                    started = task_routes._start_orchestration_background(task.task_id, ExecutionRequest())

            state = manager.load_workflow_state(task.task_id)
            self.assertTrue(started)
            self.assertEqual(state.status, "queued")
            self.assertEqual(state.current_stage, "intake")

    def test_start_orchestration_rejects_duplicate_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            project_root.mkdir()
            project = ProjectManager(root).create_project("Demo", str(project_root))
            manager = WorkflowManager(root)
            task = manager.create_task("Build login", "Add login", project.project_id)
            manager.confirm_requirements(task.task_id, "Build a minimal login flow.")
            task_routes._RUNNING_WORKFLOWS[task.task_id] = _DummyBackgroundTask()

            with patch("scheduler_automation.api.routes.tasks.get_manager", return_value=manager):
                started = task_routes._start_orchestration_background(task.task_id, ExecutionRequest())

            self.assertFalse(started)


if __name__ == "__main__":
    unittest.main()
