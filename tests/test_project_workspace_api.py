from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from scheduler_automation.api.app import create_app
from scheduler_automation.development import TestRunResult
from scheduler_automation.projects import ProjectManager


@contextmanager
def working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class ProjectScopedWorkspaceApiTests(unittest.TestCase):
    def test_workspace_tree_uses_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            mounted_root = repo_root / "mounted"
            mounted_root.mkdir()
            (mounted_root / "global.txt").write_text("global\n", encoding="utf-8")

            project_root = repo_root / "repos" / "alpha"
            project_root.mkdir(parents=True)
            (project_root / "project.txt").write_text("project\n", encoding="utf-8")

            ProjectManager(repo_root).create_project("Alpha", str(project_root))

            with patch.dict(os.environ, {"SCHEDULER_PROJECT_ROOT": str(mounted_root)}, clear=False):
                with working_directory(repo_root):
                    app = create_app()
                    with TestClient(app) as client:
                        response = client.get("/api/workspace/tree", params={"project_id": "alpha"})

            self.assertEqual(response.status_code, 200)
            paths = {item["path"] for item in response.json()}
            self.assertIn("project.txt", paths)
            self.assertNotIn("global.txt", paths)

    def test_workspace_info_reports_unbound_project_as_unconfigured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            ProjectManager(repo_root).create_project("Alpha")

            with working_directory(repo_root):
                app = create_app()
                with TestClient(app) as client:
                    response = client.get("/api/workspace/", params={"project_id": "alpha"})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"configured": False, "root": ""})

    def test_apply_development_writes_into_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            mounted_root = repo_root / "mounted"
            mounted_root.mkdir()
            (mounted_root / "app.py").write_text("print('global')\n", encoding="utf-8")

            project_root = repo_root / "repos" / "alpha"
            project_root.mkdir(parents=True)
            (project_root / "app.py").write_text("print('old')\n", encoding="utf-8")

            ProjectManager(repo_root).create_project("Alpha", str(project_root))
            sessions_dir = repo_root / "tasks" / ".development_sessions"
            sessions_dir.mkdir(parents=True)
            (sessions_dir / "session1.json").write_text(
                json.dumps(
                    {
                        "session_id": "session1",
                        "summary": "update app",
                        "project_id": "alpha",
                        "changes": [
                            {
                                "path": "app.py",
                                "old_content": "print('old')\n",
                                "new_content": "print('new')\n",
                                "diff": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"SCHEDULER_PROJECT_ROOT": str(mounted_root)}, clear=False):
                with working_directory(repo_root):
                    app = create_app()
                    with TestClient(app) as client:
                        response = client.post("/api/development/apply", json={"session_id": "session1"})

            self.assertEqual(response.status_code, 200)
            self.assertEqual((project_root / "app.py").read_text(encoding="utf-8"), "print('new')\n")
            self.assertEqual((mounted_root / "app.py").read_text(encoding="utf-8"), "print('global')\n")

    def test_run_development_test_uses_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            mounted_root = repo_root / "mounted"
            mounted_root.mkdir()

            project_root = repo_root / "repos" / "alpha"
            project_root.mkdir(parents=True)

            ProjectManager(repo_root).create_project("Alpha", str(project_root))

            def fake_run_test_command(workspace, command: str) -> TestRunResult:
                return TestRunResult(command=command, exit_code=0, output=str(workspace.root))

            with patch.dict(os.environ, {"SCHEDULER_PROJECT_ROOT": str(mounted_root)}, clear=False):
                with working_directory(repo_root):
                    app = create_app()
                    with patch("scheduler_automation.api.routes.development.run_test_command", side_effect=fake_run_test_command):
                        with TestClient(app) as client:
                            response = client.post(
                                "/api/development/test",
                                json={"command": "npm test", "project_id": "alpha"},
                            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["output"], str(project_root.resolve()))


if __name__ == "__main__":
    unittest.main()
