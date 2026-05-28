from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scheduler_automation.projects import ProjectManager


class ProjectManagerTests(unittest.TestCase):
    def test_create_project_persists_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ProjectManager(Path(temp_dir))

            project = manager.create_project("Alpha", "D:/Work/Alpha")

            self.assertEqual(project.project_id, "alpha")
            self.assertEqual(project.root_path, "D:/Work/Alpha")
            self.assertEqual(manager.get_project("alpha").name, "Alpha")

    def test_update_project_root_path_persists_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ProjectManager(Path(temp_dir))
            manager.create_project("Alpha")

            updated = manager.update_project_root_path("alpha", "D:/Work/Alpha")

            self.assertEqual(updated.root_path, "D:/Work/Alpha")
            self.assertEqual(manager.get_project("alpha").root_path, "D:/Work/Alpha")


if __name__ == "__main__":
    unittest.main()
