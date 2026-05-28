# Task-Driven Execution Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current document-only agent flow into a task-driven execution workflow that can generate code changes against the bound project workspace, apply them, run tests, and write execution results back into the task.

**Architecture:** Keep requirement confirmation as the gate, but replace the current “run agents writes three markdown files” path with a single execution pipeline owned by the task. Backend execution will reuse the existing development proposal/apply/test utilities, add task-scoped orchestration, and expose one API entrypoint for “start implementation”. Frontend task detail will call that entrypoint, display execution progress/results, and demote the old document-only agent run path to secondary status.

**Tech Stack:** Python 3.11+, FastAPI, React, TypeScript, Ant Design, unittest

---

### Task 1: Backend Execution Contract

**Files:**
- Create: `tests/test_execution_workflow.py`
- Modify: `src/scheduler_automation/workflow.py`
- Modify: `src/scheduler_automation/projects.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- running task implementation requires confirmed requirements
- running task implementation requires a project with a bound `root_path`
- execution result writes implementation summary, written files, test command, test output
- task stage advances to `implement` if execution succeeds

- [ ] **Step 2: Run targeted tests to verify RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_execution_workflow -v`

Expected: FAIL because no execution workflow exists yet.

- [ ] **Step 3: Implement minimal task execution data model**

Add workflow-level result types and helpers for:
- resolving task project workspace
- capturing execution metadata
- writing execution results into task files

- [ ] **Step 4: Run targeted tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_execution_workflow -v`

Expected: PASS.

### Task 2: Backend Orchestration Pipeline

**Files:**
- Create: `src/scheduler_automation/execution.py`
- Modify: `src/scheduler_automation/development.py`
- Modify: `src/scheduler_automation/project_workspace.py`
- Modify: `tests/test_execution_workflow.py`

- [ ] **Step 1: Write the failing orchestration tests**

Cover:
- requirement summary becomes execution instruction context
- development proposal produces file changes tied to task/project
- apply writes to bound workspace
- configured test command runs after apply
- failure paths still write task artifacts

- [ ] **Step 2: Run targeted tests to verify RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_execution_workflow.ExecutionOrchestrationTests -v`

Expected: FAIL because orchestration layer does not exist.

- [ ] **Step 3: Implement minimal orchestration**

Build one execution pipeline:
- gather task + project + workspace context
- select files
- generate proposal
- optionally apply
- run test command
- write implementation/review/journal updates

- [ ] **Step 4: Run targeted tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_execution_workflow.ExecutionOrchestrationTests -v`

Expected: PASS.

### Task 3: API Surface

**Files:**
- Modify: `src/scheduler_automation/api/routes/tasks.py`
- Modify: `src/scheduler_automation/api/routes/development.py`
- Modify: `tests/test_api_app.py`
- Modify: `tests/test_project_workspace_api.py`

- [ ] **Step 1: Write the failing API tests**

Cover:
- `POST /api/tasks/{task_id}/execute` triggers the task-driven execution workflow
- response includes proposal summary, written files, test result, and stage state
- task execution rejects unconfirmed requirements or unbound project directories

- [ ] **Step 2: Run API tests to verify RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_api_app tests.test_project_workspace_api -v`

Expected: FAIL because the execute endpoint does not exist.

- [ ] **Step 3: Implement the execute endpoint**

Expose one task-scoped API for:
- execution request payload
- execution result payload
- task/project validation
- mapping execution failures to HTTP errors

- [ ] **Step 4: Run API tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_api_app tests.test_project_workspace_api -v`

Expected: PASS.

### Task 4: Frontend Task-Driven Execution

**Files:**
- Modify: `src/web/src/api/index.ts`
- Modify: `src/web/src/types/index.ts`
- Modify: `src/web/src/views/TaskDetail.tsx`
- Modify: `src/web/src/views/Workspace.tsx`

- [ ] **Step 1: Add frontend API/types**

Add task execution request/response types and client methods.

- [ ] **Step 2: Replace primary action in task detail**

Task detail should:
- show `开始实施` as the main action after requirements are confirmed
- launch execution against the current project
- show execution result summary, modified files, and test output inline

- [ ] **Step 3: Keep workspace as a secondary drill-down**

Workspace remains available, but task execution becomes the main path.

- [ ] **Step 4: Run frontend build**

Run: `npm.cmd run build`

Expected: PASS.

### Task 5: Task Artifact Writeback

**Files:**
- Modify: `src/scheduler_automation/workflow.py`
- Modify: `src/scheduler_automation/agents/service.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Write failing tests**

Cover:
- implementation artifact includes applied change summary
- review artifact includes test command/result
- journal records execution start/end/failure
- old document-only agent output no longer pretends to be the main execution path

- [ ] **Step 2: Run workflow tests to verify RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow -v`

Expected: FAIL because task artifacts are not written from the execution pipeline.

- [ ] **Step 3: Implement artifact writeback**

Use execution results to update task markdown files and stage/journal metadata.

- [ ] **Step 4: Run workflow tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow -v`

Expected: PASS.

### Task 6: Full Verification

**Files:**
- Modify: any touched files above

- [ ] **Step 1: Run Python test suite**

Run: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run: `npm.cmd run build`

Expected: PASS.

- [ ] **Step 3: Manual workflow check**

Verify:
- open folder -> open project
- create task
- confirm requirements
- start implementation
- apply code changes
- run tests
- inspect task artifacts

