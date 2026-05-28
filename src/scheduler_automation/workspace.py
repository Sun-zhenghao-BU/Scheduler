from __future__ import annotations

from pathlib import Path
from typing import TypedDict

IGNORED_DIRS = {
    ".git",
    ".idea",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
TEXT_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
MAX_FILE_BYTES = 512 * 1024


class WorkspaceAccessError(ValueError):
    pass


class WorkspaceItem(TypedDict):
    path: str
    name: str
    type: str


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def exists(self) -> bool:
        return self.root.exists() and self.root.is_dir()

    def tree(self, limit: int = 500) -> list[WorkspaceItem]:
        if not self.exists():
            return []

        results: list[WorkspaceItem] = []
        for path in sorted(self.root.rglob("*")):
            if len(results) >= limit:
                break
            if self._is_ignored(path):
                continue
            relative = path.relative_to(self.root).as_posix()
            results.append(
                {
                    "path": relative,
                    "name": path.name,
                    "type": "directory" if path.is_dir() else "file",
                }
            )
        return results

    def list_directories(self, relative_path: str = "") -> list[WorkspaceItem]:
        target = self._resolve(relative_path) if relative_path else self.root
        if not target.exists() or not target.is_dir():
            raise WorkspaceAccessError("Directory does not exist.")

        results: list[WorkspaceItem] = []
        for path in sorted(target.iterdir()):
            if not path.is_dir() or self._is_ignored(path):
                continue
            relative = path.relative_to(self.root).as_posix()
            results.append(
                {
                    "path": relative,
                    "name": path.name,
                    "type": "directory",
                }
            )
        return results

    def read_file(self, relative_path: str) -> dict[str, str | int]:
        path = self._resolve(relative_path)
        if not path.exists() or not path.is_file():
            raise WorkspaceAccessError("File does not exist.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceAccessError("File is too large to preview.")
        if path.suffix and path.suffix.lower() not in TEXT_EXTENSIONS:
            raise WorkspaceAccessError("Only text files can be previewed.")
        return {
            "path": path.relative_to(self.root).as_posix(),
            "content": path.read_text(encoding="utf-8", errors="replace"),
            "size": path.stat().st_size,
        }

    def resolve_for_write(self, relative_path: str) -> Path:
        return self._resolve(relative_path)

    def summary(self, limit: int = 200) -> str:
        lines = [f"Workspace root: {self.root}"]
        for item in self.tree(limit=limit):
            prefix = "dir" if item["type"] == "directory" else "file"
            lines.append(f"- [{prefix}] {item['path']}")
        return "\n".join(lines)

    def _resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if path != self.root and self.root not in path.parents:
            raise WorkspaceAccessError("Cannot access files outside the workspace.")
        if self._is_ignored(path):
            raise WorkspaceAccessError("This path is ignored.")
        return path

    def _is_ignored(self, path: Path) -> bool:
        try:
            relative_parts = path.relative_to(self.root).parts
        except ValueError:
            return True
        return any(part in IGNORED_DIRS for part in relative_parts)
