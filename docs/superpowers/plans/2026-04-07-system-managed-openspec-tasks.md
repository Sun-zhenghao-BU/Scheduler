# System-Managed OpenSpec Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `openspec/changes/<change>/tasks.md` reflect real workflow progress automatically so users do not manually edit checkbox state.

**Architecture:** Keep `tasks.md` human-readable but let `WorkflowManager` own checkbox state transitions. Sync task items after artifact generation, stage advancement, verification, and review so release gates and dashboard progress stay aligned with actual work.

**Tech Stack:** Python standard library, unittest

---

### Task 1: Lock expected auto-sync behavior with tests

**Files:**
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Use realistic generated tasks in the stub artifacts**
- [ ] **Step 2: Keep tests asserting definition items complete after generation**
- [ ] **Step 3: Keep tests asserting implementation/review items sync and reopen correctly**

### Task 2: Implement workflow-driven task syncing

**Files:**
- Modify: `src/scheduler_automation/workflow.py`

- [ ] **Step 1: Add helpers to parse and rewrite numbered checkbox items in `tasks.md`**
- [ ] **Step 2: Sync definition items when generated artifacts are approved and written**
- [ ] **Step 3: Sync implementation/review items after stage changes, verification, and review**
- [ ] **Step 4: Reopen the final review/verification item when review still has open high findings**

### Task 3: Verify the behavior

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `src/scheduler_automation/workflow.py`

- [ ] **Step 1: Run focused unittest cases for auto-sync**
- [ ] **Step 2: Run full unittest suite**
- [ ] **Step 3: Summarize the new automatic behavior and any remaining manual steps**
