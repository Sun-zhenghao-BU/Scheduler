# Local Workflow Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an OpenSpec-backed local workflow engine with gated stage progression, self-review loops, release completion, and bilingual project documentation.

**Architecture:** Extend `WorkflowManager` into the orchestration layer for OpenSpec change creation, state gating, verification, review parsing, and completion. Keep the CLI thin, add only the commands required for the first end-to-end delivery loop, and isolate command execution behind an injectable runner for testability.

**Tech Stack:** Python 3.11+, standard library, OpenSpec CLI, git, unittest

---

### Task 1: Add failing tests for OpenSpec binding and metadata

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `src/scheduler_automation/workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_create_task_creates_openspec_change_and_tracks_binding(self) -> None:
    runner = RecordingRunner([])
    manager = WorkflowManager(Path(temp_dir), command_runner=runner)

    metadata = manager.create_task("Ship workflow", "Need a gated workflow")

    self.assertEqual(metadata.change_name, "ship-workflow")
    self.assertIn("openspec/changes/ship-workflow", metadata.change_path)
    self.assertEqual(runner.commands[0], ["openspec", "new", "change", "ship-workflow"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests.test_create_task_creates_openspec_change_and_tracks_binding -v`
Expected: FAIL because `WorkflowManager` does not accept a command runner and metadata lacks OpenSpec binding fields.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class TaskMetadata:
    change_name: str
    change_path: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests.test_create_task_creates_openspec_change_and_tracks_binding -v`
Expected: PASS

### Task 2: Add stage gating tests and implementation

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `src/scheduler_automation/workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_advance_to_implement_requires_openspec_artifacts(self) -> None:
    with self.assertRaisesRegex(ValueError, "proposal.md"):
        manager.advance_task(metadata.task_id, "implement")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests.test_advance_to_implement_requires_openspec_artifacts -v`
Expected: FAIL because `advance_task` currently permits the transition.

- [ ] **Step 3: Write minimal implementation**

```python
def advance_task(self, task_id: str, stage: str) -> TaskMetadata:
    blocked_reasons = self.validate_stage_transition(task_id, stage)
    if blocked_reasons:
        raise ValueError("; ".join(blocked_reasons))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests.test_advance_to_implement_requires_openspec_artifacts -v`
Expected: PASS

### Task 3: Add verification and review state handling

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `src/scheduler_automation/workflow.py`
- Modify: `src/scheduler_automation/cli.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_verify_records_successful_run(self) -> None:
    runner = RecordingRunner([CommandResult(0, "ok", "")])
    manager = WorkflowManager(Path(temp_dir), command_runner=runner)
    metadata = manager.create_task("Verify workflow")

    result = manager.verify_task(metadata.task_id)

    self.assertTrue(result.passed)
    self.assertIn("Verification", implementation_path.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests.test_verify_records_successful_run -v`
Expected: FAIL because no verification API exists.

- [ ] **Step 3: Write minimal implementation**

```python
def verify_task(self, task_id: str) -> VerificationResult:
    result = self.command_runner(self.verification_command)
    self._append_section(task_dir / "implementation.md", "Verification", result.stdout)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests.test_verify_records_successful_run -v`
Expected: PASS

### Task 4: Add completion orchestration tests and implementation

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `src/scheduler_automation/workflow.py`
- Modify: `src/scheduler_automation/cli.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_complete_task_archives_change_and_runs_git_commands(self) -> None:
    runner = RecordingRunner([
        CommandResult(0, "", ""),
        CommandResult(0, "", ""),
        CommandResult(0, "", ""),
    ])
    result = manager.complete_task(metadata.task_id)

    self.assertEqual(runner.commands[-2], ["git", "commit", "-m", "chore: complete ..."])
    self.assertEqual(runner.commands[-1], ["git", "push"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests.test_complete_task_archives_change_and_runs_git_commands -v`
Expected: FAIL because `complete_task` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def complete_task(self, task_id: str) -> CompletionResult:
    self._archive_change(metadata.change_name)
    self.command_runner(["git", "add", "."])
    self.command_runner(["git", "commit", "-m", message])
    self.command_runner(["git", "push"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.WorkflowManagerTests.test_complete_task_archives_change_and_runs_git_commands -v`
Expected: PASS

### Task 5: Refresh CLI output and bilingual README

**Files:**
- Modify: `src/scheduler_automation/cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing tests**

```python
def test_status_reports_blocked_tasks(self) -> None:
    output = run_cli(["status"])
    self.assertIn("BLOCKED", output)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.CLITests.test_status_reports_blocked_tasks -v`
Expected: FAIL because CLI does not expose blocked state.

- [ ] **Step 3: Write minimal implementation**

```python
print(f"{task.task_id} | {task.current_stage} | {state_label} | {task.title}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.CLITests.test_status_reports_blocked_tasks -v`
Expected: PASS

### Task 6: Full verification

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `src/scheduler_automation/cli.py`
- Modify: `src/scheduler_automation/workflow.py`
- Modify: `README.md`

- [ ] **Step 1: Run the full test suite**

Run: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`
Expected: PASS with all workflow tests green.

- [ ] **Step 2: Review release flow manually**

Run: `scheduler-flow --help`
Expected: New commands appear and help text matches the workflow.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/superpowers src/scheduler_automation tests/test_workflow.py .gitignore
git commit -m "feat: add openspec workflow engine"
```
