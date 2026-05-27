from __future__ import annotations

import difflib
from dataclasses import asdict, dataclass

from scheduler_automation.workspace import Workspace


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
