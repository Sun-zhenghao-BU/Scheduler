from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class GeneratedArtifacts:
    proposal: str
    design: str
    tasks: str
    specs: dict[str, str] = field(default_factory=dict)

    def preview_items(self) -> list[tuple[str, str]]:
        items = [
            ("proposal.md", self.proposal),
            ("design.md", self.design),
        ]
        items.extend((path, content) for path, content in sorted(self.specs.items()))
        items.append(("tasks.md", self.tasks))
        return items


TemplateLoader = Callable[[], dict[str, Path]]


class OpenSpecArtifactGenerator:
    def __init__(self, root: Path, template_loader: TemplateLoader | None = None) -> None:
        self.root = root
        self.template_loader = template_loader or self._load_template_paths

    def generate(self, title: str, request: str, change_name: str) -> GeneratedArtifacts:
        template_paths = self.template_loader()
        for required in ("proposal", "design", "specs", "tasks"):
            if required not in template_paths:
                raise ValueError(f"OpenSpec templates output is missing '{required}'.")
            if not template_paths[required].exists():
                raise FileNotFoundError(f"OpenSpec template not found: {template_paths[required].as_posix()}")

        request_text = request.strip() or title.strip()
        capability_name = change_name
        short_title = title.strip() or change_name.replace("-", " ")

        proposal = (
            "## Why\n\n"
            f"{request_text} needs a structured OpenSpec change so the work can move from request to implementation "
            "with clear artifacts and reviewable scope.\n\n"
            "## What Changes\n\n"
            f"- Introduce the `{capability_name}` capability for this change.\n"
            f"- Capture the requested work as OpenSpec proposal, design, spec, and tasks artifacts.\n"
            "- Provide an implementation path that can be reviewed and refined before coding.\n\n"
            "## Capabilities\n\n"
            "### New Capabilities\n"
            f"- `{capability_name}`: {short_title}\n\n"
            "### Modified Capabilities\n"
            "- None.\n\n"
            "## Impact\n\n"
            f"- Affected area: {request_text}\n"
            "- Artifact flow: proposal, design, specs, tasks\n"
            "- Delivery flow: implementation, review, fix, and release tracking\n"
        )

        design = (
            "## Context\n\n"
            f"Change title: {short_title}\n\n"
            f"The change is requested as: {request_text}\n\n"
            "## Goals / Non-Goals\n\n"
            "**Goals:**\n"
            f"- Define the `{capability_name}` capability clearly enough for implementation.\n"
            "- Keep the first implementation path small and reviewable.\n\n"
            "**Non-Goals:**\n"
            "- Unrelated refactors outside the requested change.\n"
            "- Additional capabilities not implied by the request.\n\n"
            "## Decisions\n\n"
            f"- Use `{capability_name}` as the primary capability name.\n"
            "- Describe behavior and scope in OpenSpec artifacts before implementation.\n"
            "- Use checklist tasks so progress can be tracked locally.\n\n"
            "## Risks / Trade-offs\n\n"
            "- The first draft may need refinement after review.\n"
            "- Scope may still need trimming if implementation reveals hidden complexity.\n"
        )

        spec_path = f"specs/{capability_name}/spec.md"
        spec_content = (
            "## ADDED Requirements\n\n"
            f"### Requirement: {short_title}\n"
            f"The system MUST support the requested change described as: {request_text}\n\n"
            "#### Scenario: Requested workflow is executed\n"
            f"- **WHEN** a user works on `{capability_name}`\n"
            "- **THEN** the project MUST have a clear OpenSpec definition for the work before implementation begins\n"
        )

        tasks = (
            f"## 1. Define `{capability_name}`\n\n"
            "- [ ] 1.1 Review and refine the generated proposal\n"
            "- [ ] 1.2 Review and refine the generated design and spec\n\n"
            "## 2. Implement and verify\n\n"
            f"- [ ] 2.1 Implement the requested behavior for `{capability_name}`\n"
            "- [ ] 2.2 Run verification and record review findings\n"
        )

        return GeneratedArtifacts(
            proposal=proposal,
            design=design,
            tasks=tasks,
            specs={spec_path: spec_content},
        )

    def _load_template_paths(self) -> dict[str, Path]:
        command = self._resolve_command(["openspec", "templates", "--json"])
        completed = subprocess.run(
            command,
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "openspec templates failed")
        data = json.loads(completed.stdout)
        return {
            artifact_id: Path(entry["path"])
            for artifact_id, entry in data.items()
            if isinstance(entry, dict) and isinstance(entry.get("path"), str)
        }

    def _resolve_command(self, command: list[str]) -> list[str]:
        if not command:
            return command
        if os.name == "nt" and command[0] == "openspec":
            shim = shutil.which("openspec.cmd") or shutil.which("openspec")
            if shim:
                return [shim, *command[1:]]
        return command
