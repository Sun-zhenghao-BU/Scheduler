from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable

from scheduler_automation.artifact_generation import GeneratedArtifacts


STAGES = ("intake", "spec", "implement", "review", "fix", "release")
ALLOWED_TRANSITIONS = {
    "intake": {"spec"},
    "spec": {"implement"},
    "implement": {"review"},
    "review": {"fix", "release"},
    "fix": {"review"},
    "release": set(),
}
PLACEHOLDER_PREFIXES = (
    "replace this line",
    "fill in",
    "define ",
    "record ",
    "describe ",
    "break work into",
    "add ",
    "pending",
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "task"


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class TaskMetadata:
    task_id: str
    title: str
    current_stage: str
    created_at: str
    updated_at: str
    change_name: str
    change_path: str
    blocked: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    last_verified_at: str | None = None
    last_verification_passed: bool | None = None
    last_reviewed_at: str | None = None
    ready_for_release: bool = False
    base_commit: str | None = None


@dataclass
class TaskProgress:
    total: int
    complete: int
    incomplete: int


@dataclass
class ReviewFinding:
    finding_id: str
    severity: str
    status: str
    summary: str


@dataclass
class ReviewSummary:
    findings: list[ReviewFinding]
    open_by_severity: dict[str, int]


@dataclass
class VerificationResult:
    passed: bool
    command: str
    stdout: str
    stderr: str
    timestamp: str


@dataclass
class TaskSnapshot:
    metadata: TaskMetadata
    blocked_reasons: list[str]
    next_action: str
    suggested_actions: list[str]
    progress: TaskProgress
    review_summary: ReviewSummary


@dataclass
class CompletionResult:
    archive_path: str
    commit_message: str
    commit_sha: str | None = None
    evidence_path: str | None = None


@dataclass
class AutopilotResult:
    task_id: str
    final_stage: str
    stop_reason: str
    actions: list[str]
    ready_for_completion: bool


CommandRunner = Callable[[list[str], Path | None], CommandResult]
ConfirmWrite = Callable[[str, GeneratedArtifacts], bool]


class WorkflowManager:
    # WorkflowManager is the single orchestration entrypoint for the local loop:
    # create task -> bind OpenSpec change -> enforce stage gates -> verify/review -> complete.
    def __init__(
        self,
        root: Path,
        command_runner: CommandRunner | None = None,
        artifact_generator: object | None = None,
        confirm_write: ConfirmWrite | None = None,
    ) -> None:
        self.root = root
        self.tasks_dir = self.root / "tasks"
        self.changes_dir = self.root / "openspec" / "changes"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.changes_dir.mkdir(parents=True, exist_ok=True)
        self.command_runner = command_runner or self._run_command
        self.artifact_generator = artifact_generator
        self.confirm_write = confirm_write or (lambda _change_name, _artifacts: True)

    def create_task(self, title: str, request: str = "") -> TaskMetadata:
        # Task creation always starts by binding the local workspace to exactly one OpenSpec change.
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_id = f"{timestamp}-{slugify(title)}"
        task_dir = self.tasks_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=False)

        change_name = self._unique_change_name(slugify(title))
        result = self.command_runner(["openspec", "new", "change", change_name], self.root)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "OpenSpec change creation failed.")

        change_dir = self._change_dir(change_name)
        if not change_dir.exists():
            raise RuntimeError(f"OpenSpec change '{change_name}' was not created.")

        now = utc_timestamp()
        metadata = TaskMetadata(
            task_id=task_id,
            title=title.strip(),
            current_stage="intake",
            created_at=now,
            updated_at=now,
            change_name=change_name,
            change_path=self._relative_to_root(change_dir),
            base_commit=self._current_head_commit(),
        )
        self._write_metadata(task_dir, metadata)

        files = {
            "request.md": self._request_template(title, request),
            "spec.md": self._spec_template(change_name, metadata.change_path),
            "implementation.md": self._implementation_template(),
            "review.md": self._review_template(),
            "fixes.md": self._fixes_template(),
            "release.md": self._release_template(),
            "journal.md": self._journal_template(),
        }
        for name, content in files.items():
            (task_dir / name).write_text(content, encoding="utf-8")

        if self.artifact_generator is not None:
            artifacts = self._generate_artifacts(title=title, request=request, change_name=change_name)
            approved = self.confirm_write(change_name, artifacts)
            if approved:
                self._write_generated_artifacts(change_dir, artifacts)
                self._populate_local_spec_summary(task_dir / "spec.md", request or title)
                self._populate_implementation_seed(task_dir / "implementation.md", change_name, request or title)
                self._sync_managed_tasks_for(metadata, task_dir)
                self.append_log(task_id, "intake", "Generated OpenSpec artifacts")
            else:
                self.append_log(task_id, "intake", "Generated OpenSpec artifacts were rejected")

        self.append_log(task_id, "intake", f"Created bound OpenSpec change {change_name}")
        return self.get_task(task_id)[0]

    def list_tasks(self) -> list[TaskMetadata]:
        results: list[TaskMetadata] = []
        for task_dir in sorted(self.tasks_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            metadata_file = task_dir / "metadata.json"
            if metadata_file.exists():
                results.append(self._read_metadata(metadata_file))
        return results

    def list_task_snapshots(self) -> list[TaskSnapshot]:
        return [self.task_snapshot(task.task_id) for task in self.list_tasks()]

    def get_task(self, task_id: str) -> tuple[TaskMetadata, Path]:
        task_dir = self.tasks_dir / task_id
        metadata_file = task_dir / "metadata.json"
        if not metadata_file.exists():
            raise FileNotFoundError(f"Task '{task_id}' does not exist.")
        return self._read_metadata(metadata_file), task_dir

    def advance_task(self, task_id: str, stage: str) -> TaskMetadata:
        # Stage transitions are the main control point. Every move is validated before metadata changes.
        if stage not in STAGES:
            raise ValueError(f"Unsupported stage '{stage}'. Expected one of: {', '.join(STAGES)}")
        metadata, task_dir = self.get_task(task_id)
        reasons = self.validate_stage_transition(task_id, stage)
        if reasons:
            metadata.blocked = True
            metadata.blocked_reasons = reasons
            metadata.updated_at = utc_timestamp()
            self._write_metadata(task_dir, metadata)
            raise ValueError("; ".join(reasons))

        metadata.current_stage = stage
        metadata.updated_at = utc_timestamp()
        metadata.blocked = False
        metadata.blocked_reasons = []
        self._write_metadata(task_dir, metadata)
        self._sync_managed_tasks_for(metadata, task_dir)
        metadata.ready_for_release = not self._release_gate_reasons_for(metadata, task_dir)
        self._write_metadata(task_dir, metadata)
        self.append_log(task_id, stage, f"Stage advanced to {stage}")
        return self.get_task(task_id)[0]

    def append_log(self, task_id: str, stage: str, message: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"Unsupported stage '{stage}'. Expected one of: {', '.join(STAGES)}")
        metadata, task_dir = self.get_task(task_id)
        journal_path = task_dir / "journal.md"
        entry = f"- {utc_timestamp()} [{stage}] {message.strip()}\n"
        with journal_path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        metadata.updated_at = utc_timestamp()
        self._write_metadata(task_dir, metadata)

    def verify_task(self, task_id: str) -> VerificationResult:
        # Verification is persisted as evidence, not just printed, so release gates can rely on it later.
        metadata, task_dir = self.get_task(task_id)
        command = ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
        result = self.command_runner(command, self.root)
        timestamp = utc_timestamp()
        verification = VerificationResult(
            passed=result.returncode == 0,
            command=" ".join(command),
            stdout=result.stdout,
            stderr=result.stderr,
            timestamp=timestamp,
        )
        self._append_verification(task_dir / "implementation.md", verification)
        metadata.last_verified_at = timestamp
        metadata.last_verification_passed = verification.passed
        metadata.updated_at = timestamp
        self._write_metadata(task_dir, metadata)
        self._sync_managed_tasks_for(metadata, task_dir)
        metadata.ready_for_release = not self._release_gate_reasons_for(metadata, task_dir)
        self._write_metadata(task_dir, metadata)
        state = "passed" if verification.passed else "failed"
        self.append_log(task_id, metadata.current_stage, f"Verification {state}")
        return verification

    def review_task(self, task_id: str) -> ReviewSummary:
        # Review reads structured findings from review.md and turns them into gateable state.
        metadata, task_dir = self.get_task(task_id)
        findings = self._parse_review_findings(task_dir / "review.md")
        has_summary = self._section_has_meaningful_content(task_dir / "review.md", "## Summary")
        if not findings and not has_summary:
            raise ValueError("review.md does not contain review notes.")

        open_by_severity = {"high": 0, "medium": 0, "low": 0}
        for finding in findings:
            if finding.status == "open":
                open_by_severity[finding.severity] = open_by_severity.get(finding.severity, 0) + 1

        metadata.last_reviewed_at = utc_timestamp()
        metadata.updated_at = metadata.last_reviewed_at
        self._write_metadata(task_dir, metadata)
        self._sync_managed_tasks_for(metadata, task_dir)
        metadata.ready_for_release = not self._release_gate_reasons_for(metadata, task_dir)
        self._write_metadata(task_dir, metadata)
        self.append_log(task_id, metadata.current_stage, "Recorded self-review")
        return ReviewSummary(findings=findings, open_by_severity=open_by_severity)

    def complete_task(self, task_id: str) -> CompletionResult:
        # Completion is intentionally strict: only release-stage tasks that still satisfy every final gate
        # may archive the change and trigger git commit/push.
        metadata, task_dir = self.get_task(task_id)
        if metadata.current_stage != "release":
            raise ValueError("Task must be in release stage before completion.")

        reasons = self._complete_gate_reasons(task_id)
        if reasons:
            raise ValueError("; ".join(reasons))

        archive_path = self._archive_change(metadata.change_name)
        commit_message = f"chore: complete {metadata.task_id} ({metadata.change_name})"
        command_results: dict[str, dict[str, object]] = {}

        metadata.change_path = archive_path
        metadata.updated_at = utc_timestamp()
        metadata.ready_for_release = False
        self._write_metadata(task_dir, metadata)

        commands = (
            ("git_add", ["git", "add", "."]),
            ("git_commit", ["git", "commit", "-m", commit_message]),
            ("git_push", ["git", "push", "--set-upstream", "origin", "HEAD"]),
        )
        for label, command in commands:
            result = self.command_runner(command, self.root)
            command_results[label] = {
                "ok": result.returncode == 0,
                "returncode": result.returncode,
                "stderr": result.stderr.strip(),
                "stdout": result.stdout.strip(),
            }
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"Command failed: {' '.join(command)}")

        commit_sha = self._current_head_commit()
        completion_path = self._write_completion_evidence(
            task_dir=task_dir,
            metadata=metadata,
            archive_path=archive_path,
            commit_message=commit_message,
            commit_sha=commit_sha,
            command_results=command_results,
        )
        self._append_release_record(
            task_dir / "release.md",
            archive_path,
            commit_message,
            commit_sha,
            self._relative_to_root(completion_path),
        )
        self.append_log(task_id, "release", f"Completed task and archived {metadata.change_name}")
        return CompletionResult(
            archive_path=archive_path,
            commit_message=commit_message,
            commit_sha=commit_sha,
            evidence_path=self._relative_to_root(completion_path),
        )

    def autopilot_task(self, task_id: str) -> AutopilotResult:
        actions: list[str] = []

        while True:
            metadata, task_dir = self.get_task(task_id)

            if metadata.current_stage == "intake":
                self.advance_task(task_id, "spec")
                actions.append("advanced to spec")
                continue

            if metadata.current_stage == "spec":
                self._ensure_local_spec_summary(task_dir, metadata)
                implement_reasons = self.validate_stage_transition(task_id, "implement")
                if implement_reasons:
                    return self._autopilot_result(task_id, metadata.current_stage, implement_reasons, actions, False)
                self.advance_task(task_id, "implement")
                actions.append("advanced to implement")
                continue

            if metadata.current_stage == "implement":
                self._write_autopilot_implementation(task_dir, metadata)
                verification = self.verify_task(task_id)
                actions.append(f"verification {'passed' if verification.passed else 'failed'}")
                self._write_autopilot_implementation(task_dir, self.get_task(task_id)[0])
                self.advance_task(task_id, "review")
                actions.append("advanced to review")
                continue

            if metadata.current_stage == "review":
                review_summary = self._write_autopilot_review(task_id)
                actions.append("recorded automated review")
                if review_summary.open_by_severity.get("high", 0):
                    self.advance_task(task_id, "fix")
                    actions.append("advanced to fix")
                    metadata, task_dir = self.get_task(task_id)
                    self._write_autopilot_fixes(task_dir, metadata, review_summary)
                    return AutopilotResult(
                        task_id=task_id,
                        final_stage="fix",
                        stop_reason="code changes required before autopilot can continue",
                        actions=actions,
                        ready_for_completion=False,
                    )

                self.advance_task(task_id, "release")
                actions.append("advanced to release")
                metadata, task_dir = self.get_task(task_id)
                self._write_autopilot_release(task_dir, metadata)
                return AutopilotResult(
                    task_id=task_id,
                    final_stage="release",
                    stop_reason="release-ready: run complete when you want to archive, commit, and push",
                    actions=actions,
                    ready_for_completion=True,
                )

            if metadata.current_stage == "fix":
                review_summary = self._review_summary(task_id)
                self._write_autopilot_fixes(task_dir, metadata, review_summary)
                return AutopilotResult(
                    task_id=task_id,
                    final_stage="fix",
                    stop_reason="code changes required before autopilot can continue",
                    actions=actions,
                    ready_for_completion=False,
                )

            if metadata.current_stage == "release":
                self._write_autopilot_release(task_dir, metadata)
                return AutopilotResult(
                    task_id=task_id,
                    final_stage="release",
                    stop_reason="release-ready: run complete when you want to archive, commit, and push",
                    actions=actions,
                    ready_for_completion=True,
                )

    def validate_stage_transition(self, task_id: str, stage: str) -> list[str]:
        # This is the central gate dispatcher. Each target stage has its own minimal requirements.
        metadata, task_dir = self.get_task(task_id)
        if stage == metadata.current_stage:
            return [f"Task is already in stage '{stage}'."]

        allowed = ALLOWED_TRANSITIONS.get(metadata.current_stage, set())
        if stage not in allowed:
            allowed_text = ", ".join(sorted(allowed)) or "no further stages"
            return [f"Cannot move from {metadata.current_stage} to {stage}. Allowed: {allowed_text}."]

        if stage == "spec":
            return self._gate_spec(metadata)
        if stage == "implement":
            return self._gate_implement(metadata, task_dir)
        if stage == "review":
            return self._gate_review(metadata, task_dir)
        if stage == "fix":
            return self._gate_fix(task_dir)
        if stage == "release":
            return self._release_gate_reasons(task_id)
        return []

    def task_snapshot(self, task_id: str) -> TaskSnapshot:
        # Snapshots power `status` and `show`: they combine persisted metadata with live gate evaluation.
        metadata, task_dir = self.get_task(task_id)
        self._sync_managed_tasks_for(metadata, task_dir)
        review_summary = self._review_summary(task_id)
        progress = self._tasks_progress(metadata.change_name)
        blocked_reasons = self._next_action_reasons(task_id, metadata.current_stage, review_summary)
        planned_action = self._next_action(metadata.current_stage, review_summary)
        next_action = "resolve blockers" if blocked_reasons else planned_action
        suggested_actions = self._suggested_actions(task_id, metadata, planned_action, blocked_reasons)
        return TaskSnapshot(
            metadata=metadata,
            blocked_reasons=blocked_reasons,
            next_action=next_action,
            suggested_actions=suggested_actions,
            progress=progress,
            review_summary=review_summary,
        )

    def render_task(self, task_id: str) -> str:
        snapshot = self.task_snapshot(task_id)
        metadata = snapshot.metadata
        lines = [
            f"Task ID: {metadata.task_id}",
            f"Title: {metadata.title}",
            f"Current stage: {metadata.current_stage}",
            f"OpenSpec change: {metadata.change_name}",
            f"Change path: {metadata.change_path}",
            f"Next action: {snapshot.next_action}",
            f"OpenSpec tasks: {snapshot.progress.complete}/{snapshot.progress.total} complete",
            f"Verification: {self._verification_label(metadata)}",
            f"High findings open: {snapshot.review_summary.open_by_severity.get('high', 0)}",
            f"Created: {metadata.created_at}",
            f"Updated: {metadata.updated_at}",
        ]
        if snapshot.suggested_actions:
            lines.extend(["", "Recommended Steps:"])
            lines.extend(f"- {step}" for step in snapshot.suggested_actions)
        if snapshot.blocked_reasons:
            lines.extend(["", "Next-Step Blockers:"])
            lines.extend(f"- {reason}" for reason in snapshot.blocked_reasons)
        return "\n".join(lines)

    def completion_evidence(self, task_id: str) -> dict[str, object] | None:
        metadata, task_dir = self.get_task(task_id)
        completion_path = task_dir / "completion.json"
        if not completion_path.exists():
            return None

        payload = json.loads(completion_path.read_text(encoding="utf-8"))
        archive_path = str(payload.get("archive_path", ""))
        archive_exists = bool(archive_path) and (self.root / archive_path).exists()
        payload["checks"] = {
            "archive_exists": archive_exists,
            "metadata_archived": "openspec/changes/archive/" in metadata.change_path,
        }
        payload["path"] = self._relative_to_root(completion_path)
        return payload

    def set_task_baseline(self, task_id: str, commit_sha: str | None = None) -> TaskMetadata:
        metadata, task_dir = self.get_task(task_id)
        target = (commit_sha or "").strip() or self._current_head_commit()
        if not target:
            raise RuntimeError("Unable to resolve git HEAD for baseline.")
        metadata.base_commit = target
        metadata.updated_at = utc_timestamp()
        self._write_metadata(task_dir, metadata)
        self.append_log(task_id, metadata.current_stage, f"Set baseline commit to {target}")
        return self.get_task(task_id)[0]

    def task_compare(self, task_id: str) -> dict[str, object]:
        metadata, _task_dir = self.get_task(task_id)
        base_commit = metadata.base_commit
        head_commit = self._current_head_commit()
        if not base_commit:
            return {
                "available": False,
                "reason": "Task baseline is missing. Set baseline first to compare only this task's code delta.",
                "base_commit": None,
                "head_commit": head_commit,
                "commit_range": None,
                "baseline_source": "none",
                "committed_files": [],
                "related_committed_files": [],
                "hidden_committed_count": 0,
                "working_tree": [],
                "related_working_tree": [],
                "hidden_working_count": 0,
                "totals": {"files": 0, "added": 0, "deleted": 0},
            }
        if not head_commit:
            return {
                "available": False,
                "reason": "Unable to read current git HEAD.",
                "base_commit": base_commit,
                "head_commit": None,
                "commit_range": None,
                "baseline_source": "task",
                "committed_files": [],
                "related_committed_files": [],
                "hidden_committed_count": 0,
                "working_tree": [],
                "related_working_tree": [],
                "hidden_working_count": 0,
                "totals": {"files": 0, "added": 0, "deleted": 0},
            }

        commit_range = f"{base_commit}..{head_commit}"
        diff_result = self.command_runner(["git", "diff", "--numstat", commit_range, "--"], self.root)
        committed_files = self._parse_numstat(diff_result.stdout) if diff_result.returncode == 0 else []
        related_committed = [
            item
            for item in committed_files
            if self._is_task_related_path(str(item["path"]), task_id=metadata.task_id, change_name=metadata.change_name)
        ]
        status_result = self.command_runner(["git", "status", "--porcelain"], self.root)
        working_tree = self._parse_porcelain(status_result.stdout) if status_result.returncode == 0 else []
        related_working = [
            item
            for item in working_tree
            if self._is_task_related_path(item["path"], task_id=metadata.task_id, change_name=metadata.change_name)
        ]

        return {
            "available": diff_result.returncode == 0 and status_result.returncode == 0,
            "reason": None
            if diff_result.returncode == 0 and status_result.returncode == 0
            else "Unable to compute git compare summary.",
            "base_commit": base_commit,
            "head_commit": head_commit,
            "commit_range": commit_range,
            "baseline_source": "task",
            "committed_files": committed_files,
            "related_committed_files": related_committed,
            "hidden_committed_count": max(0, len(committed_files) - len(related_committed)),
            "working_tree": working_tree,
            "related_working_tree": related_working,
            "hidden_working_count": max(0, len(working_tree) - len(related_working)),
            "totals": {
                "files": len(committed_files),
                "added": sum(item["added"] for item in committed_files),
                "deleted": sum(item["deleted"] for item in committed_files),
            },
        }

    def _gate_spec(self, metadata: TaskMetadata) -> list[str]:
        reasons: list[str] = []
        if not self._change_dir(metadata.change_name).exists():
            reasons.append(f"Bound OpenSpec change '{metadata.change_name}' does not exist.")
        return reasons

    def _gate_implement(self, metadata: TaskMetadata, task_dir: Path) -> list[str]:
        # Implement is only allowed once the OpenSpec side is real enough to execute against.
        reasons: list[str] = []
        change_dir = self._change_dir(metadata.change_name)
        for artifact in ("proposal.md", "design.md", "tasks.md"):
            if not (change_dir / artifact).exists():
                reasons.append(f"Missing OpenSpec artifact: {artifact}.")

        spec_files = list((change_dir / "specs").glob("**/*.md")) if (change_dir / "specs").exists() else []
        if not spec_files:
            reasons.append("Missing OpenSpec artifact: specs/**/*.md.")

        progress = self._tasks_progress(metadata.change_name)
        if progress.total == 0:
            reasons.append("OpenSpec tasks.md does not contain any checklist items.")

        if not self._section_has_meaningful_content(task_dir / "spec.md", "## Summary"):
            reasons.append("spec.md summary has not been updated.")
        return reasons

    def _gate_review(self, metadata: TaskMetadata, task_dir: Path) -> list[str]:
        # Review means different things depending on where we came from:
        # from implement we require implementation + verification, from fix we require fix notes + re-verification.
        reasons: list[str] = []
        if metadata.current_stage == "implement":
            if not self._implementation_has_notes(task_dir / "implementation.md"):
                reasons.append("implementation.md does not contain implementation notes.")
            if metadata.last_verified_at is None:
                reasons.append("Verification has not been run.")
        elif metadata.current_stage == "fix":
            if not self._fixes_have_notes(task_dir / "fixes.md"):
                reasons.append("fixes.md does not contain fix notes.")
            if metadata.last_verified_at is None:
                reasons.append("Verification has not been re-run after fixes.")
            elif metadata.last_reviewed_at and metadata.last_verified_at <= metadata.last_reviewed_at:
                reasons.append("Verification has not been re-run after the last review.")
        return reasons

    def _gate_fix(self, task_dir: Path) -> list[str]:
        findings = self._parse_review_findings(task_dir / "review.md")
        if not any(finding.status == "open" for finding in findings):
            return ["No open review findings are available for fix."]
        return []

    def _release_gate_reasons(self, task_id: str) -> list[str]:
        metadata, task_dir = self.get_task(task_id)
        return self._release_gate_reasons_for(metadata, task_dir)

    def _release_gate_reasons_for(self, metadata: TaskMetadata, task_dir: Path) -> list[str]:
        # Release is the quality gate: tasks done, latest verification green, and no open high findings.
        self._sync_managed_tasks_for(metadata, task_dir)
        reasons: list[str] = []
        progress = self._tasks_progress(metadata.change_name)
        if progress.total == 0:
            reasons.append("OpenSpec tasks.md does not contain any checklist items.")
        elif progress.incomplete:
            reasons.append(f"OpenSpec tasks are incomplete: {progress.incomplete} remaining.")

        if metadata.last_verification_passed is not True:
            reasons.append("Latest verification did not pass.")

        if metadata.last_reviewed_at is None:
            reasons.append("Self-review has not been recorded.")

        findings = self._parse_review_findings(task_dir / "review.md")
        open_high = sum(1 for finding in findings if finding.status == "open" and finding.severity == "high")
        if open_high:
            reasons.append(f"{open_high} high severity review finding(s) remain open.")

        if not findings and not self._section_has_meaningful_content(task_dir / "review.md", "## Summary"):
            reasons.append("review.md has not been updated with review notes.")
        return reasons

    def _complete_gate_reasons(self, task_id: str) -> list[str]:
        # Complete re-checks release gates and adds archive-specific requirements before any git side effects happen.
        metadata, task_dir = self.get_task(task_id)
        reasons = list(self._release_gate_reasons(task_id))
        if not self._section_has_meaningful_content(task_dir / "release.md", "## Notes"):
            reasons.append("release.md notes have not been updated.")
        if not self._change_dir(metadata.change_name).exists():
            reasons.append("Bound OpenSpec change is missing and cannot be archived.")
        return reasons

    def _tasks_progress(self, change_name: str) -> TaskProgress:
        # OpenSpec task completion is inferred from markdown checkboxes so the local task can show live progress.
        tasks_file = self._change_dir(change_name) / "tasks.md"
        if not tasks_file.exists():
            return TaskProgress(total=0, complete=0, incomplete=0)

        total = 0
        complete = 0
        for line in tasks_file.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^- \[( |x|X)\] ", line.strip())
            if not match:
                continue
            total += 1
            if match.group(1).lower() == "x":
                complete += 1
        return TaskProgress(total=total, complete=complete, incomplete=max(total - complete, 0))

    def _review_summary(self, task_id: str) -> ReviewSummary:
        _, task_dir = self.get_task(task_id)
        findings = self._parse_review_findings(task_dir / "review.md")
        open_by_severity = {"high": 0, "medium": 0, "low": 0}
        for finding in findings:
            if finding.status == "open":
                open_by_severity[finding.severity] = open_by_severity.get(finding.severity, 0) + 1
        return ReviewSummary(findings=findings, open_by_severity=open_by_severity)

    def _generate_artifacts(self, title: str, request: str, change_name: str) -> GeneratedArtifacts:
        if self.artifact_generator is None:
            raise RuntimeError("Artifact generator is not configured.")
        artifacts = self.artifact_generator.generate(title=title, request=request, change_name=change_name)
        if not artifacts.proposal.strip() or not artifacts.design.strip() or not artifacts.tasks.strip():
            raise ValueError("Generated artifacts were incomplete.")
        if not artifacts.specs:
            raise ValueError("Generated artifacts did not include any spec files.")
        return artifacts

    def _next_action(self, stage: str, review_summary: ReviewSummary) -> str:
        if stage == "intake":
            return "advance spec"
        if stage == "spec":
            return "advance implement"
        if stage == "implement":
            return "advance review"
        if stage == "review":
            has_open = any(finding.status == "open" for finding in review_summary.findings)
            return "advance fix" if has_open else "advance release"
        if stage == "fix":
            return "advance review"
        return "complete"

    def _next_action_reasons(self, task_id: str, stage: str, review_summary: ReviewSummary) -> list[str]:
        if stage == "release":
            return self._complete_gate_reasons(task_id)
        if stage == "review":
            has_open = any(finding.status == "open" for finding in review_summary.findings)
            target = "fix" if has_open else "release"
            return self.validate_stage_transition(task_id, target)
        if stage == "intake":
            return self.validate_stage_transition(task_id, "spec")
        if stage == "spec":
            return self.validate_stage_transition(task_id, "implement")
        if stage == "implement":
            return self.validate_stage_transition(task_id, "review")
        if stage == "fix":
            return self.validate_stage_transition(task_id, "review")
        return []

    def _suggested_actions(
        self,
        task_id: str,
        metadata: TaskMetadata,
        planned_action: str,
        blocked_reasons: list[str],
    ) -> list[str]:
        if not blocked_reasons:
            return [self._action_command(task_id, planned_action)]

        suggestions: list[str] = []
        for reason in blocked_reasons:
            if "implementation.md does not contain implementation notes" in reason:
                suggestions.append(
                    f"Run `python -m scheduler_automation.cli autopilot --task {task_id}` to generate implementation records and continue automatically."
                )
            elif "Verification has not been run" in reason and "fixes" not in reason:
                suggestions.append(
                    f"Run `python -m scheduler_automation.cli autopilot --task {task_id}` to continue verification and review automatically."
                )
            elif "fixes.md does not contain fix notes" in reason:
                suggestions.append(
                    f"Apply the required code changes, then run `python -m scheduler_automation.cli autopilot --task {task_id}`."
                )
            elif "Verification has not been re-run after fixes" in reason or "after the last review" in reason:
                suggestions.append(
                    f"After changing the code, run `python -m scheduler_automation.cli autopilot --task {task_id}`."
                )
            elif "Self-review has not been recorded" in reason or "review.md has not been updated with review notes" in reason:
                suggestions.append(
                    f"Run `python -m scheduler_automation.cli autopilot --task {task_id}` to write review notes and continue automatically."
                )
            elif "OpenSpec tasks are incomplete" in reason or "tasks.md does not contain any checklist items" in reason:
                suggestions.append(
                    "Complete the remaining workflow steps; the OpenSpec tasks checklist is synchronized automatically."
                )
            elif "release.md notes have not been updated" in reason:
                suggestions.append(
                    f"Run `python -m scheduler_automation.cli autopilot --task {task_id}` to prepare release notes automatically."
                )
            elif "proposal.md" in reason or "design.md" in reason or "specs/**/*.md" in reason:
                suggestions.append(
                    f"Review and complete the missing OpenSpec artifacts under openspec/changes/{metadata.change_name}/."
                )
            else:
                suggestions.append(reason)

        # Preserve order while removing duplicates.
        deduped: list[str] = []
        for suggestion in suggestions:
            if suggestion not in deduped:
                deduped.append(suggestion)
        return deduped

    def _action_command(self, task_id: str, action: str) -> str:
        if action.startswith("advance ") or action == "complete":
            if action == "complete":
                return f"Run `python -m scheduler_automation.cli complete --task {task_id}`."
            return f"Run `python -m scheduler_automation.cli autopilot --task {task_id}`."
        return action

    def _archive_change(self, change_name: str) -> str:
        # Archival moves the active change out of the working set before git commit/push happens.
        source = self._change_dir(change_name)
        archive_root = self.changes_dir / "archive"
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_name = f"{datetime.now().strftime('%Y-%m-%d')}-{change_name}"
        target = archive_root / archive_name
        if target.exists():
            raise FileExistsError(f"Archive target already exists: {self._relative_to_root(target)}")
        shutil.move(str(source), str(target))
        return self._relative_to_root(target)

    def _implementation_has_notes(self, path: Path) -> bool:
        return self._section_has_meaningful_content(path, "## Plan") or self._section_has_meaningful_content(
            path, "## Code changes"
        )

    def _fixes_have_notes(self, path: Path) -> bool:
        return self._section_has_meaningful_content(path, "## Bugs addressed") or self._section_has_meaningful_content(
            path, "## Retest notes"
        )

    def _section_has_meaningful_content(self, path: Path, heading: str) -> bool:
        if not path.exists():
            return False
        section = self._extract_section(path.read_text(encoding="utf-8"), heading)
        if not section:
            return False
        for line in section.splitlines():
            stripped = line.strip(" -\t")
            if not stripped or stripped.startswith("#"):
                continue
            if any(stripped.lower().startswith(prefix) for prefix in PLACEHOLDER_PREFIXES):
                continue
            return True
        return False

    def _extract_section(self, text: str, heading: str) -> str:
        lines = text.splitlines()
        collected: list[str] = []
        capture = False
        for line in lines:
            if line.strip() == heading:
                capture = True
                continue
            if capture and line.startswith("## "):
                break
            if capture:
                collected.append(line)
        return "\n".join(collected).strip()

    def _append_verification(self, path: Path, verification: VerificationResult) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                "\n## Verification Run\n\n"
                f"- Timestamp: {verification.timestamp}\n"
                f"- Command: {verification.command}\n"
                f"- Status: {'PASS' if verification.passed else 'FAIL'}\n\n"
            )
            if verification.stdout:
                handle.write("```text\n")
                handle.write(verification.stdout.rstrip() + "\n")
                handle.write("```\n")
            if verification.stderr:
                handle.write("\n```text\n")
                handle.write(verification.stderr.rstrip() + "\n")
                handle.write("```\n")

    def _append_release_record(
        self,
        path: Path,
        archive_path: str,
        commit_message: str,
        commit_sha: str | None,
        evidence_path: str,
    ) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                "\n## Completion\n\n"
                f"- Archived change: {archive_path}\n"
                f"- Commit message: {commit_message}\n"
                f"- Commit SHA: {commit_sha or 'unavailable'}\n"
                f"- Completion evidence: {evidence_path}\n"
            )

    def _write_completion_evidence(
        self,
        task_dir: Path,
        metadata: TaskMetadata,
        archive_path: str,
        commit_message: str,
        commit_sha: str | None,
        command_results: dict[str, dict[str, object]],
    ) -> Path:
        completion_path = task_dir / "completion.json"
        payload = {
            "task_id": metadata.task_id,
            "title": metadata.title,
            "change_name": metadata.change_name,
            "archive_path": archive_path,
            "commit_message": commit_message,
            "commit_sha": commit_sha,
            "completed_at": utc_timestamp(),
            "base_commit": metadata.base_commit,
            "commands": command_results,
        }
        completion_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        return completion_path

    def _parse_numstat(self, text: str) -> list[dict[str, int | str]]:
        results: list[dict[str, int | str]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            results.append(
                {
                    "path": parts[2],
                    "added": self._safe_numstat(parts[0]),
                    "deleted": self._safe_numstat(parts[1]),
                }
            )
        return results

    def _parse_porcelain(self, text: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for raw_line in text.splitlines():
            if len(raw_line) < 4:
                continue
            entries.append({"status": raw_line[:2], "path": raw_line[3:].strip()})
        return entries

    def _safe_numstat(self, value: str) -> int:
        value = value.strip()
        return int(value) if value.isdigit() else 0

    def _is_task_related_path(self, path: str, task_id: str, change_name: str) -> bool:
        normalized = path.replace("\\", "/").lower()
        task_token = task_id.lower()
        change_token = change_name.lower()
        return (
            task_token in normalized
            or change_token in normalized
            or normalized.startswith("src/scheduler_automation/")
            or normalized.startswith("tests/test_workflow.py")
            or normalized.startswith("docs/superpowers/")
        )

    def _parse_review_findings(self, path: Path) -> list[ReviewFinding]:
        # review.md stays human-editable, so findings are parsed from a simple markdown format instead of JSON.
        if not path.exists():
            return []

        findings: list[ReviewFinding] = []
        current: dict[str, str] | None = None
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("### Finding "):
                if current and {"finding_id", "severity", "status", "summary"} <= current.keys():
                    findings.append(
                        ReviewFinding(
                            finding_id=current["finding_id"],
                            severity=current["severity"],
                            status=current["status"],
                            summary=current["summary"],
                        )
                    )
                current = {"finding_id": line.removeprefix("### Finding ").strip()}
                continue
            if current is None:
                continue
            if line.startswith("- Severity:"):
                current["severity"] = line.split(":", 1)[1].strip().lower()
            elif line.startswith("- Status:"):
                current["status"] = line.split(":", 1)[1].strip().lower()
            elif line.startswith("- Summary:"):
                current["summary"] = line.split(":", 1)[1].strip()

        if current and {"finding_id", "severity", "status", "summary"} <= current.keys():
            findings.append(
                ReviewFinding(
                    finding_id=current["finding_id"],
                    severity=current["severity"],
                    status=current["status"],
                    summary=current["summary"],
                )
            )
        return findings

    def _unique_change_name(self, base: str) -> str:
        candidate = base
        if not self._change_dir(candidate).exists():
            return candidate
        suffix = datetime.now().strftime("%H%M%S")
        return f"{candidate}-{suffix}"

    def _change_dir(self, change_name: str) -> Path:
        return self.changes_dir / change_name

    def _relative_to_root(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _read_metadata(self, metadata_file: Path) -> TaskMetadata:
        data = json.loads(metadata_file.read_text(encoding="utf-8"))
        return TaskMetadata(**data)

    def _write_metadata(self, task_dir: Path, metadata: TaskMetadata) -> None:
        metadata_file = task_dir / "metadata.json"
        metadata_file.write_text(
            json.dumps(asdict(metadata), indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def _write_generated_artifacts(self, change_dir: Path, artifacts: GeneratedArtifacts) -> None:
        (change_dir / "proposal.md").write_text(artifacts.proposal, encoding="utf-8")
        (change_dir / "design.md").write_text(artifacts.design, encoding="utf-8")
        (change_dir / "tasks.md").write_text(artifacts.tasks, encoding="utf-8")
        for relative_path, content in artifacts.specs.items():
            target = change_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def _sync_managed_tasks_for(self, metadata: TaskMetadata, task_dir: Path) -> None:
        tasks_path = self._change_dir(metadata.change_name) / "tasks.md"
        if not tasks_path.exists():
            return

        desired_state = self._managed_task_state(metadata, task_dir)
        original = tasks_path.read_text(encoding="utf-8")
        trailing_newline = original.endswith("\n")
        updated_lines: list[str] = []
        changed = False

        for line in original.splitlines():
            match = re.match(r"^(\s*-\s)\[(?: |x|X)\](\s+((?:\d+\.)+\d+)\b.*)$", line)
            if not match:
                updated_lines.append(line)
                continue

            item_id = match.group(3)
            if item_id not in desired_state:
                updated_lines.append(line)
                continue

            marker = "x" if desired_state[item_id] else " "
            new_line = f"{match.group(1)}[{marker}]{match.group(2)}"
            updated_lines.append(new_line)
            changed = changed or new_line != line

        if not changed:
            return

        updated = "\n".join(updated_lines)
        if trailing_newline:
            updated += "\n"
        tasks_path.write_text(updated, encoding="utf-8")

    def _managed_task_state(self, metadata: TaskMetadata, task_dir: Path) -> dict[str, bool]:
        change_dir = self._change_dir(metadata.change_name)
        review_path = task_dir / "review.md"
        findings = self._parse_review_findings(review_path)
        open_high = sum(1 for finding in findings if finding.status == "open" and finding.severity == "high")

        definition_ready = (
            (change_dir / "proposal.md").exists()
            and (change_dir / "design.md").exists()
            and (change_dir / "tasks.md").exists()
            and any((change_dir / "specs").glob("**/*.md"))
        )
        implementation_started = metadata.current_stage in {"implement", "review", "fix", "release"} and (
            self._implementation_has_notes(task_dir / "implementation.md")
        )
        review_recorded = metadata.last_reviewed_at is not None and (
            bool(findings) or self._section_has_meaningful_content(review_path, "## Summary")
        )
        review_ready = metadata.last_verification_passed is True and review_recorded and open_high == 0

        return {
            "1.1": definition_ready,
            "1.2": definition_ready,
            "2.1": implementation_started,
            "2.2": review_ready,
        }

    def _populate_local_spec_summary(self, spec_path: Path, summary: str) -> None:
        text = spec_path.read_text(encoding="utf-8")
        replacement = (
            "## Summary\n\n"
            f"{summary.strip()}\n\n"
            "## Acceptance Alignment\n\n"
            "- Review the generated OpenSpec artifacts before implementation.\n"
        )
        text = re.sub(
            r"## Summary\s+.*?## Acceptance Alignment\s+.*",
            replacement,
            text,
            flags=re.DOTALL,
        )
        spec_path.write_text(text, encoding="utf-8")

    def _populate_implementation_seed(self, implementation_path: Path, summary: str, request: str) -> None:
        implementation_path.write_text(
            "# Superpower Implementation\n\n"
            "## Plan\n\n"
            f"Use the generated OpenSpec artifacts for `{summary}` as the implementation baseline.\n"
            f"Requested work: {request.strip()}\n\n"
            "## Code changes\n\n"
            "- No implementation changes recorded yet.\n\n"
            "## Verification\n\n"
            "- Pending\n",
            encoding="utf-8",
        )

    def _request_template(self, title: str, request: str) -> str:
        body = request.strip() or "- Replace this line with the exact request from the user.\n"
        return f"# Request\n\n## Title\n\n{title.strip()}\n\n## Raw input\n\n{body}\n"

    def _spec_template(self, change_name: str, change_path: str) -> str:
        return (
            "# Spec\n\n"
            "## OpenSpec Change\n\n"
            f"- Name: {change_name}\n"
            f"- Path: {change_path}\n\n"
            "## Summary\n\n"
            "- Replace this line with the local summary of the bound OpenSpec change.\n\n"
            "## Acceptance Alignment\n\n"
            "- Replace this line with the completion criteria for this task.\n"
        )

    def _implementation_template(self) -> str:
        return (
            "# Superpower Implementation\n\n"
            "## Plan\n\n"
            "- Replace this line with implementation notes.\n\n"
            "## Code changes\n\n"
            "- Replace this line with the files and decisions made.\n\n"
            "## Verification\n\n"
            "- Replace this line with the latest verification summary.\n"
        )

    def _review_template(self) -> str:
        return (
            "# Review\n\n"
            "## Summary\n\n"
            "- Replace this line with the review summary.\n\n"
            "## Findings\n\n"
            "- Add findings using the format below when needed.\n"
            "- `### Finding F001`\n"
            "- `- Severity: high|medium|low`\n"
            "- `- Status: open|resolved`\n"
            "- `- Summary: short description`\n"
        )

    def _fixes_template(self) -> str:
        return (
            "# Fixes\n\n"
            "## Bugs addressed\n\n"
            "- Replace this line with the findings fixed in this round.\n\n"
            "## Retest notes\n\n"
            "- Replace this line with what was re-verified.\n"
        )

    def _release_template(self) -> str:
        return (
            "# Release\n\n"
            "## Notes\n\n"
            "- Replace this line with the archive and sync notes.\n"
        )

    def _journal_template(self) -> str:
        return "# Journal\n\n"

    def _verification_label(self, metadata: TaskMetadata) -> str:
        if metadata.last_verification_passed is True:
            return f"PASS at {metadata.last_verified_at}"
        if metadata.last_verification_passed is False:
            return f"FAIL at {metadata.last_verified_at}"
        return "Not run"

    def _task_files(self, task_dir: Path) -> Iterable[Path]:
        return sorted(path for path in task_dir.iterdir() if path.is_file())

    def _current_head_commit(self) -> str | None:
        result = self.command_runner(["git", "rev-parse", "HEAD"], self.root)
        if result.returncode != 0:
            return None
        sha = result.stdout.strip()
        return sha or None

    def _run_command(self, command: list[str], cwd: Path | None = None) -> CommandResult:
        env = os.environ.copy()
        if command[:4] == ["python", "-m", "unittest", "discover"]:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = "src" if not existing else f"src{os.pathsep}{existing}"
        command = self._resolve_command(command)
        completed = subprocess.run(
            command,
            cwd=str(cwd or self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=env,
        )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _resolve_command(self, command: list[str]) -> list[str]:
        if not command:
            return command
        if os.name == "nt" and command[0] == "openspec":
            shim = shutil.which("openspec.cmd") or shutil.which("openspec")
            if shim:
                return [shim, *command[1:]]
        return command

    def _autopilot_result(
        self,
        task_id: str,
        final_stage: str,
        reasons: list[str],
        actions: list[str],
        ready_for_completion: bool,
    ) -> AutopilotResult:
        return AutopilotResult(
            task_id=task_id,
            final_stage=final_stage,
            stop_reason="; ".join(reasons),
            actions=actions,
            ready_for_completion=ready_for_completion,
        )

    def _ensure_local_spec_summary(self, task_dir: Path, metadata: TaskMetadata) -> None:
        spec_path = task_dir / "spec.md"
        if self._section_has_meaningful_content(spec_path, "## Summary"):
            return
        summary = self._task_request(task_dir) or metadata.title
        self._populate_local_spec_summary(spec_path, summary)

    def _task_request(self, task_dir: Path) -> str:
        request_path = task_dir / "request.md"
        if not request_path.exists():
            return ""
        text = request_path.read_text(encoding="utf-8")
        raw_input = self._extract_section(text, "## Raw input")
        return raw_input.strip().splitlines()[0].strip() if raw_input.strip() else ""

    def _write_autopilot_implementation(self, task_dir: Path, metadata: TaskMetadata) -> None:
        request = self._task_request(task_dir) or metadata.title
        verification = self._verification_label(metadata)
        text = (
            "# Superpower Implementation\n\n"
            "<!-- workflow-autopilot -->\n\n"
            "## Plan\n\n"
            f"Advance task `{metadata.task_id}` for OpenSpec change `{metadata.change_name}` through the local workflow.\n"
            f"Requested work: {request}\n\n"
            "## Code changes\n\n"
            f"- OpenSpec change: {metadata.change_name}\n"
            f"- Current stage: {metadata.current_stage}\n"
            "- Workflow evidence is being recorded automatically by autopilot.\n\n"
            "## Verification\n\n"
            f"- Latest status: {verification}\n"
        )
        (task_dir / "implementation.md").write_text(text, encoding="utf-8")

    def _write_autopilot_review(self, task_id: str) -> ReviewSummary:
        metadata, task_dir = self.get_task(task_id)
        if metadata.last_verification_passed is True:
            review_text = (
                "# Review\n\n"
                "<!-- workflow-autopilot -->\n\n"
                "## Summary\n\n"
                "Automated self-review completed after the latest passing verification run and found no blocking issues.\n\n"
                "## Findings\n\n"
                "None.\n"
            )
        else:
            failure_detail = "Latest verification failed and code changes are required before release."
            review_text = (
                "# Review\n\n"
                "<!-- workflow-autopilot -->\n\n"
                "## Summary\n\n"
                "Automated self-review found a blocking issue after the latest verification run.\n\n"
                "## Findings\n\n"
                "### Finding F001\n"
                "- Severity: high\n"
                "- Status: open\n"
                f"- Summary: {failure_detail}\n"
            )
        (task_dir / "review.md").write_text(review_text, encoding="utf-8")
        return self.review_task(task_id)

    def _write_autopilot_fixes(self, task_dir: Path, metadata: TaskMetadata, review_summary: ReviewSummary) -> None:
        open_high = review_summary.open_by_severity.get("high", 0)
        text = (
            "# Fixes\n\n"
            "<!-- workflow-autopilot -->\n\n"
            "## Bugs addressed\n\n"
            f"- {open_high} blocking review finding(s) remain open for `{metadata.change_name}`.\n"
            "- Apply code changes for the failing implementation before rerunning autopilot.\n\n"
            "## Retest notes\n\n"
            f"- After fixing the code, run `python -m scheduler_automation.cli autopilot --task {metadata.task_id}`.\n"
        )
        (task_dir / "fixes.md").write_text(text, encoding="utf-8")

    def _write_autopilot_release(self, task_dir: Path, metadata: TaskMetadata) -> None:
        text = (
            "# Release\n\n"
            "<!-- workflow-autopilot -->\n\n"
            "## Notes\n\n"
            f"Ready to archive OpenSpec change `{metadata.change_name}` for task `{metadata.task_id}`.\n"
            f"Latest verification: {self._verification_label(metadata)}.\n"
            "No open high-severity review findings remain.\n"
            f"Next step: run `python -m scheduler_automation.cli complete --task {metadata.task_id}` when you want to archive, commit, and push.\n"
        )
        (task_dir / "release.md").write_text(text, encoding="utf-8")
