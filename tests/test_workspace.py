from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scheduler_automation.workspace import Workspace, WorkspaceAccessError


class WorkspaceTests(unittest.TestCase):
    def test_list_directories_returns_only_direct_children(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "alpha").mkdir()
            (root / "alpha" / "nested").mkdir()
            (root / "beta").mkdir()
            (root / "README.md").write_text("x", encoding="utf-8")

            directories = Workspace(root).list_directories()

            self.assertEqual([item["name"] for item in directories], ["alpha", "beta"])

    def test_tree_lists_project_files_and_skips_ignored_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "ignored.js").write_text("", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("", encoding="utf-8")

            tree = Workspace(root).tree()
            paths = [item["path"] for item in tree]

            self.assertIn("src", paths)
            self.assertIn("src/app.py", paths)
            self.assertNotIn("node_modules", paths)
            self.assertNotIn(".git", paths)

    def test_read_file_rejects_path_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside = root.parent / "outside.txt"
            outside.write_text("secret", encoding="utf-8")

            with self.assertRaises(WorkspaceAccessError):
                Workspace(root).read_file("../outside.txt")

    def test_read_file_returns_text_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "README.md").write_text("# 项目", encoding="utf-8")

            result = Workspace(root).read_file("README.md")

            self.assertEqual(result["path"], "README.md")
            self.assertEqual(result["content"], "# 项目")


if __name__ == "__main__":
    unittest.main()
