# PM Requirement Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a product-manager requirement confirmation gate before development starts.

**Architecture:** Keep durable workflow state in each `tasks/<task-id>/` directory. Add a small requirement session file for multi-turn PM discussion, mirror confirmation status into task metadata, and block the `implement` stage until requirements are confirmed. The first slice is backend-only so the state model is testable before UI wiring.

**Tech Stack:** Python 3.11+, standard library, FastAPI, unittest

---

### Task 1: Requirement Session State

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `src/scheduler_automation/workflow.py`

- [x] **Step 1: Write failing tests**

Add tests that create a task with an initial request, assert a `requirements.json` session exists with `drafting` status, confirm requirements, and assert `spec.md` plus metadata update.

- [x] **Step 2: Run targeted tests to verify RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests -v`

Expected: FAIL because requirement session APIs do not exist yet.

- [x] **Step 3: Implement minimal state model**

Add `RequirementMessage`, `RequirementSession`, metadata fields, `load_requirement_session`, `append_requirement_message`, and `confirm_requirements`.

- [x] **Step 4: Run targeted tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests -v`

Expected: PASS.

### Task 2: Development Gate

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `src/scheduler_automation/workflow.py`

- [x] **Step 1: Write failing tests**

Add tests that `advance_task(..., "implement")` fails before requirements are confirmed and succeeds after confirmation.

- [x] **Step 2: Run targeted tests to verify RED**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests -v`

Expected: FAIL because `advance_task` currently permits `implement`.

- [x] **Step 3: Implement minimal gate**

Update `advance_task` to reject the `implement` stage unless `metadata.requirement_status == "confirmed"`.

- [x] **Step 4: Run full Python tests**

Run: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`

Expected: PASS.

### Task 3: API Surface

**Files:**
- Modify: `src/scheduler_automation/api/routes/tasks.py`

- [x] **Step 1: Add request/response models**

Expose requirement session messages and confirmation state through typed Pydantic models.

- [x] **Step 2: Add endpoints**

Add:
- `GET /api/tasks/{task_id}/requirements`
- `POST /api/tasks/{task_id}/requirements/messages`
- `POST /api/tasks/{task_id}/requirements/confirm`

- [x] **Step 3: Run Python tests**

Run: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`

Expected: PASS.
