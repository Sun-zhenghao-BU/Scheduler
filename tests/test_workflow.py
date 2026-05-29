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

    def test_create_task_initializes_requirement_session_from_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Build chat flow", "Users need a PM clarification chat.")

            session = manager.load_requirement_session(metadata.task_id)

            self.assertEqual(session.status, "drafting")
            self.assertEqual(len(session.messages), 1)
            self.assertEqual(session.messages[0].role, "user")
            self.assertEqual(session.messages[0].content, "Users need a PM clarification chat.")
            self.assertEqual(session.next_action, "ask")
            self.assertEqual(session.suggested_summary, "")

    def test_confirm_requirements_updates_spec_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Build chat flow", "Need a PM chat.")

            confirmed = manager.confirm_requirements(
                metadata.task_id,
                "Build a PM-led requirement confirmation flow before development starts.",
            )

            self.assertEqual(confirmed.requirement_status, "confirmed")
            self.assertTrue(confirmed.requirement_confirmed_at)
            updated, task_dir = manager.get_task(metadata.task_id)
            self.assertEqual(updated.requirement_status, "confirmed")
            spec = (task_dir / "spec.md").read_text(encoding="utf-8")
            self.assertIn("Build a PM-led requirement confirmation flow", spec)
            session = manager.load_requirement_session(metadata.task_id)
            self.assertEqual(session.status, "confirmed")
            self.assertIn("Build a PM-led requirement confirmation flow", session.summary)
            self.assertEqual(session.next_action, "confirm")
            self.assertIn("Build a PM-led requirement confirmation flow", session.suggested_summary)
            state = manager.load_workflow_state(metadata.task_id)
            self.assertEqual(state.status, "idle")
            self.assertEqual(state.current_round, 0)
            self.assertFalse(state.requires_human_review)
            self.assertEqual(state.issues, [])

    def test_reopen_requirements_returns_task_to_intake(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Build chat flow", "Need a PM chat.")
            manager.confirm_requirements(metadata.task_id, "Build a PM-led requirement confirmation flow.")

            reopened = manager.reopen_requirements(metadata.task_id)

            self.assertEqual(reopened.current_stage, "intake")
            self.assertEqual(reopened.requirement_status, "drafting")
            self.assertEqual(reopened.requirement_confirmed_at, "")
            session = manager.load_requirement_session(metadata.task_id)
            self.assertEqual(session.status, "drafting")
            self.assertEqual(session.next_action, "ask")
            self.assertEqual(session.suggested_summary, "")
            state = manager.load_workflow_state(metadata.task_id)
            self.assertEqual(state.current_stage, "intake")
            self.assertFalse(state.requires_human_review)
            self.assertEqual(state.recommended_action, "")

    def test_advance_task_updates_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Advance workflow")

            updated = manager.advance_task(metadata.task_id, "review")

            self.assertEqual(updated.current_stage, "review")
            summary = manager.render_task(metadata.task_id)
            self.assertIn("Current stage: review", summary)

    def test_advance_to_implement_requires_confirmed_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Build feature", "Need implementation.")

            with self.assertRaisesRegex(ValueError, "Requirements must be confirmed"):
                manager.advance_task(metadata.task_id, "implement")

    def test_advance_to_implement_after_requirements_are_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Build feature", "Need implementation.")
            manager.confirm_requirements(metadata.task_id, "Implement the approved feature.")

            updated = manager.advance_task(metadata.task_id, "implement")

            self.assertEqual(updated.current_stage, "implement")

    def test_append_log_writes_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WorkflowManager(Path(temp_dir))
            metadata = manager.create_task("Log workflow")

            manager.append_log(metadata.task_id, "implement", "Implemented CLI")

            journal = (Path(temp_dir) / "tasks" / metadata.task_id / "journal.md").read_text(encoding="utf-8")
            self.assertIn("[implement] Implemented CLI", journal)


if __name__ == "__main__":
    unittest.main()
