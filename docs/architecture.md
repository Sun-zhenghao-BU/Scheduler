# Architecture

## Goal

Provide a local workflow system that converts a natural-language request into a durable implementation workspace.

## Role mapping

### OpenSpec

Responsible for:

- Restating the user request.
- Defining scope and out-of-scope boundaries.
- Producing acceptance criteria.
- Capturing architecture decisions and risks.

### Superpower

Responsible for:

- Translating the spec into executable work items.
- Recording implementation progress.
- Running self-review and code review checkpoints.
- Logging fixes, release notes, and deployment steps.

## System components

1. CLI entrypoint
2. Workflow engine
3. Task workspace generator
4. Stage-aware logging
5. Review and release templates

## Task workspace structure

Each task is generated under `tasks/<task-id>/` with:

- `request.md`
- `spec.md`
- `implementation.md`
- `review.md`
- `fixes.md`
- `release.md`
- `journal.md`
- `metadata.json`

## Why this shape

This design makes the workflow inspectable, versionable, and Git-friendly. It also lets you later swap the role prompts for real external skills or agents without changing task state management.
