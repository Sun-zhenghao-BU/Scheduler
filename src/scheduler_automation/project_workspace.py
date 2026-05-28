from __future__ import annotations

import os
from pathlib import Path

from scheduler_automation.projects import ProjectManager
from scheduler_automation.workspace import Workspace


def load_workspace(repo_root: Path, project_id: str = "") -> Workspace | None:
    if project_id:
        project = ProjectManager(repo_root).get_project(project_id)
        if not project.root_path.strip():
            return None
        root = Path(project.root_path)
        if not root.is_absolute():
            root = repo_root / root
        return Workspace(root)
    root = Path(os.environ.get("SCHEDULER_PROJECT_ROOT", "/workspace/project"))
    if not root.is_absolute():
        root = repo_root / root
    return Workspace(root)
