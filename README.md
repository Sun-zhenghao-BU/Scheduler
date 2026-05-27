# Scheduler Automation Workflow

This repository bootstraps a local automation workflow for software delivery on top of `OpenSpec` and `Superpowers`.
It models two primary roles:

- `OpenSpec`: turns raw requests into implementation-ready specifications.
- `Superpowers`: executes implementation, self-review, bug fixing, release notes, and delivery tracking.

## Current status

The repository is intentionally lightweight and uses only the Python standard library.

## Goal

The target workflow is:

1. You describe a requirement in natural language.
2. `OpenSpec` converts it into a proposal, design, and executable task list.
3. The implementation agent writes code against that spec.
4. The agent runs local verification and performs self-review.
5. The agent records bugs, fixes them, and updates logs.
6. Everything is committed directly to `main` and pushed to GitHub.

## Delivery plan

This repository is being built in the following sequence:

1. Set up a local task workflow and storage format.
2. Add `OpenSpec` project configuration and Codex skill wiring.
3. Add implementation, review, fix, and release tracking.
4. Add GitHub CI for baseline verification on every push to `main`.
5. Push the repository to GitHub and use it as the control plane for future automated changes.

## Workflow stages

1. `intake`: capture the original request.
2. `spec`: produce scope, acceptance criteria, architecture notes, and risks.
3. `implement`: track execution notes and generated code tasks.
4. `review`: self-review and code review findings.
5. `fix`: record bug fixes and verification notes.
6. `release`: prepare push/deploy notes and final checklist.

## Working process

The intended operating loop for this repository is:

1. Create or refine a change in `OpenSpec`.
2. Generate proposal, design, and task artifacts.
3. Implement tasks through the local workflow CLI or agent-driven execution.
4. Log verification results in the task journal.
5. Record review findings and bug fixes.
6. Commit all relevant changes.
7. Push directly to `main`.
8. Let GitHub Actions validate the repository.

## OpenSpec and Superpowers

This repository includes:

- `openspec/config.yaml` for spec-driven change management.
- `.codex/skills/openspec-*` skills for proposing, exploring, applying, and archiving changes.
- local workflow files under `src/scheduler_automation/` for task state, logs, and summaries.

The practical split is:

- Use `OpenSpec` to define what should be built.
- Use `Superpowers` and the local workflow engine to build it, review it, and close it out.

## Quick start

### CLI (original)

```powershell
python -m scheduler_automation.cli new-task --title "Build automated GitHub workflow"
python -m scheduler_automation.cli status
python -m scheduler_automation.cli advance --task <task-id> --stage spec
python -m scheduler_automation.cli log --task <task-id> --stage review --message "Reviewed CLI edge cases"
python -m scheduler_automation.cli show --task <task-id>
```

### Docker (recommended for production)

Build and run the full stack:

```powershell
$env:PROJECT_ROOT="D:\Work\YourProject"
docker compose up -d --build
```

If Docker Hub access is slow or blocked, pull the base images first:

```powershell
docker pull node:24-alpine
docker pull python:3.13-slim
docker compose up -d --build
```

This starts:
- **FastAPI** on port 80 (accessible at `http://localhost`)
- **API** under `/api/`
- **Health check** at `/healthz`
- **Read-only project workspace** mounted at `/workspace/project`

FastAPI serves the built frontend and API from the same container.

LLM config and task data are persisted in Docker volumes. The local path in `PROJECT_ROOT` is mounted read-only so agents can inspect code context without modifying your files.

### Web UI + API Server (development)

Start the FastAPI backend:

```powershell
pip install -e ".[server]"
uvicorn scheduler_automation.api.app:app --host 0.0.0.0 --port 8000
```

Start the frontend dev server:

```powershell
cd src/web
npm install
npm run dev
```

Then open `http://localhost:5173` in your browser.

### Configure LLM

1. Go to **系统设置** in the UI
2. Enter your API Key, Base URL, and model name
3. Click **测试连接** to verify
4. Supported providers: OpenAI, DeepSeek, 通义千问, Ollama (any OpenAI-compatible API)

## Repository layout

```text
.codex/                          Codex skills used in this repo
docs/                            Architecture notes
openspec/                        OpenSpec configuration
tasks/                           Generated workflow workspaces
src/scheduler_automation/        CLI, workflow engine, and API server
src/scheduler_automation/api/    FastAPI routes (tasks, LLM, config)
src/scheduler_automation/llm/    LLM client and prompt templates
src/web/                         React frontend (Vite + TypeScript + Ant Design)
tests/                           Standard-library test suite
```

## Git workflow

This repository currently uses direct pushes to `main`.

Standard cycle:

1. update spec or task artifacts
2. implement code
3. run tests
4. review changes
5. commit
6. push to `origin/main`

## Verification

Local verification:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
```

Remote verification:

- GitHub Actions runs the same test suite on pushes and pull requests.
