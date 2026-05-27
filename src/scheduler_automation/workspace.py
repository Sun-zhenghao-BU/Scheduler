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

    def read_file(self, relative_path: str) -> dict[str, str | int]:
        path = self._resolve(relative_path)
        if not path.exists() or not path.is_file():
            raise WorkspaceAccessError("文件不存在")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceAccessError("文件过大，暂不支持读取")
        if path.suffix and path.suffix.lower() not in TEXT_EXTENSIONS:
            raise WorkspaceAccessError("仅支持读取文本文件")
        return {
            "path": path.relative_to(self.root).as_posix(),
            "content": path.read_text(encoding="utf-8", errors="replace"),
            "size": path.stat().st_size,
        }

    def summary(self, limit: int = 200) -> str:
        lines = [f"项目根目录：{self.root}"]
        for item in self.tree(limit=limit):
            prefix = "目录" if item["type"] == "directory" else "文件"
            lines.append(f"- [{prefix}] {item['path']}")
        return "\n".join(lines)

    def _resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if path != self.root and self.root not in path.parents:
            raise WorkspaceAccessError("不能访问项目目录之外的文件")
        if self._is_ignored(path):
            raise WorkspaceAccessError("该路径被忽略")
        return path

    def _is_ignored(self, path: Path) -> bool:
        try:
            relative_parts = path.relative_to(self.root).parts
        except ValueError:
            return True
        return any(part in IGNORED_DIRS for part in relative_parts)
