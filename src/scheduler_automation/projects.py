from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from scheduler_automation.workflow import slugify, utc_timestamp


@dataclass
class ProjectMetadata:
    project_id: str
    name: str
    root_path: str
    created_at: str
    updated_at: str


class ProjectManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.projects_dir = self.root / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.projects_dir / "index.json"

    def create_project(self, name: str, root_path: str = "") -> ProjectMetadata:
        projects = self.list_projects()
        base_id = slugify(name)
        project_id = base_id
        suffix = 2
        existing_ids = {project.project_id for project in projects}
        while project_id in existing_ids:
            project_id = f"{base_id}-{suffix}"
            suffix += 1

        now = utc_timestamp()
        project = ProjectMetadata(
            project_id=project_id,
            name=name.strip(),
            root_path=root_path.strip(),
            created_at=now,
            updated_at=now,
        )
        projects.append(project)
        self._write_projects(projects)
        return project

    def list_projects(self) -> list[ProjectMetadata]:
        if not self.index_path.exists():
            return []
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        return [ProjectMetadata(**item) for item in data.get("projects", [])]

    def get_project(self, project_id: str) -> ProjectMetadata:
        for project in self.list_projects():
            if project.project_id == project_id:
                return project
        raise FileNotFoundError(f"Project '{project_id}' does not exist.")

    def update_project_root_path(self, project_id: str, root_path: str) -> ProjectMetadata:
        projects = self.list_projects()
        for index, project in enumerate(projects):
            if project.project_id != project_id:
                continue
            updated = ProjectMetadata(
                project_id=project.project_id,
                name=project.name,
                root_path=root_path.strip(),
                created_at=project.created_at,
                updated_at=utc_timestamp(),
            )
            projects[index] = updated
            self._write_projects(projects)
            return updated
        raise FileNotFoundError(f"Project '{project_id}' does not exist.")

    def _write_projects(self, projects: list[ProjectMetadata]) -> None:
        self.index_path.write_text(
            json.dumps({"projects": [asdict(project) for project in projects]}, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
