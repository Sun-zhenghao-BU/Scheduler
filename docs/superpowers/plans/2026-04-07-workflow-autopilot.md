# Workflow Autopilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-command autopilot that advances a task through non-destructive workflow stages, writes process documents automatically, and stops only at release readiness or when code changes are required.

**Architecture:** Extend `WorkflowManager` with an autopilot loop that uses existing stage gates, verification, and review parsing rather than creating a second workflow path. The loop will synthesize process document content from task metadata and verification results, then call the existing transition methods until it reaches `release` or a `fix` state that still needs code changes.

**Tech Stack:** Python standard library, unittest

---

### Task 1: Lock autopilot behavior with tests

**Files:**
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Add a test that autopilot moves a generated task to `release` after successful verification**
- [ ] **Step 2: Add a test that autopilot stops in `fix` when review finds a blocking issue after failed verification**
- [ ] **Step 3: Add a CLI test for the new `autopilot` command output**

### Task 2: Implement the workflow autopilot loop

**Files:**
- Modify: `src/scheduler_automation/workflow.py`
- Modify: `src/scheduler_automation/cli.py`

- [ ] **Step 1: Add autopilot result data and a public `autopilot_task()` workflow entrypoint**
- [ ] **Step 2: Add helpers that write or refresh implementation, review, fixes, and release sections without leaving placeholders**
- [ ] **Step 3: Drive stage transitions, verification, review, and managed tasks syncing from the autopilot loop**
- [ ] **Step 4: Stop before `complete` and return a clear summary of where autopilot stopped and why**

### Task 3: Verify and document the new flow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run focused autopilot tests**
- [ ] **Step 2: Run the full unittest suite**
- [ ] **Step 3: Update the README command list to show the one-command flow**
