from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from scheduler_automation.api.app import create_app


class OpenRootsApiTests(unittest.TestCase):
    def test_list_open_roots_returns_available_mounts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            work_root = repo_root / "work"
            work_root.mkdir()

            env = {
                "SCHEDULER_OPEN_ROOTS": "work|D:/Work|/mnt/work",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("pathlib.Path.cwd", return_value=repo_root):
                    with patch("pathlib.Path.exists", side_effect=lambda self: str(self) == "/mnt/work" or Path(self).exists()):
                        app = create_app()
                        with TestClient(app) as client:
                            response = client.get("/api/projects/open-roots")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["root_id"], "work")

    def test_list_open_root_children_returns_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            mounted_root = repo_root / "mounted"
            child = mounted_root / "demo"
            child.mkdir(parents=True)
            (mounted_root / "file.txt").write_text("x", encoding="utf-8")

            env = {
                "SCHEDULER_OPEN_ROOTS": f"work|D:/Work|{mounted_root.as_posix()}",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("pathlib.Path.cwd", return_value=repo_root):
                    app = create_app()
                    with TestClient(app) as client:
                        response = client.get("/api/projects/open-roots/work/children")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "demo")
        self.assertEqual(response.json()[0]["path"], f"{mounted_root.as_posix()}/demo")


if __name__ == "__main__":
    unittest.main()
