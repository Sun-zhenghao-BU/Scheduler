from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from scheduler_automation.api.app import create_app


class ProjectPickerApiTests(unittest.TestCase):
    def test_pick_folder_returns_selected_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            app = create_app()
            app.state.root = repo_root

            with patch("pathlib.Path.cwd", return_value=repo_root):
                with patch("scheduler_automation.api.routes.projects.pick_windows_folder", return_value="C:\\Work\\Demo"):
                    with TestClient(app) as client:
                        response = client.post("/api/projects/pick-folder")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"selected": True, "path": "C:\\Work\\Demo"})

    def test_pick_folder_reports_cancelled_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            app = create_app()
            app.state.root = repo_root

            with patch("pathlib.Path.cwd", return_value=repo_root):
                with patch("scheduler_automation.api.routes.projects.pick_windows_folder", return_value=""):
                    with TestClient(app) as client:
                        response = client.post("/api/projects/pick-folder")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"selected": False, "path": ""})


if __name__ == "__main__":
    unittest.main()
