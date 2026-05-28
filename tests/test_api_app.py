from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from scheduler_automation.api.app import create_app


class ApiAppTests(unittest.TestCase):
    def test_startup_registers_core_routes_and_healthcheck(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            paths = {route.path for route in app.routes}
            response = client.get("/healthz")
            missing_api = client.get("/api/missing")

        self.assertIn("/api/tasks/", paths)
        self.assertIn("/api/llm/config", paths)
        self.assertIn("/api/tasks/{task_id}/agents", paths)
        self.assertIn("/api/tasks/{task_id}/agents/run", paths)
        self.assertIn("/api/tasks/{task_id}/execute", paths)
        self.assertIn("/api/tasks/{task_id}/orchestrate", paths)
        self.assertIn("/api/workspace/tree", paths)
        self.assertIn("/api/workspace/file", paths)
        self.assertIn("/api/development/propose", paths)
        self.assertIn("/api/development/apply", paths)
        self.assertIn("/api/development/test", paths)
        self.assertIn("/api/projects/pick-folder", paths)
        self.assertIn("/api/projects/open-roots", paths)
        self.assertIn("/api/projects/open-roots/{root_id}/children", paths)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(missing_api.status_code, 404)


if __name__ == "__main__":
    unittest.main()
