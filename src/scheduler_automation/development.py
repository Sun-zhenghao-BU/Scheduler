from __future__ import annotations

import difflib
import shlex
import subprocess
from dataclasses import asdict, dataclass

from scheduler_automation.workspace import Workspace

BLOCKED_COMMAND_TOKENS = {"&&", "||", ";", "|", ">", "<", "`", "$(", "&"}
ALLOWED_TEST_EXECUTABLES = {"npm", "pnpm", "yarn", "pytest", "python", "python3"}


class DevelopmentCommandError(ValueError):
    pass


@dataclass
class FileChange:
    path: str
    old_content: str
    new_content: str
    diff: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "FileChange":
        return cls(
            path=data["path"],
            old_content=data.get("old_content", ""),
            new_content=data.get("new_content", ""),
            diff=data.get("diff", ""),
        )


def build_change(workspace: Workspace, path: str, new_content: str) -> FileChange:
    current = workspace.read_file(path)
    old_content = str(current["content"])
    diff = "".join(
        difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    return FileChange(path=path, old_content=old_content, new_content=new_content, diff=diff)


def apply_changes(workspace: Workspace, changes: list[FileChange]) -> list[str]:
    written: list[str] = []
    for change in changes:
        target = workspace.resolve_for_write(change.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(change.new_content, encoding="utf-8")
        written.append(change.path)
    return written


@dataclass
class TestRunResult:
    command: str
    exit_code: int
    output: str


def validate_test_command(command: str) -> list[str]:
    if not command.strip():
        raise DevelopmentCommandError("Test command is required.")
    if any(token in command for token in BLOCKED_COMMAND_TOKENS):
        raise DevelopmentCommandError("Shell control operators are not allowed in test commands.")
    try:
        args = shlex.split(command, posix=False)
    except ValueError as exc:
        raise DevelopmentCommandError(str(exc))
    if not args:
        raise DevelopmentCommandError("Test command is required.")

    executable = args[0]
    if executable not in ALLOWED_TEST_EXECUTABLES:
        raise DevelopmentCommandError(
            "Only npm, pnpm, yarn, pytest, or python -m pytest are allowed test commands."
        )
    if executable in {"python", "python3"} and args[1:3] != ["-m", "pytest"]:
        raise DevelopmentCommandError("Python commands must use 'python -m pytest'.")
    return args


def run_test_command(workspace: Workspace, command: str, timeout_seconds: int = 120) -> TestRunResult:
    args = validate_test_command(command)
    completed = subprocess.run(
        args,
        cwd=workspace.root,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return TestRunResult(command=command, exit_code=completed.returncode, output=output)
