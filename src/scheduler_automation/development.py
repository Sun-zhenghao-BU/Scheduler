from __future__ import annotations

import difflib
import json
import re
import shlex
import subprocess
from dataclasses import asdict, dataclass

from scheduler_automation.llm.client import LLMClient, get_llm_profile
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
    try:
        current = workspace.read_file(path)
        old_content = str(current["content"])
    except Exception:
        old_content = ""
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


def infer_test_command(workspace: Workspace) -> str:
    root = workspace.root
    if (root / "package.json").exists():
        return "npm test"
    if (root / "pyproject.toml").exists() or (root / "tests").exists():
        return "python -m pytest"
    return ""


async def propose_changes(workspace: Workspace, instruction: str, paths: list[str]) -> tuple[str, list[FileChange]]:
    if not paths:
        raise DevelopmentCommandError("Select at least one file to modify.")

    selected_files: list[dict[str, str | int]] = []
    for path in paths:
        selected_files.append(_read_file_for_proposal(workspace, path))

    profile = get_llm_profile("codegen")
    if not profile["api_key"]:
        raise DevelopmentCommandError("Configure an LLM API key before generating code changes.")

    files_text = "\n\n".join(
        f"## {item['path']}\n\n```text\n{item['content']}\n```"
        for item in selected_files
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a code editing agent. Return JSON only, without Markdown. "
                'Format: {"summary":"...","files":[{"path":"relative/path","content":"full file contents"}]}.'
            ),
        },
        {
            "role": "user",
            "content": f"Instruction: {instruction}\n\nCurrent files:\n\n{files_text}",
        },
    ]
    raw = await LLMClient(profile).chat(messages)
    return parse_proposed_changes(workspace, str(raw))


def parse_proposed_changes(workspace: Workspace, raw: str) -> tuple[str, list[FileChange]]:
    text = _extract_json(raw)
    data: dict[str, object] = json.loads(text)
    summary = str(data.get("summary", "Generated code changes."))
    changes: list[FileChange] = []
    for item in data.get("files", []):  # type: ignore[assignment]
        file_data = item if isinstance(item, dict) else {}
        path = str(file_data.get("path", ""))
        content = str(file_data.get("content", ""))
        if not path:
            continue
        changes.append(build_change(workspace, path, content))
    if not changes:
        raise DevelopmentCommandError("The model did not return any file changes.")
    return summary, changes


def _extract_json(raw: str) -> str:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        return fenced.group(1).strip()
    return text


def _read_file_for_proposal(workspace: Workspace, path: str) -> dict[str, str | int]:
    try:
        return workspace.read_file(path)
    except Exception:
        return {
            "path": path,
            "content": "",
            "size": 0,
        }
