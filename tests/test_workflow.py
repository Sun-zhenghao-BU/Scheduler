from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scheduler_automation import cli
from scheduler_automation.artifact_generation import GeneratedArtifacts, OpenSpecArtifactGenerator
from scheduler_automation.dashboard import DashboardApp
from scheduler_automation.workflow import CommandResult, WorkflowManager


class RecordingRunner:
    def __init__(self, root: Path, results: list[CommandResult] | None = None) -> None:
        self.root = root
        self.results = list(results or [])
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], cwd: Path | None = None) -> CommandResult:
        self.commands.append(list(command))

        if command[:3] in (["openspec", "new", "change"], ["openspec.cmd", "new", "change"]):
            change_name = command[3]
            change_dir = self.root / "openspec" / "changes" / change_name
            change_dir.mkdir(parents=True, exist_ok=True)
            (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
        if command[:3] in (["openspec", "instructions", "apply"], ["openspec.cmd", "instructions", "apply"]):
            return CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "state": "ready",
                        "schemaName": "spec-driven",
                        "instruction": "Apply pending tasks.",
                        "progress": {"total": 4, "complete": 1, "remaining": 3},
                        "tasks": [{"id": "2.1", "text": "Implement", "status": "pending"}],
                    }
                ),
                stderr="",
            )
        if command[:3] in (["openspec", "status", "--change"], ["openspec.cmd", "status", "--change"]):
            return CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "changeName": command[3] if len(command) > 3 else "",
                        "schemaName": "spec-driven",
                        "isComplete": False,
                    }
                ),
                stderr="",
            )
        if command[:3] in (["openspec", "validate", "--type"], ["openspec.cmd", "validate", "--type"]):
            return CommandResult(returncode=0, stdout='{"summary":{"totals":{"failed":0}}}', stderr="")
        if command == ["git", "rev-parse", "HEAD"]:
            return CommandResult(returncode=0, stdout="deadbeef\n", stderr="")
        if len(command) >= 4 and command[:3] == ["git", "diff", "--name-only"]:
            return CommandResult(returncode=0, stdout="src/scheduler_automation/workflow.py\n", stderr="")
        if len(command) >= 4 and command[:3] == ["git", "diff", "--numstat"]:
            return CommandResult(returncode=0, stdout="3\t1\tsrc/scheduler_automation/workflow.py\n", stderr="")
        if command == ["git", "status", "--porcelain"]:
            return CommandResult(returncode=0, stdout="", stderr="")

        if self.results:
            return self.results.pop(0)
        return CommandResult(returncode=0, stdout="", stderr="")


class StubArtifactGenerator:
    def __init__(
        self,
        proposal: str = "## Why\n\nGenerated.\n",
        design: str = "## Context\n\nGenerated.\n",
        tasks: str = (
            "## 1. Define `generated`\n\n"
            "- [ ] 1.1 Review and refine the generated proposal\n"
            "- [ ] 1.2 Review and refine the generated design and spec\n\n"
            "## 2. Implement and verify\n\n"
            "- [ ] 2.1 Implement the requested behavior for `generated`\n"
            "- [ ] 2.2 Run verification and record review findings\n"
        ),
        specs: dict[str, str] | None = None,
    ) -> None:
        self.artifacts = GeneratedArtifacts(
            proposal=proposal,
            design=design,
            tasks=tasks,
            specs=specs or {"specs/generated/spec.md": "## ADDED Requirements\n\nGenerated spec.\n"},
        )
        self.calls: list[dict[str, str]] = []

    def generate(self, title: str, request: str, change_name: str) -> GeneratedArtifacts:
        self.calls.append({"title": title, "request": request, "change_name": change_name})
        return self.artifacts


