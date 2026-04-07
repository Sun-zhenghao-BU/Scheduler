from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from scheduler_automation.workflow import STAGES, WorkflowManager


class DashboardApp:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.manager = WorkflowManager(root)

    def build_task_list_payload(self) -> dict[str, object]:
        tasks = []
        for snapshot in self.manager.list_task_snapshots():
            tasks.append(
                {
                    "task_id": snapshot.metadata.task_id,
                    "title": snapshot.metadata.title,
                    "current_stage": snapshot.metadata.current_stage,
                    "state": "BLOCKED" if snapshot.blocked_reasons else "READY",
                    "change_name": snapshot.metadata.change_name,
                }
            )
        return {"tasks": tasks}

    def build_task_detail_payload(self, task_id: str) -> dict[str, object]:
        snapshot = self.manager.task_snapshot(task_id)
        return {
            "task": {
                "task_id": snapshot.metadata.task_id,
                "title": snapshot.metadata.title,
                "current_stage": snapshot.metadata.current_stage,
                "change_name": snapshot.metadata.change_name,
                "change_path": snapshot.metadata.change_path,
                "next_action": snapshot.next_action,
                "suggested_actions": snapshot.suggested_actions,
                "blocked_reasons": snapshot.blocked_reasons,
                "progress": {
                    "complete": snapshot.progress.complete,
                    "total": snapshot.progress.total,
                    "incomplete": snapshot.progress.incomplete,
                },
                "verification": self.manager._verification_label(snapshot.metadata),
                "high_findings_open": snapshot.review_summary.open_by_severity.get("high", 0),
                "stage_order": list(STAGES),
            }
        }

    def render_index_html(self) -> str:
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Scheduler Dashboard</title>
  <style>
    :root {
      --bg: #f4efe7;
      --panel: #fffaf2;
      --ink: #1f1d1a;
      --muted: #6a6258;
      --line: #d7ccbd;
      --ready: #2f7d4a;
      --blocked: #b2432f;
      --accent: #a66a2c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background: radial-gradient(circle at top left, #fdf6ea, var(--bg));
    }
    .shell {
      display: grid;
      grid-template-columns: minmax(280px, 360px) 1fr;
      min-height: 100vh;
    }
    .panel {
      padding: 24px;
      border-right: 1px solid var(--line);
      background: rgba(255, 250, 242, 0.92);
      backdrop-filter: blur(6px);
    }
    .detail {
      padding: 24px 28px;
    }
    h1, h2, h3, h4, p { margin-top: 0; }
    .subtle { color: var(--muted); }
    .task-button {
      width: 100%;
      text-align: left;
      border: 1px solid var(--line);
      background: white;
      padding: 14px;
      margin-bottom: 12px;
      border-radius: 14px;
      cursor: pointer;
    }
    .task-button.active {
      border-color: var(--accent);
      box-shadow: 0 10px 30px rgba(166, 106, 44, 0.12);
    }
    .pill {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      margin-right: 8px;
      margin-bottom: 8px;
      color: white;
    }
    .ready { background: var(--ready); }
    .blocked { background: var(--blocked); }
    .stage-strip {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 8px;
      margin: 20px 0 24px;
    }
    .stage {
      padding: 10px 8px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: white;
      text-align: center;
      font-size: 13px;
    }
    .stage.current {
      border-color: var(--accent);
      background: #fff1de;
      font-weight: bold;
    }
    .card {
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.78);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 16px;
    }
    ul { margin: 0; padding-left: 20px; }
    .empty {
      border: 1px dashed var(--line);
      border-radius: 16px;
      padding: 16px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.6);
    }
    @media (max-width: 900px) {
      .shell { grid-template-columns: 1fr; }
      .panel { border-right: 0; border-bottom: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside class="panel">
      <h1>Workflow Board</h1>
      <p class="subtle">Auto-refreshes every 5 seconds.</p>
      <div id="task-list"></div>
    </aside>
    <section class="detail">
      <div id="task-detail"></div>
    </section>
  </div>
  <script>
    const state = { selectedTaskId: null, timer: null };

    async function fetchJson(url) {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      return response.json();
    }

    function renderTaskList(tasks) {
      const container = document.getElementById('task-list');
      if (!tasks.length) {
        container.innerHTML = '<div class="empty">No tasks found yet.</div>';
        document.getElementById('task-detail').innerHTML = '<div class="empty">Select a task after creating one.</div>';
        return;
      }

      if (!state.selectedTaskId || !tasks.some(task => task.task_id === state.selectedTaskId)) {
        state.selectedTaskId = tasks[0].task_id;
      }

      container.innerHTML = tasks.map(task => `
        <button class="task-button ${task.task_id === state.selectedTaskId ? 'active' : ''}" data-task-id="${task.task_id}">
          <strong>${task.title}</strong><br>
          <span class="subtle">${task.task_id}</span><br><br>
          <span class="pill ${task.state === 'READY' ? 'ready' : 'blocked'}">${task.state}</span>
          <span class="subtle">${task.current_stage}</span><br>
          <span class="subtle">${task.change_name}</span>
        </button>
      `).join('');

      for (const button of container.querySelectorAll('.task-button')) {
        button.addEventListener('click', () => {
          state.selectedTaskId = button.dataset.taskId;
          refresh();
        });
      }
    }

    function renderTaskDetail(task) {
      const detail = document.getElementById('task-detail');
      const blocked = task.blocked_reasons.length
        ? `<ul>${task.blocked_reasons.map(reason => `<li>${reason}</li>`).join('')}</ul>`
        : '<p class="subtle">No blockers.</p>';
      const suggested = task.suggested_actions.length
        ? `<ol>${task.suggested_actions.map(step => `<li>${step}</li>`).join('')}</ol>`
        : '<p class="subtle">No manual step required.</p>';
      const stages = task.stage_order.map(stage => `
        <div class="stage ${stage === task.current_stage ? 'current' : ''}">${stage}</div>
      `).join('');

      detail.innerHTML = `
        <h2>${task.title}</h2>
        <p class="subtle">${task.task_id}</p>
        <div class="pill ${task.blocked_reasons.length ? 'blocked' : 'ready'}">
          ${task.blocked_reasons.length ? 'BLOCKED' : 'READY'}
        </div>
        <div class="stage-strip">${stages}</div>
        <div class="card">
          <h3>Next Action</h3>
          <p>${task.next_action}</p>
        </div>
        <div class="card">
          <h3>Recommended Steps</h3>
          ${suggested}
        </div>
        <div class="card">
          <h3>OpenSpec</h3>
          <p><strong>Change:</strong> ${task.change_name}</p>
          <p><strong>Path:</strong> ${task.change_path}</p>
          <p><strong>Tasks:</strong> ${task.progress.complete}/${task.progress.total} complete</p>
        </div>
        <div class="card">
          <h3>Quality State</h3>
          <p><strong>Verification:</strong> ${task.verification}</p>
          <p><strong>Open high findings:</strong> ${task.high_findings_open}</p>
        </div>
        <div class="card">
          <h3>Next-Step Blockers</h3>
          ${blocked}
        </div>
      `;
    }

    async function refresh() {
      try {
        const listPayload = await fetchJson('/api/tasks');
        renderTaskList(listPayload.tasks);
        if (state.selectedTaskId) {
          const detailPayload = await fetchJson(`/api/tasks/${encodeURIComponent(state.selectedTaskId)}`);
          renderTaskDetail(detailPayload.task);
        }
      } catch (error) {
        document.getElementById('task-detail').innerHTML = `<div class="empty">${error.message}</div>`;
      }
    }

    refresh();
    state.timer = setInterval(refresh, 5000);
  </script>
</body>
</html>
"""

    def handle_request(self, path: str) -> tuple[int, str, bytes]:
        parsed = urlparse(path)
        if parsed.path == "/":
            return 200, "text/html; charset=utf-8", self.render_index_html().encode("utf-8")
        if parsed.path == "/api/tasks":
            return 200, "application/json; charset=utf-8", json.dumps(self.build_task_list_payload()).encode("utf-8")
        if parsed.path.startswith("/api/tasks/"):
            task_id = unquote(parsed.path.removeprefix("/api/tasks/"))
            try:
                payload = self.build_task_detail_payload(task_id)
            except FileNotFoundError:
                return 404, "application/json; charset=utf-8", json.dumps({"error": "Task not found"}).encode("utf-8")
            return 200, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8")
        return 404, "application/json; charset=utf-8", json.dumps({"error": "Not found"}).encode("utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    app: DashboardApp

    def do_GET(self) -> None:  # noqa: N802
        status, content_type, body = self.app.handle_request(self.path)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local workflow dashboard.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind. Default: 127.0.0.1")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind. Default: 8000")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    app = DashboardApp(Path.cwd())
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"app": app})
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
