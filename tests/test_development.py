from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scheduler_automation.development import (
    DevelopmentCommandError,
    FileChange,
    apply_changes,
    build_change,
    parse_proposed_changes,
    propose_changes,
    validate_test_command,
)
from scheduler_automation.workspace import Workspace, WorkspaceAccessError


class DevelopmentChangeTests(unittest.TestCase):
    def test_build_change_creates_unified_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "app.py").write_text("print('old')\n", encoding="utf-8")

            change = build_change(Workspace(root), "app.py", "print('new')\n")

            self.assertEqual(change.path, "app.py")
            self.assertIn("-print('old')", change.diff)
            self.assertIn("+print('new')", change.diff)

    def test_apply_changes_writes_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "app.py").write_text("old\n", encoding="utf-8")
            change = FileChange(path="app.py", old_content="old\n", new_content="new\n", diff="")

            apply_changes(Workspace(root), [change])

            self.assertEqual((root / "app.py").read_text(encoding="utf-8"), "new\n")

    def test_apply_changes_rejects_path_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            change = FileChange(path="../outside.py", old_content="", new_content="bad\n", diff="")

            with self.assertRaises(WorkspaceAccessError):
                apply_changes(Workspace(root), [change])

    def test_validate_test_command_accepts_common_test_commands(self) -> None:
        self.assertEqual(validate_test_command("npm test"), ["npm", "test"])
        self.assertEqual(validate_test_command("pytest tests"), ["pytest", "tests"])
        self.assertEqual(validate_test_command("python -m pytest"), ["python", "-m", "pytest"])

    def test_validate_test_command_rejects_shell_control(self) -> None:
        with self.assertRaises(DevelopmentCommandError):
            validate_test_command("npm test && rm -rf /")

    def test_validate_test_command_rejects_unknown_executable(self) -> None:
        with self.assertRaises(DevelopmentCommandError):
            validate_test_command("rm -rf .")

    def test_parse_proposed_changes_accepts_wrapped_json_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = Workspace(root)

            raw = (
                "Here is the update plan.\n\n"
                '{"summary":"updated app","files":[{"path":"src/app.py","content":"print(\\"ok\\")\\n"}]}\n\n'
                "Done."
            )

            summary, changes = parse_proposed_changes(workspace, raw)

            self.assertEqual(summary, "updated app")
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0].path, "src/app.py")
            self.assertEqual(changes[0].new_content, 'print("ok")\n')

    def test_parse_proposed_changes_raises_friendly_error_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = Workspace(root)

            raw = '{"summary":"broken","files":[{"path":"src/app.py","content":"print(\\"ok\\")\\n"}'

            with self.assertRaisesRegex(DevelopmentCommandError, "valid JSON"):
                parse_proposed_changes(workspace, raw)


class DevelopmentProposalTests(unittest.IsolatedAsyncioTestCase):
    async def test_propose_changes_retries_once_when_first_response_is_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('old')\n", encoding="utf-8")
            workspace = Workspace(root)

            class FakeClient:
                def __init__(self, _profile) -> None:
                    self.calls = 0

                async def chat(self, _messages):
                    self.calls += 1
                    if self.calls == 1:
                        return '{"summary":"broken","files":[{"path":"src/app.py","content":"print(\\"new\\")\\n"}'
                    return '{"summary":"fixed","files":[{"path":"src/app.py","content":"print(\\"new\\")\\n"}]}'

            with (
                patch("scheduler_automation.development.get_llm_profile", return_value={"api_key": "x"}),
                patch("scheduler_automation.development.LLMClient", FakeClient),
            ):
                summary, changes = await propose_changes(workspace, "update app", ["src/app.py"])

            self.assertEqual(summary, "fixed")
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0].path, "src/app.py")


if __name__ == "__main__":
    unittest.main()
