from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from scheduler_automation.development import (
    FileChange,
    TestRunResult,
    apply_changes,
    infer_test_command,
)
from scheduler_automation.project_workspace import load_workspace
from scheduler_automation.projects import ProjectManager
from scheduler_automation.workflow import WorkflowManager

ProposalFunc = Callable[[str, list[str], str], Awaitable[tuple[str, list[FileChange]]]]
TestRunner = Callable[[str, str], TestRunResult]


@dataclass
class ExecutionRequest:
    instruction: str = ""
    paths: list[str] | None = None
    test_command: str = ""
    apply_changes: bool = True


@dataclass
class ExecutionResult:
    summary: str
    selected_paths: list[str]
    written: list[str]
    test_command: str
    test_exit_code: int
    test_output: str
    stage: str


async def execute_task(
    manager: WorkflowManager,
    task_id: str,
    request: ExecutionRequest,
    proposal_func: ProposalFunc,
    test_runner: TestRunner,
) -> ExecutionResult:
    metadata, task_dir = manager.get_task(task_id)
    if metadata.requirement_status != "confirmed":
        raise ValueError("Requirements must be confirmed before implementation.")
    if not metadata.project_id:
        raise ValueError("Task is not bound to a project.")

    project = ProjectManager(manager.root).get_project(metadata.project_id)
    if not project.root_path.strip():
        raise ValueError("Project root_path is not configured.")

    workspace = load_workspace(manager.root, metadata.project_id)
    if workspace is None or not workspace.exists():
        raise ValueError("Project workspace is not configured or does not exist.")

    selected_paths = request.paths or _select_workspace_files(workspace.root)
    bootstrapped = False
    if not selected_paths:
        selected_paths = _bootstrap_workspace_targets(
            workspace.root,
            metadata.title,
            manager.load_requirement_session(task_id).summary,
        )
        bootstrapped = True

    instruction = request.instruction.strip() or _build_instruction(metadata.title, manager.load_requirement_session(task_id).summary)
    manager.append_log(task_id, metadata.current_stage, "Execution started")
    if bootstrapped:
        manager.append_log(task_id, metadata.current_stage, f"Bootstrap scaffold selected: {', '.join(selected_paths)}")

    summary, changes = await proposal_func(instruction, selected_paths, metadata.project_id)
    written: list[str] = []
    if request.apply_changes:
        written = apply_changes(workspace, changes)

    test_command = request.test_command.strip() or infer_test_command(workspace)
    test_result = TestRunResult(command="", exit_code=0, output="No test command inferred.")
    if test_command:
        test_result = test_runner(metadata.project_id, test_command)

    if metadata.current_stage != "implement":
        metadata = manager.advance_task(task_id, "implement")
    manager.write_execution_result(
        task_id=task_id,
        summary=summary,
        selected_paths=selected_paths,
        written=written,
        test_command=test_result.command or test_command,
        test_exit_code=test_result.exit_code,
        test_output=test_result.output,
    )
    manager.append_log(task_id, metadata.current_stage, "Execution finished")
    return ExecutionResult(
        summary=summary,
        selected_paths=selected_paths,
        written=written,
        test_command=test_result.command or test_command,
        test_exit_code=test_result.exit_code,
        test_output=test_result.output,
        stage=metadata.current_stage,
    )


def _build_instruction(title: str, summary: str) -> str:
    return (
        f"Implement the approved task '{title}'.\n\n"
        f"Confirmed requirements:\n{summary}\n\n"
        "Make the smallest practical code changes needed to satisfy the requirement."
    )


def _select_workspace_files(root: Path, limit: int = 8) -> list[str]:
    preferred: list[Path] = []
    fallback: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", "dist", "build", "__pycache__"} for part in path.parts):
            continue
        relative = path.relative_to(root)
        if path.name in {"package.json", "pyproject.toml", "README.md"} or "src" in relative.parts:
            preferred.append(relative)
        else:
            fallback.append(relative)
    chosen = preferred[:limit]
    if len(chosen) < limit:
        chosen.extend(fallback[: limit - len(chosen)])
    return [path.as_posix() for path in chosen]


def _bootstrap_workspace_targets(root: Path, title: str, summary: str) -> list[str]:
    stack = _infer_stack(root, title, summary)
    if stack == "node":
        return [
            "package.json",
            "src/index.ts",
            "tests/app.test.ts",
        ]
    return [
        "pyproject.toml",
        "src/app.py",
        "tests/test_app.py",
    ]


def _infer_stack(root: Path, title: str, summary: str) -> str:
    node_markers = {
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "vite.config.js",
        "next.config.js",
        "next.config.ts",
    }
    python_markers = {
        "pyproject.toml",
        "requirements.txt",
        "pytest.ini",
    }
    existing = {path.name for path in root.iterdir()} if root.exists() else set()
    if existing & node_markers:
        return "node"
    if existing & python_markers:
        return "python"

    text = f"{title}\n{summary}".lower()
    node_keywords = {
        "react",
        "vue",
        "node",
        "typescript",
        "javascript",
        "frontend",
        "web",
        "vite",
        "next",
    }
    if any(keyword in text for keyword in node_keywords):
        return "node"
    return "python"
