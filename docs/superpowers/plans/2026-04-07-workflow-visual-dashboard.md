# Workflow Visual Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local browser-based dashboard that shows workflow task progress, blockers, and OpenSpec linkage using only the Python standard library.

**Architecture:** Add a dashboard server module that reads from `WorkflowManager`, serves a single HTML page, and exposes JSON endpoints for task list and task detail data. Keep the frontend minimal and polling-based so the first version stays dependency-free and testable.

**Tech Stack:** Python 3.11+, standard library (`http.server`, `json`, `threading`), unittest

---

### Task 1: Add failing tests for dashboard JSON responses

**Files:**
- Create: `src/scheduler_automation/dashboard.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_dashboard_lists_tasks_as_json(self) -> None:
    server = DashboardServer(root)
    payload = server.build_task_list_payload()
    self.assertEqual(payload["tasks"][0]["state"], "BLOCKED")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.DashboardTests.test_dashboard_lists_tasks_as_json -v`
Expected: FAIL because no dashboard module exists.

- [ ] **Step 3: Write minimal implementation**

```python
def build_task_list_payload(self) -> dict[str, object]:
    return {"tasks": [...]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.DashboardTests.test_dashboard_lists_tasks_as_json -v`
Expected: PASS

### Task 2: Add failing tests for task detail and 404 behavior

**Files:**
- Modify: `src/scheduler_automation/dashboard.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_dashboard_returns_task_detail_payload(self) -> None:
    detail = server.build_task_detail_payload(task_id)
    self.assertEqual(detail["task"]["current_stage"], "spec")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.DashboardTests.test_dashboard_returns_task_detail_payload -v`
Expected: FAIL because detail shaping does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def build_task_detail_payload(self, task_id: str) -> dict[str, object]:
    snapshot = self.manager.task_snapshot(task_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.DashboardTests.test_dashboard_returns_task_detail_payload -v`
Expected: PASS

### Task 3: Add HTTP response tests and implement the server

**Files:**
- Modify: `src/scheduler_automation/dashboard.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_dashboard_root_returns_html(self) -> None:
    status, headers, body = invoke_dashboard_handler("/")
    self.assertEqual(status, 200)
    self.assertIn("text/html", headers["Content-Type"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.DashboardTests.test_dashboard_root_returns_html -v`
Expected: FAIL because no HTTP handler exists.

- [ ] **Step 3: Write minimal implementation**

```python
class DashboardHandler(BaseHTTPRequestHandler):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.DashboardTests.test_dashboard_root_returns_html -v`
Expected: PASS

### Task 4: Add the single-page UI

**Files:**
- Modify: `src/scheduler_automation/dashboard.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing tests**

```python
def test_dashboard_html_contains_task_panels(self) -> None:
    html = render_dashboard_html()
    self.assertIn("task-list", html)
    self.assertIn("task-detail", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.DashboardTests.test_dashboard_html_contains_task_panels -v`
Expected: FAIL because the HTML shell is missing the expected layout hooks.

- [ ] **Step 3: Write minimal implementation**

```python
<aside id="task-list"></aside>
<section id="task-detail"></section>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.DashboardTests.test_dashboard_html_contains_task_panels -v`
Expected: PASS

### Task 5: Full verification

**Files:**
- Modify: `src/scheduler_automation/dashboard.py`
- Modify: `README.md`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Run the full test suite**

Run: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 2: Smoke test the module help path**

Run: `$env:PYTHONPATH='src'; python -m scheduler_automation.dashboard --help`
Expected: PASS with host/port options visible.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/superpowers src/scheduler_automation tests/test_workflow.py
git commit -m "feat: add workflow dashboard"
```
