from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scheduler_automation.workflow import WorkflowManager


class WorkflowManagerTests(unittest.TestCase):
    def test_create_task_generates_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Ship workflow")

            task_dir = Path(temp_dir) / "tasks" / metadata.task_id
            self.assertTrue(task_dir.exists())
            self.assertEqual(metadata.current_stage, "intake")
            self.assertTrue((task_dir / "spec.md").exists())
            self.assertTrue((task_dir / "metadata.json").exists())

    def test_advance_task_updates_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Advance workflow")

            updated = manager.advance_task(metadata.task_id, "review")

            self.assertEqual(updated.current_stage, "review")
            summary = manager.render_task(metadata.task_id)
            self.assertIn("Current stage: review", summary)

    def test_append_log_writes_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Log workflow")

            manager.append_log(metadata.task_id, "implement", "Implemented CLI")

            journal = (Path(temp_dir) / "tasks" / metadata.task_id / "journal.md").read_text(encoding="utf-8")
            self.assertIn("[implement] Implemented CLI", journal)


if __name__ == "__main__":
    unittest.main()
