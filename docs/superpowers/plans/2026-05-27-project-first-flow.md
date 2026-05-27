# Project First Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MVP start from creating or opening a project, then run all requirement, development, and testing work inside that project.

**Architecture:** Add a lightweight project registry stored under `projects/index.json`, bind every task to a `project_id`, and make the React app route through a project home before showing the task dashboard. Keep the existing workspace browser as an in-project tool instead of the primary entry point.

**Tech Stack:** Python 3.11 standard library, FastAPI, React, TypeScript, Ant Design, unittest

---

### Task 1: Project Registry Backend

**Files:**
- Create: `src/scheduler_automation/projects.py`
- Create: `tests/test_projects.py`
- Modify: `src/scheduler_automation/workflow.py`

- [ ] **Step 1: Write failing tests**

Cover creating a project, listing projects, opening by id, and binding a task to a project id.

- [ ] **Step 2: Run tests to verify RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_projects -v`

Expected: FAIL because `ProjectManager` does not exist.

- [ ] **Step 3: Implement registry and task binding**

Add `ProjectMetadata`, `ProjectManager`, `project_id` on `TaskMetadata`, and `WorkflowManager.create_task(..., project_id="")`.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_projects -v`

Expected: PASS.

### Task 2: Project API

**Files:**
- Create: `src/scheduler_automation/api/routes/projects.py`
- Modify: `src/scheduler_automation/api/app.py`
- Modify: `src/scheduler_automation/api/routes/tasks.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Cover project create/list and task list filtered by project.

- [ ] **Step 2: Implement routes**

Add `GET /api/projects/`, `POST /api/projects/`, `GET /api/projects/{project_id}`, and `GET /api/projects/{project_id}/tasks`.

- [ ] **Step 3: Run Python tests**

Run: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`

Expected: PASS.

### Task 3: Project-First Frontend

**Files:**
- Modify: `src/web/src/types/index.ts`
- Modify: `src/web/src/api/index.ts`
- Create: `src/web/src/views/ProjectHome.tsx`
- Modify: `src/web/src/views/Dashboard.tsx`
- Modify: `src/web/src/views/Workspace.tsx`
- Modify: `src/web/src/App.tsx`
- Modify: `src/web/src/App.css`

- [ ] **Step 1: Add frontend API/types**

Add project types and project API calls.

- [ ] **Step 2: Add project home**

Home page offers “新建项目” and “打开项目”, then routes to `/projects/:projectId`.

- [ ] **Step 3: Scope dashboard to project**

Dashboard receives `projectId`, lists only that project’s tasks, and creates new tasks bound to it.

- [ ] **Step 4: Move workspace under project route**

Workspace route becomes `/projects/:projectId/workspace` and is presented as a project tool.

- [ ] **Step 5: Verify frontend**

Run: `npm.cmd run lint` and `npm.cmd run build` in `src/web`.

Expected: both PASS.
