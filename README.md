# Scheduler Automation Workflow

This repository bootstraps a local automation workflow for software delivery.
It models two roles:

- `OpenSpec`: turns raw requests into implementation-ready specifications.
- `Superpower`: executes implementation, self-review, bug fixing, release notes, and delivery tracking.

## Current status

The repository is intentionally lightweight and uses only the Python standard library.

## Workflow stages

1. `intake`: capture the original request.
2. `spec`: produce scope, acceptance criteria, architecture notes, and risks.
3. `implement`: track execution notes and generated code tasks.
4. `review`: self-review and code review findings.
5. `fix`: record bug fixes and verification notes.
6. `release`: prepare push/deploy notes and final checklist.

## Quick start

```powershell
python -m scheduler_automation.cli new-task --title "Build automated GitHub workflow"
python -m scheduler_automation.cli status
python -m scheduler_automation.cli advance --task <task-id> --stage spec
python -m scheduler_automation.cli log --task <task-id> --stage review --message "Reviewed CLI edge cases"
python -m scheduler_automation.cli show --task <task-id>
```

## Repository layout

```text
docs/                     Architecture notes
tasks/                    Generated workflow workspaces
src/scheduler_automation/ CLI and workflow engine
tests/                    Standard-library test suite
```

## Next implementation steps

1. Initialize Git locally.
2. Create the GitHub repository named `Scheduler`.
3. Add the remote and push the first commit.
4. Wire GitHub Actions after Git is available.
