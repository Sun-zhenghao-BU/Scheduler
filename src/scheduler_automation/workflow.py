from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
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
    project_id: str = ""
    requirement_status: str = "drafting"
    requirement_confirmed_at: str = ""


@dataclass
class RequirementMessage:
    role: str
    content: str
    created_at: str


@dataclass
class RequirementSession:
    status: str
    summary: str
    messages: list[RequirementMessage]


@dataclass
class WorkflowIssue:
    title: str
    severity: str = "medium"
    blocking: bool = True
    source: str = "tester"


@dataclass
class WorkflowState:
    status: str = "idle"
    current_round: int = 0
    max_rounds: int = 0
    current_stage: str = "intake"
    release_ready: bool = False
    requires_human_review: bool = False
    last_error: str = ""
    last_test_exit_code: int = 0
    last_test_command: str = ""
    last_test_output: str = ""
    tester_summary: str = ""
    recommended_action: str = ""
    updated_at: str = ""
    issues: list[WorkflowIssue] = field(default_factory=list)


class WorkflowManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.tasks_dir = self.root / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def create_task(self, title: str, request: str = "", project_id: str = "") -> TaskMetadata:
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
            project_id=project_id,
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
        self._write_requirement_session(task_dir, self._initial_requirement_session(request))
        self.save_workflow_state(task_id, WorkflowState(updated_at=now))
        return metadata

    def list_tasks(self, project_id: str | None = None) -> list[TaskMetadata]:
        results: list[TaskMetadata] = []
        for task_dir in sorted(self.tasks_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            metadata_file = task_dir / "metadata.json"
            if not metadata_file.exists():
                continue
            metadata = self._read_metadata(metadata_file)
            if project_id is None or metadata.project_id == project_id:
                results.append(metadata)
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
        if stage == "implement" and metadata.requirement_status != "confirmed":
            raise ValueError("Requirements must be confirmed before implementation.")
        metadata.current_stage = stage
        metadata.updated_at = utc_timestamp()
        self._write_metadata(task_dir, metadata)
        self.append_log(task_id, stage, f"阶段已推进到 {stage}")
        state = self.load_workflow_state(task_id)
        state.current_stage = stage
        state.updated_at = metadata.updated_at
        self.save_workflow_state(task_id, state)
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

    def load_requirement_session(self, task_id: str) -> RequirementSession:
        _, task_dir = self.get_task(task_id)
        session_path = task_dir / "requirements.json"
        if not session_path.exists():
            session = RequirementSession(status="drafting", summary="", messages=[])
            self._write_requirement_session(task_dir, session)
            return session
        data = json.loads(session_path.read_text(encoding="utf-8"))
        return RequirementSession(
            status=data.get("status", "drafting"),
            summary=data.get("summary", ""),
            messages=[
                RequirementMessage(
                    role=item.get("role", "user"),
                    content=item.get("content", ""),
                    created_at=item.get("created_at", ""),
                )
                for item in data.get("messages", [])
            ],
        )

    def append_requirement_message(self, task_id: str, role: str, content: str) -> RequirementSession:
        if role not in {"user", "product_manager"}:
            raise ValueError("Requirement message role must be 'user' or 'product_manager'.")
        metadata, task_dir = self.get_task(task_id)
        session = self.load_requirement_session(task_id)
        session.messages.append(RequirementMessage(role=role, content=content.strip(), created_at=utc_timestamp()))
        session.status = metadata.requirement_status
        self._write_requirement_session(task_dir, session)
        metadata.updated_at = utc_timestamp()
        self._write_metadata(task_dir, metadata)
        return session

    def confirm_requirements(self, task_id: str, summary: str) -> TaskMetadata:
        if not summary.strip():
            raise ValueError("Requirement summary is required.")
        metadata, task_dir = self.get_task(task_id)
        confirmed_at = utc_timestamp()
        metadata.requirement_status = "confirmed"
        metadata.requirement_confirmed_at = confirmed_at
        metadata.updated_at = confirmed_at
        self._write_metadata(task_dir, metadata)

        session = self.load_requirement_session(task_id)
        session.status = "confirmed"
        session.summary = summary.strip()
        self._write_requirement_session(task_dir, session)
        (task_dir / "spec.md").write_text(self._confirmed_spec_template(metadata.title, summary.strip()), encoding="utf-8")
        self.append_log(task_id, metadata.current_stage, "需求已确认")
        return metadata

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

    def load_workflow_state(self, task_id: str) -> WorkflowState:
        _, task_dir = self.get_task(task_id)
        state_path = task_dir / "workflow_state.json"
        if not state_path.exists():
            return WorkflowState(updated_at=utc_timestamp())
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return WorkflowState(
            status=data.get("status", "idle"),
            current_round=data.get("current_round", 0),
            max_rounds=data.get("max_rounds", 0),
            current_stage=data.get("current_stage", "intake"),
            release_ready=data.get("release_ready", False),
            requires_human_review=data.get("requires_human_review", False),
            last_error=data.get("last_error", ""),
            last_test_exit_code=data.get("last_test_exit_code", 0),
            last_test_command=data.get("last_test_command", ""),
            last_test_output=data.get("last_test_output", ""),
            tester_summary=data.get("tester_summary", ""),
            recommended_action=data.get("recommended_action", ""),
            updated_at=data.get("updated_at", ""),
            issues=[WorkflowIssue(**item) for item in data.get("issues", [])],
        )

    def save_workflow_state(self, task_id: str, state: WorkflowState) -> None:
        _, task_dir = self.get_task(task_id)
        if not state.updated_at:
            state.updated_at = utc_timestamp()
        (task_dir / "workflow_state.json").write_text(
            json.dumps(
                {
                    **asdict(state),
                    "issues": [asdict(issue) for issue in state.issues],
                },
                indent=2,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_execution_result(
        self,
        task_id: str,
        summary: str,
        selected_paths: list[str],
        written: list[str],
        test_command: str,
        test_exit_code: int,
        test_output: str,
    ) -> None:
        _, task_dir = self.get_task(task_id)
        implementation_path = task_dir / "implementation.md"
        review_path = task_dir / "review.md"
        self._append_section(
            implementation_path,
            "Execution Summary",
            "\n".join(
                [
                    summary.strip(),
                    "",
                    "Selected files:",
                    *[f"- {path}" for path in selected_paths],
                    "",
                    "Applied files:",
                    *([f"- {path}" for path in written] if written else ["- No files written"]),
                ]
            ).strip(),
        )
        self._append_section(
            review_path,
            "Execution Test Result",
            "\n".join(
                [
                    f"Command: {test_command or '(none)'}",
                    f"Exit code: {test_exit_code}",
                    "",
                    test_output.strip() or "(no output)",
                ]
            ),
        )

    def write_fix_summary(
        self,
        task_id: str,
        round_number: int,
        test_output: str,
        tester_content: str,
    ) -> None:
        _, task_dir = self.get_task(task_id)
        fixes_path = task_dir / "fixes.md"
        body = "\n".join(
            [
                f"Round: {round_number}",
                "",
                "Tester assessment:",
                tester_content.strip() or "(no tester output)",
                "",
                "Failing test output:",
                test_output.strip() or "(no test output)",
            ]
        )
        self._append_section(fixes_path, f"Fix Round {round_number}", body)

    def write_release_summary(
        self,
        task_id: str,
        summary: str,
        test_command: str,
        test_output: str,
    ) -> None:
        _, task_dir = self.get_task(task_id)
        release_path = task_dir / "release.md"
        body = "\n".join(
            [
                summary.strip() or "Workflow marked this task ready for release.",
                "",
                f"Final test command: {test_command or '(none)'}",
                "",
                "Final verification output:",
                test_output.strip() or "(no output)",
            ]
        )
        self._append_section(release_path, "Release Decision", body)

    def _task_files(self, task_dir: Path) -> Iterable[Path]:
        return sorted(path for path in task_dir.iterdir() if path.is_file())

    def _append_section(self, path: Path, heading: str, body: str) -> None:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        section = f"\n## {heading}\n\n{body.strip()}\n"
        path.write_text(existing.rstrip() + section + "\n", encoding="utf-8")

    def _read_metadata(self, metadata_file: Path) -> TaskMetadata:
        data = json.loads(metadata_file.read_text(encoding="utf-8"))
        return TaskMetadata(**data)

    def _write_metadata(self, task_dir: Path, metadata: TaskMetadata) -> None:
        metadata_file = task_dir / "metadata.json"
        metadata_file.write_text(json.dumps(asdict(metadata), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def _initial_requirement_session(self, request: str) -> RequirementSession:
        messages: list[RequirementMessage] = []
        if request.strip():
            messages.append(RequirementMessage(role="user", content=request.strip(), created_at=utc_timestamp()))
        return RequirementSession(status="drafting", summary="", messages=messages)

    def _write_requirement_session(self, task_dir: Path, session: RequirementSession) -> None:
        (task_dir / "requirements.json").write_text(
            json.dumps(
                {
                    "status": session.status,
                    "summary": session.summary,
                    "messages": [asdict(message) for message in session.messages],
                },
                indent=2,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _request_template(self, title: str, request: str) -> str:
        body = request.strip() or "- 请补充原始需求。\n"
        return f"# 需求\n\n## 标题\n\n{title.strip()}\n\n## 原始输入\n\n{body}\n"

    def _spec_template(self, title: str) -> str:
        return (
            "# 产品规划\n\n"
            f"## 问题\n\n{title.strip()}\n\n"
            "## 范围\n\n- 定义本次要完成的内容。\n\n"
            "## 不做什么\n\n- 明确本次不包含的内容。\n\n"
            "## 验收标准\n\n- 补充可验证的验收条件。\n\n"
            "## 架构说明\n\n- 记录关键技术决策。\n\n"
            "## 风险\n\n- 记录技术和交付风险。\n"
        )

    def _confirmed_spec_template(self, title: str, summary: str) -> str:
        return (
            "# 产品规划\n\n"
            f"## 问题\n\n{title.strip()}\n\n"
            "## 已确认需求\n\n"
            f"{summary}\n\n"
            "## 验收标准\n\n"
            "- 后续开发必须基于本确认需求执行。\n\n"
            "## 风险\n\n"
            "- 需求变更需要重新确认后再进入开发。\n"
        )

    def _implementation_template(self) -> str:
        return (
            "# 实施方案\n\n"
            "## 计划\n\n- 拆分具体实施步骤。\n\n"
            "## 代码变更\n\n- 记录要修改的文件和关键决策。\n\n"
            "## 验证\n\n- 记录验证命令和结果。\n"
        )

    def _review_template(self) -> str:
        return (
            "# 测试评审\n\n"
            "## 自测范围\n\n- 验证正确性、回归风险和遗漏点。\n\n"
            "## 评审发现\n\n- 记录问题、风险和待处理项。\n"
        )

    def _fixes_template(self) -> str:
        return (
            "# 修复记录\n\n"
            "## 已修复问题\n\n- 记录修复内容。\n\n"
            "## 复测说明\n\n- 描述重新验证的内容。\n"
        )

    def _release_template(self) -> str:
        return (
            "# 发布记录\n\n"
            "## 发布检查\n\n- 提交变更\n- 推送分支\n- 部署\n\n"
            "## 说明\n\n- 补充发布摘要。\n"
        )

    def _journal_template(self) -> str:
        return "# 日志\n\n"