@contextmanager
def temporary_cwd(path: Path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


class OpenSpecGenerationTests(unittest.TestCase):
    def test_openspec_artifact_generator_builds_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template_dir = root / "templates"
            template_dir.mkdir()
            for name in ("proposal", "design", "specs", "tasks"):
                (template_dir / f"{name}.md").write_text(f"{name} template\n", encoding="utf-8")

            generator = OpenSpecArtifactGenerator(
                root,
                template_loader=lambda: {
                    "proposal": template_dir / "proposal.md",
                    "design": template_dir / "design.md",
                    "specs": template_dir / "specs.md",
                    "tasks": template_dir / "tasks.md",
                },
            )

            artifacts = generator.generate(
                title="Workflow dashboard",
                request="Show workflow progress visually",
                change_name="workflow-dashboard",
            )

            self.assertIn("workflow-dashboard", artifacts.proposal)
            self.assertIn("Workflow dashboard", artifacts.design)
            self.assertIn("specs/workflow-dashboard/spec.md", artifacts.preview_items()[2][0])
            self.assertIn("Show workflow progress visually", artifacts.specs["specs/workflow-dashboard/spec.md"])

    def test_create_task_generates_preview_and_writes_artifacts_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(root)
            generator = StubArtifactGenerator()
            previews: list[tuple[str, GeneratedArtifacts]] = []
            manager = WorkflowManager(
                root,
                command_runner=runner,
                artifact_generator=generator,
                confirm_write=lambda change_name, artifacts: previews.append((change_name, artifacts)) or True,
            )

            metadata = manager.create_task("Generated workflow", "Generate artifacts")

            change_dir = root / metadata.change_path
            self.assertTrue((change_dir / "proposal.md").exists())
            self.assertTrue((change_dir / "specs" / "generated" / "spec.md").exists())
            self.assertEqual(previews[0][0], metadata.change_name)
            spec_text = (root / "tasks" / metadata.task_id / "spec.md").read_text(encoding="utf-8")
            self.assertIn("Generate artifacts", spec_text)
            implementation_text = (root / "tasks" / metadata.task_id / "implementation.md").read_text(encoding="utf-8")
            self.assertIn("Use the generated OpenSpec artifacts", implementation_text)
            tasks_text = (change_dir / "tasks.md").read_text(encoding="utf-8")
            self.assertIn("- [x] 1.1", tasks_text)
            self.assertIn("- [x] 1.2", tasks_text)
            self.assertIn("- [ ] 2.1", tasks_text)

    def test_create_task_leaves_generated_files_unwritten_when_confirmation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(root)
            manager = WorkflowManager(
                root,
                command_runner=runner,
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: False,
            )

            metadata = manager.create_task("Rejected workflow", "Generate artifacts")

            change_dir = root / metadata.change_path
            self.assertFalse((change_dir / "proposal.md").exists())
            self.assertFalse((change_dir / "specs").exists())
            journal_text = (root / "tasks" / metadata.task_id / "journal.md").read_text(encoding="utf-8")
            self.assertIn("rejected", journal_text.lower())

    def test_generated_tasks_sync_with_implementation_and_review_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(root, [CommandResult(0, "", ""), CommandResult(0, "verification ok", "")])
            manager = WorkflowManager(
                root,
                command_runner=runner,
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: True,
            )

            metadata = manager.create_task("Synced workflow", "Generate artifacts")
            manager.advance_task(metadata.task_id, "spec")
            manager.advance_task(metadata.task_id, "implement")
            manager.verify_task(metadata.task_id)
            manager.advance_task(metadata.task_id, "review")
            review_path = root / "tasks" / metadata.task_id / "review.md"
            review_path.write_text(
                "# Review\n\n"
                "## Summary\n\n"
                "Reviewed workflow changes and found no blocking issues.\n\n"
                "## Findings\n\n"
                "None.\n",
                encoding="utf-8",
            )
            manager.review_task(metadata.task_id)

            tasks_text = (root / "openspec" / "changes" / metadata.change_name / "tasks.md").read_text(encoding="utf-8")
            self.assertIn("- [x] 2.1", tasks_text)
            self.assertIn("- [x] 2.2", tasks_text)

    def test_generated_tasks_reopen_when_review_finds_blocking_issue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(root, [CommandResult(0, "", ""), CommandResult(0, "verification ok", "")])
            manager = WorkflowManager(
                root,
                command_runner=runner,
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: True,
            )

            metadata = manager.create_task("Reopen workflow", "Generate artifacts")
            manager.advance_task(metadata.task_id, "spec")
            manager.advance_task(metadata.task_id, "implement")
            manager.verify_task(metadata.task_id)
            manager.advance_task(metadata.task_id, "review")
            review_path = root / "tasks" / metadata.task_id / "review.md"
            review_path.write_text(
                "# Review\n\n"
                "## Summary\n\n"
                "Found one blocking issue.\n\n"
                "## Findings\n\n"
                "### Finding F001\n"
                "- Severity: high\n"
                "- Status: open\n"
                "- Summary: Something is still wrong.\n",
                encoding="utf-8",
            )
            manager.review_task(metadata.task_id)

            tasks_text = (root / "openspec" / "changes" / metadata.change_name / "tasks.md").read_text(encoding="utf-8")
            self.assertIn("- [x] 2.1", tasks_text)
            self.assertIn("- [ ] 2.2", tasks_text)


class WorkflowManagerTests(unittest.TestCase):
    def test_autopilot_advances_successful_task_to_release_and_writes_process_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(root, [CommandResult(0, "", ""), CommandResult(0, "verification ok", "")])
            manager = WorkflowManager(
                root,
                command_runner=runner,
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: True,
            )
            metadata = manager.create_task("Autopilot workflow", "Automate the local workflow")

            result = manager.autopilot_task(metadata.task_id)

            updated, _ = manager.get_task(metadata.task_id)
            self.assertEqual(updated.current_stage, "release")
            self.assertEqual(result.final_stage, "release")
            self.assertTrue(result.ready_for_completion)
            self.assertIn("release-ready", result.stop_reason)
            implementation_text = (root / "tasks" / metadata.task_id / "implementation.md").read_text(encoding="utf-8")
            review_text = (root / "tasks" / metadata.task_id / "review.md").read_text(encoding="utf-8")
            release_text = (root / "tasks" / metadata.task_id / "release.md").read_text(encoding="utf-8")
            self.assertIn("OpenSpec change:", implementation_text)
            self.assertIn("no blocking issues", review_text.lower())
            self.assertIn("Ready to archive", release_text)

    def test_autopilot_stops_in_fix_when_verification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(root, [CommandResult(0, "", ""), CommandResult(1, "", "verification failed")])
            manager = WorkflowManager(
                root,
                command_runner=runner,
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: True,
            )
            metadata = manager.create_task("Autopilot fix workflow", "Automate the local workflow")

            result = manager.autopilot_task(metadata.task_id)

            updated, _ = manager.get_task(metadata.task_id)
            self.assertEqual(updated.current_stage, "fix")
            self.assertEqual(result.final_stage, "fix")
            self.assertFalse(result.ready_for_completion)
            self.assertIn("code changes required", result.stop_reason)
            review_text = (root / "tasks" / metadata.task_id / "review.md").read_text(encoding="utf-8")
            fixes_text = (root / "tasks" / metadata.task_id / "fixes.md").read_text(encoding="utf-8")
            self.assertIn("Severity: high", review_text)
            self.assertIn("verification failed", review_text.lower())
            self.assertIn("apply code changes", fixes_text.lower())

    def test_run_command_uses_windows_cmd_shim_for_openspec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(root)

            with patch("scheduler_automation.workflow.os.name", "nt"), patch(
                "scheduler_automation.workflow.shutil.which"
            ) as which_mock, patch("scheduler_automation.workflow.subprocess.run") as run_mock:
                which_mock.side_effect = lambda name: (
                    "C:\\Users\\SZH\\AppData\\Roaming\\npm\\openspec.cmd" if name == "openspec.cmd" else None
                )
                run_mock.return_value.returncode = 0
                run_mock.return_value.stdout = "ok"
                run_mock.return_value.stderr = ""

                manager._run_command(["openspec", "--help"])

            self.assertEqual(run_mock.call_args.args[0][0], "C:\\Users\\SZH\\AppData\\Roaming\\npm\\openspec.cmd")
            self.assertEqual(run_mock.call_args.kwargs["encoding"], "utf-8")
            self.assertEqual(run_mock.call_args.kwargs["errors"], "replace")

    def test_create_task_creates_openspec_change_and_tracks_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(root)
            manager = WorkflowManager(root, command_runner=runner)

            metadata = manager.create_task("Ship workflow", "Need a gated workflow")

            self.assertEqual(metadata.change_name, "ship-workflow")
            self.assertEqual(metadata.change_path, "openspec/changes/ship-workflow")
            self.assertEqual(runner.commands[0], ["openspec", "new", "change", "ship-workflow"])
            self.assertTrue((root / metadata.change_path / ".openspec.yaml").exists())

    def test_create_task_timestamps_use_shanghai_timezone(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(root, command_runner=RecordingRunner(root))

            metadata = manager.create_task("Timezone workflow")

            self.assertTrue(metadata.created_at.endswith("+08:00"))
            self.assertTrue(metadata.updated_at.endswith("+08:00"))

    def test_advance_to_implement_requires_openspec_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(root, command_runner=RecordingRunner(root))
            metadata = manager.create_task("Advance workflow")

            manager.advance_task(metadata.task_id, "spec")

            with self.assertRaisesRegex(ValueError, "proposal.md"):
                manager.advance_task(metadata.task_id, "implement")

    def test_advance_to_implement_requires_openspec_specs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(root, command_runner=RecordingRunner(root))
            metadata = manager.create_task("Spec workflow")
            change_dir = root / "openspec" / "changes" / metadata.change_name
            (change_dir / "proposal.md").write_text("# Proposal\n\nReady.\n", encoding="utf-8")
            (change_dir / "design.md").write_text("# Design\n\nReady.\n", encoding="utf-8")
            (change_dir / "tasks.md").write_text("- [ ] First task\n", encoding="utf-8")
            self._write_local_spec_summary(root, metadata.task_id)
            manager.advance_task(metadata.task_id, "spec")

            with self.assertRaisesRegex(ValueError, "specs"):
                manager.advance_task(metadata.task_id, "implement")

    def test_verify_records_successful_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(root, [CommandResult(0, "", ""), CommandResult(0, "verification ok", "")])
            manager = WorkflowManager(root, command_runner=runner)
            metadata = manager.create_task("Verify workflow")

            result = manager.verify_task(metadata.task_id)

            implementation_path = root / "tasks" / metadata.task_id / "implementation.md"
            self.assertTrue(result.passed)
            self.assertIn("python -m unittest discover -s tests -v", result.command)
            self.assertIn("openspec validate --type change", result.command)
            self.assertIn("verification ok", implementation_path.read_text(encoding="utf-8"))

    def test_review_gate_requires_real_code_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def command_runner(command: list[str], cwd: Path | None = None) -> CommandResult:
                if command[:3] in (["openspec", "new", "change"], ["openspec.cmd", "new", "change"]):
                    change_name = command[3]
                    change_dir = root / "openspec" / "changes" / change_name
                    change_dir.mkdir(parents=True, exist_ok=True)
                    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
                    return CommandResult(returncode=0, stdout="", stderr="")
                if command == ["git", "rev-parse", "HEAD"]:
                    return CommandResult(returncode=0, stdout="deadbeef\n", stderr="")
                if command[:3] in (["openspec", "instructions", "apply"], ["openspec.cmd", "instructions", "apply"]):
                    return CommandResult(returncode=0, stdout='{"state":"ready","progress":{"total":4,"complete":1,"remaining":3}}', stderr="")
                if command[:3] in (["openspec", "status", "--change"], ["openspec.cmd", "status", "--change"]):
                    return CommandResult(returncode=0, stdout='{"schemaName":"spec-driven"}', stderr="")
                if command[:3] in (["openspec", "validate", "--type"], ["openspec.cmd", "validate", "--type"]):
                    return CommandResult(returncode=0, stdout='{"summary":{"totals":{"failed":0}}}', stderr="")
                if len(command) >= 4 and command[:3] == ["git", "diff", "--name-only"]:
                    return CommandResult(returncode=0, stdout="", stderr="")
                if command == ["git", "status", "--porcelain"]:
                    return CommandResult(returncode=0, stdout="", stderr="")
                if command[:4] == ["python", "-m", "unittest", "discover"]:
                    return CommandResult(returncode=0, stdout="verification ok", stderr="")
                return CommandResult(returncode=0, stdout="", stderr="")

            manager = WorkflowManager(root, command_runner=command_runner)
            metadata = manager.create_task("No code change workflow")
            self._write_spec_artifacts(root, metadata.change_name, "- [x] done\n")
            self._write_local_spec_summary(root, metadata.task_id)
            manager.advance_task(metadata.task_id, "spec")
            manager.advance_task(metadata.task_id, "implement")
            self._write_implementation_note(root, metadata.task_id, "Updated docs only.\n")
            manager.verify_task(metadata.task_id)

            with self.assertRaisesRegex(ValueError, "No code changes detected"):
                manager.advance_task(metadata.task_id, "review")

    def test_review_gate_ignores_preexisting_dirty_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status_calls = {"count": 0}

            def command_runner(command: list[str], cwd: Path | None = None) -> CommandResult:
                if command[:3] in (["openspec", "new", "change"], ["openspec.cmd", "new", "change"]):
                    change_name = command[3]
                    change_dir = root / "openspec" / "changes" / change_name
                    change_dir.mkdir(parents=True, exist_ok=True)
                    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
                    return CommandResult(returncode=0, stdout="", stderr="")
                if command == ["git", "rev-parse", "HEAD"]:
                    return CommandResult(returncode=0, stdout="deadbeef\n", stderr="")
                if command[:3] in (["openspec", "instructions", "apply"], ["openspec.cmd", "instructions", "apply"]):
                    return CommandResult(returncode=0, stdout='{"state":"ready","progress":{"total":4,"complete":1,"remaining":3}}', stderr="")
                if command[:3] in (["openspec", "status", "--change"], ["openspec.cmd", "status", "--change"]):
                    return CommandResult(returncode=0, stdout='{"schemaName":"spec-driven"}', stderr="")
                if command[:3] in (["openspec", "validate", "--type"], ["openspec.cmd", "validate", "--type"]):
                    return CommandResult(returncode=0, stdout='{"summary":{"totals":{"failed":0}}}', stderr="")
                if len(command) >= 4 and command[:3] == ["git", "diff", "--name-only"]:
                    return CommandResult(returncode=0, stdout="", stderr="")
                if command == ["git", "status", "--porcelain"]:
                    status_calls["count"] += 1
                    return CommandResult(returncode=0, stdout=" M src/scheduler_automation/workflow.py\n", stderr="")
                if command[:4] == ["python", "-m", "unittest", "discover"]:
                    return CommandResult(returncode=0, stdout="verification ok", stderr="")
                return CommandResult(returncode=0, stdout="", stderr="")

            manager = WorkflowManager(root, command_runner=command_runner)
            metadata = manager.create_task("Pre-dirty workflow")
            self._write_spec_artifacts(root, metadata.change_name, "- [x] done\n")
            self._write_local_spec_summary(root, metadata.task_id)
            manager.advance_task(metadata.task_id, "spec")
            manager.advance_task(metadata.task_id, "implement")
            self._write_implementation_note(root, metadata.task_id, "Touched pre-existing dirty file only.\n")
            manager.verify_task(metadata.task_id)

            with self.assertRaisesRegex(ValueError, "No code changes detected"):
                manager.advance_task(metadata.task_id, "review")
            self.assertGreaterEqual(status_calls["count"], 2)

    def test_review_gate_allows_committed_changes_even_if_path_was_initially_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status_calls = {"count": 0}

            def command_runner(command: list[str], cwd: Path | None = None) -> CommandResult:
                if command[:3] in (["openspec", "new", "change"], ["openspec.cmd", "new", "change"]):
                    change_name = command[3]
                    change_dir = root / "openspec" / "changes" / change_name
                    change_dir.mkdir(parents=True, exist_ok=True)
                    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
                    return CommandResult(returncode=0, stdout="", stderr="")
                if command == ["git", "rev-parse", "HEAD"]:
                    return CommandResult(returncode=0, stdout="deadbeef\n", stderr="")
                if command[:3] in (["openspec", "instructions", "apply"], ["openspec.cmd", "instructions", "apply"]):
                    return CommandResult(returncode=0, stdout='{"state":"ready","progress":{"total":4,"complete":1,"remaining":3}}', stderr="")
                if command[:3] in (["openspec", "status", "--change"], ["openspec.cmd", "status", "--change"]):
                    return CommandResult(returncode=0, stdout='{"schemaName":"spec-driven"}', stderr="")
                if command[:3] in (["openspec", "validate", "--type"], ["openspec.cmd", "validate", "--type"]):
                    return CommandResult(returncode=0, stdout='{"summary":{"totals":{"failed":0}}}', stderr="")
                if len(command) >= 4 and command[:3] == ["git", "diff", "--name-only"]:
                    return CommandResult(returncode=0, stdout="src/scheduler_automation/workflow.py\n", stderr="")
                if command == ["git", "status", "--porcelain"]:
                    status_calls["count"] += 1
                    return CommandResult(returncode=0, stdout=" M src/scheduler_automation/workflow.py\n", stderr="")
                if command[:4] == ["python", "-m", "unittest", "discover"]:
                    return CommandResult(returncode=0, stdout="verification ok", stderr="")
                return CommandResult(returncode=0, stdout="", stderr="")

            manager = WorkflowManager(root, command_runner=command_runner)
            metadata = manager.create_task("Committed over pre-dirty")
            self._write_spec_artifacts(root, metadata.change_name, "- [x] done\n")
            self._write_local_spec_summary(root, metadata.task_id)
            manager.advance_task(metadata.task_id, "spec")
            manager.advance_task(metadata.task_id, "implement")
            self._write_implementation_note(root, metadata.task_id, "Committed a real code change.\n")
            manager.verify_task(metadata.task_id)

            updated = manager.advance_task(metadata.task_id, "review")
            self.assertEqual(updated.current_stage, "review")
            self.assertGreaterEqual(status_calls["count"], 2)

    def test_review_blocks_release_when_high_finding_is_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(root, [CommandResult(0, "tests passed", "")])
            manager = WorkflowManager(root, command_runner=runner)
            metadata = manager.create_task("Review workflow")
            self._write_spec_artifacts(root, metadata.change_name, "- [x] done\n")
            self._write_local_spec_summary(root, metadata.task_id)
            manager.advance_task(metadata.task_id, "spec")
            manager.advance_task(metadata.task_id, "implement")
            self._write_implementation_note(root, metadata.task_id, "Implemented the workflow engine.\n")
            manager.verify_task(metadata.task_id)
            manager.advance_task(metadata.task_id, "review")

            review_path = root / "tasks" / metadata.task_id / "review.md"
            review_path.write_text(
                "# Review\n\n"
                "## Summary\n\n"
                "Reviewed workflow changes.\n\n"
                "## Findings\n\n"
                "### Finding F001\n"
                "- Severity: high\n"
                "- Status: open\n"
                "- Summary: Release gate can be bypassed.\n",
                encoding="utf-8",
            )

            summary = manager.review_task(metadata.task_id)

            self.assertEqual(summary.open_by_severity["high"], 1)
            self.assertIn("high severity", " ".join(manager.validate_stage_transition(metadata.task_id, "release")))

    def test_complete_task_archives_change_and_runs_git_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(
                root,
                [
                    CommandResult(0, "tests passed", ""),
                    CommandResult(0, "", ""),
                    CommandResult(0, "", ""),
                    CommandResult(0, "", ""),
                ],
            )
            manager = WorkflowManager(root, command_runner=runner)
            metadata = manager.create_task("Complete workflow")
            self._write_spec_artifacts(root, metadata.change_name, "- [x] done\n")
            self._write_local_spec_summary(root, metadata.task_id)
            manager.advance_task(metadata.task_id, "spec")
            manager.advance_task(metadata.task_id, "implement")
            self._write_implementation_note(root, metadata.task_id, "Implemented the workflow engine.\n")
            manager.verify_task(metadata.task_id)
            manager.advance_task(metadata.task_id, "review")
            self._write_review_summary(root, metadata.task_id)
            manager.review_task(metadata.task_id)
            manager.advance_task(metadata.task_id, "release")
            self._write_release_summary(root, metadata.task_id)

            result = manager.complete_task(metadata.task_id)

            archive_dir = root / result.archive_path
            self.assertTrue(archive_dir.exists())
            self.assertIn(["git", "add", "."], runner.commands)
            self.assertIn(
                ["git", "commit", "-m", f"chore: complete {metadata.task_id} ({metadata.change_name})"],
                runner.commands,
            )
            self.assertIn(["git", "push", "--set-upstream", "origin", "HEAD"], runner.commands)
            completion_path = root / "tasks" / metadata.task_id / "completion.json"
            self.assertTrue(completion_path.exists())
            completion = json.loads(completion_path.read_text(encoding="utf-8"))
            self.assertEqual(completion["task_id"], metadata.task_id)
            self.assertEqual(completion["archive_path"], result.archive_path)
            self.assertEqual(completion["commit_message"], result.commit_message)
            self.assertTrue(completion["commands"]["git_push"]["ok"])

    def _write_spec_artifacts(self, root: Path, change_name: str, tasks_content: str) -> None:
        change_dir = root / "openspec" / "changes" / change_name
        (change_dir / "proposal.md").write_text("# Proposal\n\nReady.\n", encoding="utf-8")
        (change_dir / "design.md").write_text("# Design\n\nReady.\n", encoding="utf-8")
        specs_dir = change_dir / "specs" / change_name
        specs_dir.mkdir(parents=True, exist_ok=True)
        (specs_dir / "spec.md").write_text("## ADDED Requirements\n\nReady.\n", encoding="utf-8")
        (change_dir / "tasks.md").write_text(tasks_content, encoding="utf-8")

    def _write_local_spec_summary(self, root: Path, task_id: str) -> None:
        spec_path = root / "tasks" / task_id / "spec.md"
        spec_path.write_text(
            "# Spec\n\n"
            "## OpenSpec Change\n\n"
            "- Name: bound-change\n"
            "- Path: openspec/changes/bound-change\n\n"
            "## Summary\n\n"
            "This task implements the gated workflow engine.\n",
            encoding="utf-8",
        )

    def _write_implementation_note(self, root: Path, task_id: str, note: str) -> None:
        path = root / "tasks" / task_id / "implementation.md"
        path.write_text(
            "# Superpower Implementation\n\n"
            "## Plan\n\n"
            f"{note}\n"
            "## Verification\n\n"
            "- Pending\n",
            encoding="utf-8",
        )

    def _write_review_summary(self, root: Path, task_id: str) -> None:
        review_path = root / "tasks" / task_id / "review.md"
        review_path.write_text(
            "# Review\n\n"
            "## Summary\n\n"
            "Reviewed workflow changes and found no blocking issues.\n\n"
            "## Findings\n\n"
            "None.\n",
            encoding="utf-8",
        )

    def _write_release_summary(self, root: Path, task_id: str) -> None:
        release_path = root / "tasks" / task_id / "release.md"
        release_path.write_text(
            "# Release\n\n"
            "## Notes\n\n"
            "Archive this change and push it upstream.\n",
            encoding="utf-8",
        )


class CLITests(unittest.TestCase):
    def test_autopilot_command_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = io.StringIO()

            def manager_factory(
                current_root: Path,
                command_runner=None,
                artifact_generator=None,
                confirm_write=None,
            ):
                return WorkflowManager(
                    current_root,
                    command_runner=RecordingRunner(
                        current_root,
                        [CommandResult(0, "", ""), CommandResult(0, "verification ok", "")],
                    ),
                    artifact_generator=StubArtifactGenerator(),
                    confirm_write=lambda *_: True,
                )

            with (
                temporary_cwd(root),
                redirect_stdout(output),
                patch("scheduler_automation.cli.OpenSpecArtifactGenerator", return_value=StubArtifactGenerator()),
                patch("scheduler_automation.cli.WorkflowManager", side_effect=manager_factory),
                patch("builtins.input", return_value="y"),
            ):
                self.assertEqual(
                    cli.main(["new-task", "--title", "Autopilot CLI", "--request", "Run autopilot"]),
                    0,
                )

            created_line = next(
                line for line in output.getvalue().splitlines() if line.startswith("Created task:")
            )
            task_id = created_line.split("Created task: ", 1)[1].split(" | ", 1)[0]
            autopilot_output = io.StringIO()
            with (
                temporary_cwd(root),
                redirect_stdout(autopilot_output),
                patch("scheduler_automation.cli.WorkflowManager", side_effect=manager_factory),
            ):
                exit_code = cli.main(["autopilot", "--task", task_id])

            self.assertEqual(exit_code, 0)
            self.assertIn("stopped at release", autopilot_output.getvalue())

    def test_status_reports_blocked_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(root, command_runner=RecordingRunner(root))
            metadata = manager.create_task("CLI workflow")
            manager.advance_task(metadata.task_id, "spec")
            output = io.StringIO()

            with temporary_cwd(root), redirect_stdout(output):
                exit_code = cli.main(["status"])

            self.assertEqual(exit_code, 0)
            self.assertIn("BLOCKED", output.getvalue())

    def test_new_task_prints_generated_preview_before_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = io.StringIO()
            stub_generator = StubArtifactGenerator()

            def manager_factory(
                current_root: Path,
                command_runner=None,
                artifact_generator=None,
                confirm_write=None,
            ):
                return WorkflowManager(
                    current_root,
                    command_runner=RecordingRunner(current_root),
                    artifact_generator=artifact_generator,
                    confirm_write=confirm_write,
                )

            with (
                temporary_cwd(root),
                redirect_stdout(output),
                patch("scheduler_automation.cli.OpenSpecArtifactGenerator", return_value=stub_generator),
                patch("scheduler_automation.cli.WorkflowManager", side_effect=manager_factory),
                patch("builtins.input", return_value="y"),
            ):
                exit_code = cli.main(["new-task", "--title", "Preview workflow", "--request", "Generate preview"])

            self.assertEqual(exit_code, 0)
            self.assertIn("Generated proposal.md", output.getvalue())
            self.assertIn("Generated specs/generated/spec.md", output.getvalue())
            self.assertIn("Write generated artifacts", output.getvalue())


class DashboardTests(unittest.TestCase):
    def test_dashboard_lists_tasks_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(root, command_runner=RecordingRunner(root))
            metadata = manager.create_task("Dashboard workflow")
            manager.advance_task(metadata.task_id, "spec")
            app = DashboardApp(root, manager=manager)

            payload = app.build_task_list_payload()

            self.assertEqual(payload["tasks"][0]["state"], "Waiting for workflow input")
            self.assertEqual(payload["tasks"][0]["task_id"], metadata.task_id)
            self.assertIn("status_tone", payload["tasks"][0])
            self.assertFalse(payload["tasks"][0]["completed"])

    def test_dashboard_returns_task_detail_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(root, command_runner=RecordingRunner(root))
            metadata = manager.create_task("Dashboard detail")
            manager.advance_task(metadata.task_id, "spec")
            app = DashboardApp(root, manager=manager)

            detail = app.build_task_detail_payload(metadata.task_id)

            self.assertEqual(detail["task"]["current_stage"], "spec")
            self.assertEqual(detail["task"]["change_name"], metadata.change_name)
            self.assertIn("blocked_reasons", detail["task"])
            self.assertIn("suggested_actions", detail["task"])
            self.assertIn("timeline", detail["task"])
            self.assertIn("conclusion", detail["task"])
            self.assertIn("skill_pipeline", detail["task"])
            self.assertTrue(any(skill["skill"] == "brainstorming" for skill in detail["task"]["skill_pipeline"]))

    def test_dashboard_root_returns_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app = DashboardApp(root)

            status, content_type, body = app.handle_request("GET", "/")

            self.assertEqual(status, 200)
            self.assertEqual(content_type, "text/html; charset=utf-8")
            html = body.decode("utf-8")
            self.assertIn("continue-autopilot", html)
            self.assertIn("complete-task", html)
            self.assertIn("set-baseline", html)
            self.assertIn("new-task-title", html)
            self.assertIn("create-task", html)

    def test_dashboard_html_contains_task_panels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app = DashboardApp(root)

            html = app.render_index_html()

            self.assertIn('id="task-detail"', html)
            self.assertIn('id="task-list"', html)
            self.assertIn("stage-flow", html)
            self.assertIn("Skill Pipeline", html)

    def test_dashboard_missing_task_returns_404(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app = DashboardApp(root)

            status, content_type, body = app.handle_request("GET", "/api/tasks/missing-task")

            self.assertEqual(status, 404)
            self.assertEqual(content_type, "application/json; charset=utf-8")
            self.assertIn("error", body.decode("utf-8"))

    def test_dashboard_shows_blocker_aware_guidance_for_review_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(root, command_runner=RecordingRunner(root))
            metadata = manager.create_task(
                "Dashboard review guidance",
                "Show workflow progress in the browser",
            )
            change_dir = root / "openspec" / "changes" / metadata.change_name
            (change_dir / "proposal.md").write_text("# Proposal\n\nReady.\n", encoding="utf-8")
            (change_dir / "design.md").write_text("# Design\n\nReady.\n", encoding="utf-8")
            specs_dir = change_dir / "specs" / metadata.change_name
            specs_dir.mkdir(parents=True, exist_ok=True)
            (specs_dir / "spec.md").write_text("## ADDED Requirements\n\nReady.\n", encoding="utf-8")
            (change_dir / "tasks.md").write_text("- [ ] First task\n", encoding="utf-8")
            spec_path = root / "tasks" / metadata.task_id / "spec.md"
            spec_path.write_text(
                "# Spec\n\n"
                "## OpenSpec Change\n\n"
                f"- Name: {metadata.change_name}\n"
                f"- Path: {metadata.change_path}\n\n"
                "## Summary\n\n"
                "Show workflow progress in the browser\n\n"
                "## Acceptance Alignment\n\n"
                "- Review the generated OpenSpec artifacts before implementation.\n",
                encoding="utf-8",
            )
            implementation_path = root / "tasks" / metadata.task_id / "implementation.md"
            implementation_path.write_text(
                "# Superpower Implementation\n\n"
                "## Plan\n\n"
                "Use the generated OpenSpec artifacts for dashboard-demo as the implementation baseline.\n\n"
                "## Code changes\n\n"
                "- No implementation changes recorded yet.\n\n"
                "## Verification\n\n"
                "- Pending\n",
                encoding="utf-8",
            )
            manager.advance_task(metadata.task_id, "spec")
            manager.advance_task(metadata.task_id, "implement")
            manager.verify_task(metadata.task_id)
            manager.advance_task(metadata.task_id, "review")
            app = DashboardApp(root, manager=manager)

            detail = app.build_task_detail_payload(metadata.task_id)

            self.assertEqual(detail["task"]["next_action"], "resolve blockers")
            self.assertTrue(any("autopilot" in step for step in detail["task"]["suggested_actions"]))
            self.assertTrue(any("synchronized automatically" in step for step in detail["task"]["suggested_actions"]))

    def test_dashboard_can_trigger_autopilot_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(
                root,
                command_runner=RecordingRunner(root, [CommandResult(0, "", ""), CommandResult(0, "verification ok", "")]),
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: True,
            )
            metadata = manager.create_task("Dashboard autopilot", "Run from dashboard")
            app = DashboardApp(root, manager=manager)

            status, content_type, body = app.handle_request("POST", f"/api/tasks/{metadata.task_id}/autopilot")

            payload = json.loads(body.decode("utf-8"))
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/json; charset=utf-8")
            self.assertEqual(payload["result"]["final_stage"], "release")
            self.assertEqual(payload["task"]["current_stage"], "release")

    def test_dashboard_can_trigger_complete_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = RecordingRunner(
                root,
                [
                    CommandResult(0, "", ""),
                    CommandResult(0, "verification ok", ""),
                    CommandResult(0, "", ""),
                    CommandResult(0, "", ""),
                    CommandResult(0, "", ""),
                ],
            )
            manager = WorkflowManager(
                root,
                command_runner=runner,
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: True,
            )
            metadata = manager.create_task("Dashboard complete", "Complete from dashboard")
            manager.autopilot_task(metadata.task_id)
            app = DashboardApp(root, manager=manager)

            status, content_type, body = app.handle_request("POST", f"/api/tasks/{metadata.task_id}/complete")

            payload = json.loads(body.decode("utf-8"))
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/json; charset=utf-8")
            self.assertIn("archive_path", payload["result"])
            self.assertTrue(payload["task"]["completed"])

    def test_dashboard_can_create_task_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = WorkflowManager(
                root,
                command_runner=RecordingRunner(root, [CommandResult(0, "", ""), CommandResult(0, "verification ok", "")]),
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: True,
            )
            app = DashboardApp(root, manager=manager)

            request = {
                "title": "Task from dashboard",
                "request": "Create and run from dashboard",
                "run_autopilot": True,
            }
            status, content_type, body = app.handle_request(
                "POST",
                "/api/tasks",
                json.dumps(request).encode("utf-8"),
            )

            payload = json.loads(body.decode("utf-8"))
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/json; charset=utf-8")
            self.assertIn("task_id", payload["task"])
            self.assertEqual(payload["result"]["action"], "create_task")
            self.assertIn(payload["task"]["current_stage"], {"review", "release", "fix"})

    def test_dashboard_detail_includes_git_compare_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rev_parse_calls = {"count": 0}

            def command_runner(command: list[str], cwd: Path | None = None) -> CommandResult:
                if command[:3] in (["openspec", "new", "change"], ["openspec.cmd", "new", "change"]):
                    change_name = command[3]
                    change_dir = root / "openspec" / "changes" / change_name
                    change_dir.mkdir(parents=True, exist_ok=True)
                    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
                    return CommandResult(returncode=0, stdout="", stderr="")
                if command == ["git", "rev-parse", "HEAD"]:
                    rev_parse_calls["count"] += 1
                    sha = "base123" if rev_parse_calls["count"] == 1 else "head456"
                    return CommandResult(returncode=0, stdout=f"{sha}\n", stderr="")
                if command == ["git", "diff", "--numstat", "base123..head456", "--"]:
                    return CommandResult(
                        returncode=0,
                        stdout="12\t3\tsrc/scheduler_automation/dashboard.py\n2\t0\ttests/test_workflow.py\n",
                        stderr="",
                    )
                if command == ["git", "status", "--porcelain"]:
                    return CommandResult(returncode=0, stdout=" M src/scheduler_automation/workflow.py\n", stderr="")
                return CommandResult(returncode=0, stdout="", stderr="")

            manager = WorkflowManager(
                root,
                command_runner=command_runner,
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: True,
            )
            metadata = manager.create_task("Compare dashboard", "Show git compare in dashboard")
            app = DashboardApp(root, manager=manager)

            detail = app.build_task_detail_payload(metadata.task_id)

            compare = detail["task"]["compare"]
            self.assertTrue(compare["available"])
            self.assertEqual(compare["base_commit"], "base123")
            self.assertEqual(compare["head_commit"], "head456")
            self.assertEqual(compare["commit_range"], "base123..head456")
            self.assertEqual(compare["baseline_source"], "task")
            self.assertEqual(compare["totals"]["files"], 2)
            self.assertEqual(compare["totals"]["added"], 14)
            self.assertEqual(compare["totals"]["deleted"], 3)
            self.assertEqual(compare["working_tree"][0]["path"], "src/scheduler_automation/workflow.py")
            self.assertEqual(len(compare["related_committed_files"]), 2)
            self.assertEqual(compare["hidden_committed_count"], 0)

    def test_dashboard_compare_requires_explicit_task_baseline_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def command_runner(command: list[str], cwd: Path | None = None) -> CommandResult:
                if command[:3] in (["openspec", "new", "change"], ["openspec.cmd", "new", "change"]):
                    change_name = command[3]
                    change_dir = root / "openspec" / "changes" / change_name
                    change_dir.mkdir(parents=True, exist_ok=True)
                    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
                    return CommandResult(returncode=0, stdout="", stderr="")
                if command == ["git", "rev-parse", "HEAD"]:
                    return CommandResult(returncode=0, stdout="head456\n", stderr="")
                if command == ["git", "diff", "--numstat", "head456..head456", "--"]:
                    return CommandResult(returncode=0, stdout="4\t1\tsrc/scheduler_automation/cli.py\n", stderr="")
                if command == ["git", "status", "--porcelain"]:
                    return CommandResult(returncode=0, stdout="", stderr="")
                return CommandResult(returncode=0, stdout="", stderr="")

            manager = WorkflowManager(
                root,
                command_runner=command_runner,
                artifact_generator=StubArtifactGenerator(),
                confirm_write=lambda *_: True,
            )
            metadata = manager.create_task("Legacy compare", "Show compare for old task")
            metadata_file = root / "tasks" / metadata.task_id / "metadata.json"
            metadata_payload = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata_payload["base_commit"] = None
            metadata_file.write_text(json.dumps(metadata_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            app = DashboardApp(root, manager=manager)

            detail = app.build_task_detail_payload(metadata.task_id)

            compare = detail["task"]["compare"]
            self.assertFalse(compare["available"])
            self.assertEqual(compare["baseline_source"], "none")
            self.assertIn("baseline is missing", compare["reason"])
            self.assertIsNone(compare["base_commit"])
            self.assertEqual(compare["head_commit"], "head456")

            status, content_type, body = app.handle_request("POST", f"/api/tasks/{metadata.task_id}/baseline")
            payload = json.loads(body.decode("utf-8"))
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/json; charset=utf-8")
            self.assertEqual(payload["result"]["action"], "baseline")
            self.assertEqual(payload["result"]["base_commit"], "head456")
            self.assertTrue(payload["task"]["compare"]["available"])


if __name__ == "__main__":
    unittest.main()
