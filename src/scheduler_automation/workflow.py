from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


STAGES = ("intake", "spec", "implement", "review", "fix", "release")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "task"


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class TaskMetadata:
    task_id: str
    title: str
    current_stage: str
    created_at: str
    updated_at: str


class WorkflowManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.tasks_dir = self.root / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def create_task(self, title: str, request: str = "") -> TaskMetadata:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_id = f"{timestamp}-{slugify(title)}"
        task_dir = self.tasks_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=False)

        now = utc_timestamp()
        metadata = TaskMetadata(
            task_id=task_id,
            title=title.strip(),
            current_stage="intake",
            created_at=now,
            updated_at=now,
        )
        self._write_metadata(task_dir, metadata)

        files = {
            "request.md": self._request_template(title, request),
            "spec.md": self._spec_template(title),
            "implementation.md": self._implementation_template(),
            "review.md": self._review_template(),
            "fixes.md": self._fixes_template(),
            "release.md": self._release_template(),
            "journal.md": self._journal_template(),
        }
        for name, content in files.items():
            (task_dir / name).write_text(content, encoding="utf-8")

        return metadata

    def list_tasks(self) -> list[TaskMetadata]:
        results: list[TaskMetadata] = []
        for task_dir in sorted(self.tasks_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            metadata_file = task_dir / "metadata.json"
            if metadata_file.exists():
                results.append(self._read_metadata(metadata_file))
        return results

    def get_task(self, task_id: str) -> tuple[TaskMetadata, Path]:
        task_dir = self.tasks_dir / task_id
        metadata_file = task_dir / "metadata.json"
        if not metadata_file.exists():
            raise FileNotFoundError(f"Task '{task_id}' does not exist.")
        return self._read_metadata(metadata_file), task_dir

    def advance_task(self, task_id: str, stage: str) -> TaskMetadata:
        if stage not in STAGES:
            raise ValueError(f"Unsupported stage '{stage}'. Expected one of: {', '.join(STAGES)}")
        metadata, task_dir = self.get_task(task_id)
        metadata.current_stage = stage
        metadata.updated_at = utc_timestamp()
        self._write_metadata(task_dir, metadata)
        self.append_log(task_id, stage, f"Stage advanced to {stage}")
        return metadata

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

    def render_task(self, task_id: str) -> str:
        metadata, task_dir = self.get_task(task_id)
        lines = [
            f"Task ID: {metadata.task_id}",
            f"Title: {metadata.title}",
            f"Current stage: {metadata.current_stage}",
            f"Created: {metadata.created_at}",
            f"Updated: {metadata.updated_at}",
            "",
            "Files:",
        ]
        for path in self._task_files(task_dir):
            lines.append(f"- {path.name}")
        return "\n".join(lines)

    def _task_files(self, task_dir: Path) -> Iterable[Path]:
        return sorted(path for path in task_dir.iterdir() if path.is_file())

    def _read_metadata(self, metadata_file: Path) -> TaskMetadata:
        data = json.loads(metadata_file.read_text(encoding="utf-8"))
        return TaskMetadata(**data)

    def _write_metadata(self, task_dir: Path, metadata: TaskMetadata) -> None:
        metadata_file = task_dir / "metadata.json"
        metadata_file.write_text(
            json.dumps(asdict(metadata), indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def _request_template(self, title: str, request: str) -> str:
        body = request.strip() or "- Fill in the exact request from the user.\n"
        return (
            f"# Request\n\n"
            f"## Title\n\n{title.strip()}\n\n"
            f"## Raw input\n\n{body}\n"
        )

    def _spec_template(self, title: str) -> str:
        return (
            f"# OpenSpec\n\n"
            f"## Problem\n\n{title.strip()}\n\n"
            f"## Scope\n\n- Define the in-scope work.\n\n"
            f"## Out of scope\n\n- Define what is explicitly excluded.\n\n"
            f"## Acceptance criteria\n\n- Add measurable criteria.\n\n"
            f"## Architecture notes\n\n- Document major decisions.\n\n"
            f"## Risks\n\n- Capture technical and delivery risks.\n"
        )

    def _implementation_template(self) -> str:
        return (
            "# Superpower Implementation\n\n"
            "## Plan\n\n- Break work into concrete steps.\n\n"
            "## Code changes\n\n- Record files and decisions.\n\n"
            "## Verification\n\n- Record commands and outcomes.\n"
        )

    def _review_template(self) -> str:
        return (
            "# Review\n\n"
            "## Self-review\n\n- Validate correctness, regressions, and gaps.\n\n"
            "## Code review findings\n\n- Record bugs, risks, or cleanup items.\n"
        )

    def _fixes_template(self) -> str:
        return (
            "# Fixes\n\n"
            "## Bugs addressed\n\n- Record bug fixes.\n\n"
            "## Retest notes\n\n- Describe what was rechecked.\n"
        )

    def _release_template(self) -> str:
        return (
            "# Release\n\n"
            "## Push checklist\n\n- Commit changes.\n- Push branch.\n- Deploy.\n\n"
            "## Notes\n\n- Add release summary.\n"
        )

    def _journal_template(self) -> str:
        return "# Journal\n\n"
