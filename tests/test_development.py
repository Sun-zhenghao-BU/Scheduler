from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scheduler_automation.development import (
    DevelopmentCommandError,
    FileChange,
    apply_changes,
    build_change,
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


if __name__ == "__main__":
    unittest.main()
