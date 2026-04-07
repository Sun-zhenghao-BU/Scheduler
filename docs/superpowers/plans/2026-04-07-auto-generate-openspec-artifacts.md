# Auto Generate OpenSpec Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate OpenSpec `proposal.md`, `design.md`, `specs/.../spec.md`, and `tasks.md` during `new-task`, preview them in the terminal, and only write them after user confirmation.

**Architecture:** Add an OpenSpec-template-backed artifact generator behind a clear interface, then extend `WorkflowManager.create_task()` to orchestrate generation, preview, confirmation, and conditional writes without coupling template resolution directly into the CLI. Keep tests offline by mocking the generator and confirmation path.

**Tech Stack:** Python 3.11+, standard library, OpenSpec CLI, unittest

---

### Task 1: Add template-backed generator tests

**Files:**
- Create: `src/scheduler_automation/artifact_generation.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_openspec_artifact_generator_builds_expected_artifacts(self) -> None:
    generator = OpenSpecArtifactGenerator(root, template_loader=stub_loader)
    artifacts = generator.generate(
        title="Workflow dashboard",
        request="Show workflow progress visually",
        change_name="workflow-dashboard",
    )
    self.assertIn("workflow-dashboard", artifacts.proposal)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.OpenSpecGenerationTests.test_openspec_artifact_generator_builds_expected_artifacts -v`
Expected: FAIL because no OpenSpec-backed generator exists.

- [ ] **Step 3: Write minimal implementation**

```python
class OpenSpecArtifactGenerator:
    def generate(self, title: str, request: str, change_name: str) -> GeneratedArtifacts:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.OpenSpecGenerationTests.test_openspec_artifact_generator_builds_expected_artifacts -v`
Expected: PASS

### Task 2: Add workflow generation orchestration tests

**Files:**
- Modify: `src/scheduler_automation/workflow.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_create_task_generates_preview_and_writes_artifacts_after_confirmation(self) -> None:
    manager = WorkflowManager(root, command_runner=runner, artifact_generator=generator, confirm_write=lambda *_: True)
    metadata = manager.create_task("Generated workflow", "Generate artifacts")
    self.assertTrue((root / metadata.change_path / "proposal.md").exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.OpenSpecGenerationTests.test_create_task_generates_preview_and_writes_artifacts_after_confirmation -v`
Expected: FAIL because generated artifacts are not yet wired into task creation.

- [ ] **Step 3: Write minimal implementation**

```python
if self.artifact_generator is not None:
    artifacts = self._generate_artifacts(...)
    if self.confirm_write(change_name, artifacts):
        self._write_generated_artifacts(change_dir, artifacts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.OpenSpecGenerationTests.test_create_task_generates_preview_and_writes_artifacts_after_confirmation -v`
Expected: PASS

### Task 3: Add preview rejection handling

**Files:**
- Modify: `src/scheduler_automation/workflow.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_create_task_leaves_generated_files_unwritten_when_confirmation_is_rejected(self) -> None:
    manager = WorkflowManager(root, command_runner=runner, artifact_generator=generator, confirm_write=lambda *_: False)
    metadata = manager.create_task("Rejected workflow", "Generate artifacts")
    self.assertFalse((root / metadata.change_path / "proposal.md").exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.OpenSpecGenerationTests.test_create_task_leaves_generated_files_unwritten_when_confirmation_is_rejected -v`
Expected: FAIL because rejection is not handled.

- [ ] **Step 3: Write minimal implementation**

```python
if approved:
    ...
else:
    self.append_log(task_id, "intake", "Generated OpenSpec artifacts were rejected")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.OpenSpecGenerationTests.test_create_task_leaves_generated_files_unwritten_when_confirmation_is_rejected -v`
Expected: PASS

### Task 4: Add CLI preview and confirmation wiring

**Files:**
- Modify: `src/scheduler_automation/cli.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_new_task_prints_generated_preview_before_confirmation(self) -> None:
    output = io.StringIO()
    with redirect_stdout(output):
        cli.main(["new-task", "--title", "Preview workflow", "--request", "Generate preview"])
    self.assertIn("Generated proposal.md", output.getvalue())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.CLITests.test_new_task_prints_generated_preview_before_confirmation -v`
Expected: FAIL because CLI does not preview generated artifacts.

- [ ] **Step 3: Write minimal implementation**

```python
def confirm_generated_artifacts(change_name: str, artifacts: GeneratedArtifacts) -> bool:
    for filename, content in artifacts.preview_items():
        print(...)
    print(...)
    response = input()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_workflow.CLITests.test_new_task_prints_generated_preview_before_confirmation -v`
Expected: PASS

### Task 5: Full verification

**Files:**
- Modify: `src/scheduler_automation/artifact_generation.py`
- Modify: `src/scheduler_automation/workflow.py`
- Modify: `src/scheduler_automation/cli.py`
- Modify: `README.md`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: Run the full test suite**

Run: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 2: Smoke test the CLI help**

Run: `$env:PYTHONPATH='src'; python -m scheduler_automation.cli --help`
Expected: PASS with `new-task` still present and behavior documented in README.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/superpowers src/scheduler_automation tests/test_workflow.py
git commit -m "feat: auto-generate openspec artifacts"
```
