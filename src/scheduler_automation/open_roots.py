from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from scheduler_automation.workspace import Workspace, WorkspaceAccessError


@dataclass
class OpenRoot:
    root_id: str
    label: str
    path: str


def configured_open_roots() -> list[OpenRoot]:
    raw = os.environ.get("SCHEDULER_OPEN_ROOTS", "").strip()
    roots: list[OpenRoot] = []
    if raw:
        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = [part.strip() for part in chunk.split("|")]
            if len(parts) != 3:
                continue
            root_id, label, path = parts
            if path and Path(path).exists():
                roots.append(OpenRoot(root_id=root_id, label=label, path=path))

    if roots:
        return roots

    defaults = [
        OpenRoot(root_id="project", label="Current Project", path=os.environ.get("SCHEDULER_PROJECT_ROOT", "/workspace/project")),
        OpenRoot(root_id="c", label=os.environ.get("SCHEDULER_HOST_C_LABEL", "Windows (C:)"), path="/host/c"),
        OpenRoot(root_id="d", label=os.environ.get("SCHEDULER_HOST_D_LABEL", "Data (D:)"), path="/host/d"),
    ]
    return [root for root in defaults if Path(root.path).exists()]


def get_open_root(root_id: str) -> OpenRoot:
    for root in configured_open_roots():
        if root.root_id == root_id:
            return root
    raise FileNotFoundError(f"Open root '{root_id}' not found")


def list_open_root_children(root_id: str, relative_path: str = "") -> list[dict[str, str]]:
    root = get_open_root(root_id)
    workspace = Workspace(Path(root.path))
    directories = workspace.list_directories(relative_path)
    results: list[dict[str, str]] = []
    for item in directories:
        relative = item["path"]
        absolute = str((workspace.root / relative).resolve()).replace("\\", "/")
        results.append(
            {
                "name": item["name"],
                "path": absolute,
                "relative_path": relative,
                "type": "directory",
            }
        )
    return results
