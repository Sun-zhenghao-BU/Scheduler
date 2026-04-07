# Workflow Visual Dashboard Design

## Goal

Provide a local browser-based dashboard for the workflow engine so a user can quickly see task progress, blockers, OpenSpec linkage, verification state, and review status without reading multiple files or repeatedly calling CLI commands.

## Scope

This change covers:

- a local HTTP server using only the Python standard library
- a single-page dashboard served at `/`
- JSON endpoints for task list and task detail data
- a task list panel and a task detail panel
- automatic polling refresh so the page updates without manual command re-entry

## Out Of Scope

- editing files from the browser
- stage transitions triggered from the browser
- real-time push updates
- authentication or remote access
- multi-page navigation

## User Flow

1. The user starts the dashboard locally.
2. The browser opens `http://127.0.0.1:<port>`.
3. The left panel shows all tasks with stage and ready/blocked state.
4. Clicking a task loads the right panel with detailed workflow information.
5. The page refreshes data on a fixed polling interval.

## Architecture

### Service Layer

Add a dashboard module that starts a local `ThreadingHTTPServer`.

Endpoints:

- `/`: HTML shell for the dashboard
- `/api/tasks`: all task summaries
- `/api/tasks/<task-id>`: one task detail payload

### Data Source

Reuse `WorkflowManager` as the source of truth. The dashboard should not duplicate gate logic. It should read task snapshots and render them.

### Frontend

Serve a single HTML page with embedded CSS and JavaScript:

- left column: task list
- right column: selected task detail
- polling every 5 seconds

### Display Model

Task list items should show:

- title
- task id
- current stage
- ready or blocked label
- bound change name

Task detail should show:

- current stage
- stage progress bar
- next action
- blocked reasons
- OpenSpec change name and path
- OpenSpec task completion count
- last verification state
- open high-severity review findings

## Error Handling

- if no tasks exist, the dashboard should show an empty state rather than an error
- if a task disappears between list fetch and detail fetch, return 404 JSON
- malformed paths should return 404

## Testing Strategy

Add tests for:

- task summary JSON shape
- task detail JSON shape
- HTML page response
- missing task 404 behavior

Use temporary task directories and the existing `WorkflowManager` test patterns.

## Risks

- embedded HTML/CSS/JS can become noisy if the page grows too much
- polling may briefly show stale state between refreshes
- Windows browser auto-open behavior may vary, so first version should not depend on GUI launch
