from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from scheduler_automation.artifact_generation import OpenSpecArtifactGenerator
from scheduler_automation.workflow import STAGES, ReviewSummary, WorkflowManager


class DashboardApp:
    def __init__(self, root: Path, manager: WorkflowManager | None = None) -> None:
        self.root = root
        self.manager = manager or WorkflowManager(
            root,
            artifact_generator=OpenSpecArtifactGenerator(root),
            confirm_write=lambda *_: True,
        )

    def build_task_list_payload(self) -> dict[str, object]:
        tasks = []
        for snapshot in self.manager.list_task_snapshots():
            completed = self._is_completed(snapshot.metadata)
            state = self._task_state(snapshot.metadata.current_stage, snapshot.blocked_reasons, completed=completed)
            tasks.append(
                {
                    "task_id": snapshot.metadata.task_id,
                    "title": snapshot.metadata.title,
                    "current_stage": snapshot.metadata.current_stage,
                    "state": state["label"],
                    "status_tone": state["tone"],
                    "completed": completed,
                    "change_name": snapshot.metadata.change_name,
                }
            )
        return {"tasks": tasks}

    def build_task_detail_payload(self, task_id: str) -> dict[str, object]:
        snapshot = self.manager.task_snapshot(task_id)
        metadata, task_dir = self.manager.get_task(task_id)
        completion = self.manager.completion_evidence(task_id)
        compare = self.manager.task_compare(task_id)
        completed = self._is_completed(metadata)
        state = self._task_state(metadata.current_stage, snapshot.blocked_reasons, completed)
        conclusion = self._task_conclusion(snapshot.next_action, state["label"], snapshot.blocked_reasons, completed)
        findings = [
            {
                "finding_id": finding.finding_id,
                "severity": finding.severity,
                "status": finding.status,
                "summary": finding.summary,
            }
            for finding in snapshot.review_summary.findings
        ]
        return {
            "task": {
                "task_id": metadata.task_id,
                "title": metadata.title,
                "current_stage": metadata.current_stage,
                "stage_progress": self._stage_progress(metadata.current_stage, completed),
                "change_name": metadata.change_name,
                "change_path": metadata.change_path,
                "next_action": snapshot.next_action,
                "suggested_actions": snapshot.suggested_actions,
                "blocked_reasons": snapshot.blocked_reasons,
                "progress": {
                    "complete": snapshot.progress.complete,
                    "total": snapshot.progress.total,
                    "incomplete": snapshot.progress.incomplete,
                },
                "verification": self.manager._verification_label(metadata),
                "high_findings_open": snapshot.review_summary.open_by_severity.get("high", 0),
                "stage_order": list(STAGES),
                "timeline": self._read_timeline(task_dir / "journal.md"),
                "conclusion": conclusion,
                "status": state["label"],
                "status_tone": state["tone"],
                "review_findings": findings,
                "artifacts": self._artifact_preview(metadata.change_name, task_dir),
                "completion": completion,
                "compare": compare,
                "can_step": not completed and metadata.current_stage != "release",
                "can_autopilot": not completed,
                "can_verify": not completed and metadata.current_stage in {"implement", "fix"},
                "can_review": not completed and metadata.current_stage == "review",
                "can_complete": metadata.current_stage == "release" and not completed,
                "completed": completed,
            }
        }

    def render_index_html(self) -> str:
        return """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scheduler Workbench</title>
<style>
body{font-family:Segoe UI,Tahoma,sans-serif;background:#f3f1eb;color:#231f1a;margin:0}
.page{max-width:1320px;margin:0 auto;padding:16px}
.box{background:#fff;border:1px solid #d8cab6;border-radius:12px;padding:12px;margin-bottom:10px}
.workspace{display:grid;grid-template-columns:300px 1fr;gap:12px;align-items:start}
.sidebar{position:sticky;top:12px;max-height:calc(100vh - 24px);overflow:auto}
.row{display:flex;gap:8px;flex-wrap:wrap}
input,textarea,button{padding:8px 10px;border:1px solid #d8cab6;border-radius:8px}
textarea{min-height:80px;min-width:320px}
button{cursor:pointer}
.pill{display:inline-block;padding:3px 8px;border-radius:999px;color:#fff;font-size:12px}
.ok{background:#2f7d4a}.warn{background:#b55a1f}.bad{background:#b2432f}
.task-list-title{font-size:12px;letter-spacing:.06em;color:#756858;text-transform:uppercase;margin:8px 0 6px}
.task-item{width:100%;text-align:left;background:#fff;border:1px solid #d8cab6;border-radius:10px;padding:10px;margin-bottom:8px}
.task-item.active{border-color:#2f7d4a;box-shadow:0 0 0 1px #2f7d4a inset}
.task-item .name{font-weight:600}
.task-item .meta{font-size:12px;color:#6a5d4e;margin-top:4px}
pre{white-space:pre-wrap;word-break:break-word}
.grid{display:grid;grid-template-columns:1.2fr 1fr;gap:10px}
.stage-flow{display:flex;flex-wrap:wrap;gap:10px}
.stage-node{display:flex;align-items:center;gap:6px}
.stage-node .dot{width:12px;height:12px;border-radius:50%;display:inline-block;border:1px solid #6a5d4e;background:#f8f4ed}
.stage-node .label{font-size:12px;text-transform:capitalize;color:#6a5d4e}
.stage-node.done .dot{background:#2f7d4a;border-color:#2f7d4a}
.stage-node.current .dot{background:#b55a1f;border-color:#b55a1f}
.stage-node.pending .dot{background:#f8f4ed;border-color:#bcae9b}
.stage-node .line{display:inline-block;width:26px;height:2px;background:#c8b9a5;margin-left:2px}
@media(max-width:1000px){.workspace{grid-template-columns:1fr}.sidebar{position:static;max-height:none}}
@media(max-width:860px){.grid{grid-template-columns:1fr}}
</style></head>
<body><div class="page">
<div class="workspace">
  <aside class="box sidebar">
    <h3>Tasks</h3>
    <div id="task-list">Loading...</div>
  </aside>
  <main>
    <div class="box row">
      <input id="new-task-title" placeholder="New task title">
      <textarea id="new-task-request" placeholder="Describe request"></textarea>
      <label><input id="new-task-autopilot" type="checkbox" checked> Run autopilot after create</label>
      <button id="create-task">Create Task</button>
    </div>
    <div class="box row">
      <button id="refresh-task">Refresh</button>
      <button id="continue-step">Continue One Step</button>
      <button id="run-verify">Run Verify</button>
      <button id="record-review">Record Review</button>
      <button id="continue-autopilot">Continue Autopilot</button>
      <button id="set-baseline">Set Baseline</button>
      <button id="complete-task">Archive, Commit, Push</button>
    </div>
    <div id="flash"></div>
    <div id="task-detail" class="box">Loading task...</div>
  </main>
</div>
</div>
<script>
const state={selectedTaskId:null,busy:false};
async function fetchJson(url,opts={}){const r=await fetch(url,{cache:'no-store',...opts});const t=await r.text();const p=t?JSON.parse(t):{};if(!r.ok)throw new Error(p.error||`Request failed: ${r.status}`);return p;}
function flash(m){document.getElementById('flash').textContent=m||'';}
function setBusy(v){state.busy=v;['create-task','new-task-title','new-task-request','new-task-autopilot','continue-step','run-verify','record-review','continue-autopilot','set-baseline','complete-task','refresh-task'].forEach(id=>{const n=document.getElementById(id);if(n)n.disabled=v;});}
function taskItemHtml(task){return `<button class="task-item ${task.task_id===state.selectedTaskId?'active':''}" data-task-id="${task.task_id}"><div class="name">${task.title}</div><div class="meta">${task.current_stage} | ${task.change_name}</div><span class="pill ${task.status_tone==='ok'?'ok':task.status_tone==='warn'?'warn':'bad'}">${task.state}</span></button>`;}
function renderTaskList(tasks){const panel=document.getElementById('task-list');if(!tasks.length){state.selectedTaskId=null;panel.innerHTML='<div>No tasks found yet.</div>';document.getElementById('task-detail').innerHTML='No tasks found yet.';return;}const running=tasks.filter(t=>!t.completed);const completed=tasks.filter(t=>t.completed);const ordered=[...running,...completed];if(!state.selectedTaskId||!ordered.some(t=>t.task_id===state.selectedTaskId)){state.selectedTaskId=(running[0]||ordered[0]).task_id;}const runningHtml=running.length?running.map(taskItemHtml).join(''):'<div>No running tasks.</div>';const doneHtml=completed.length?completed.map(taskItemHtml).join(''):'<div>No completed tasks.</div>';panel.innerHTML=`<div class="task-list-title">Running</div>${runningHtml}<div class="task-list-title">Completed</div>${doneHtml}`;}
function artifactsHtml(items){if(!items.length)return '<div>No artifacts</div>';return items.map(i=>`<details><summary>${i.path}</summary><pre>${i.content}</pre></details>`).join('');}
function stageProgressHtml(items){if(!items||!items.length)return '<div>No stage data</div>';return `<div class="stage-flow">${items.map((s,i)=>`<div class="stage-node ${s.state}"><span class="dot"></span><span class="label">${s.stage}</span>${i<items.length-1?'<span class="line"></span>':''}</div>`).join('')}</div>`;}
function compareHtml(compare){if(!compare||!compare.available){return `<div>${compare&&compare.reason?compare.reason:'Compare not available'}</div><p><small>Click "Set Baseline" to start clean compare for this task.</small></p>`;}const committed=compare.related_committed_files.length?`<ul>${compare.related_committed_files.map(f=>`<li>${f.path} (+${f.added}/-${f.deleted})</li>`).join('')}</ul>`:'<div>No related committed delta in range.</div>';const working=compare.related_working_tree.length?`<ul>${compare.related_working_tree.map(f=>`<li>${f.status} ${f.path}</li>`).join('')}</ul>`:'<div>Related working tree clean.</div>';const hiddenCommitted=compare.hidden_committed_count?`<p><small>${compare.hidden_committed_count} unrelated committed file(s) hidden.</small></p>`:'';const hiddenWorking=compare.hidden_working_count?`<p><small>${compare.hidden_working_count} unrelated working tree file(s) hidden.</small></p>`:'';return `<p><b>Range:</b> ${compare.commit_range}</p><p><b>Totals:</b> ${compare.totals.files} files, +${compare.totals.added}/-${compare.totals.deleted}</p><h5>Related committed changes</h5>${committed}${hiddenCommitted}<h5>Related working tree</h5>${working}${hiddenWorking}`;}
function completionHtml(completion){if(!completion){return '<div>Not completed yet.</div>';}const checks=completion.checks?`<p>Archive exists: ${completion.checks.archive_exists?'yes':'no'}</p><p>Metadata archived: ${completion.checks.metadata_archived?'yes':'no'}</p>`:'';const sha=completion.commit_sha||'unavailable';return `<p><b>Completed at:</b> ${completion.completed_at}</p><p><b>Archive:</b> ${completion.archive_path}</p><p><b>Commit:</b> ${sha}</p><p><b>Evidence file:</b> ${completion.path}</p>${checks}`;}
function renderTaskDetail(task){const blocked=task.blocked_reasons.length?`<ul>${task.blocked_reasons.map(r=>`<li>${r}</li>`).join('')}</ul>`:'<div>No blockers</div>';const suggested=task.suggested_actions.length?`<ol>${task.suggested_actions.map(r=>`<li>${r}</li>`).join('')}</ol>`:'<div>No manual step required</div>';const timeline=task.timeline.length?task.timeline.map(e=>`<div><small>${e.timestamp} | ${e.stage}</small><div>${e.message}</div></div>`).join(''):'<div>No timeline</div>';const findings=task.review_findings.length?task.review_findings.map(f=>`<div><small>${f.finding_id} | ${f.severity} | ${f.status}</small><div>${f.summary}</div></div>`).join(''):'<div>No findings</div>';document.getElementById('task-detail').innerHTML=`<div><h2>${task.title}</h2><div>${task.task_id}</div><span class="pill ${task.status_tone==='ok'?'ok':task.status_tone==='warn'?'warn':'bad'}">${task.status}</span><p><b>Stage:</b> ${task.current_stage} | <b>Change:</b> ${task.change_name}</p><h3>${task.conclusion.title}</h3><p>${task.conclusion.body}</p></div><div class="grid"><div><div class="box"><h4>Stage Progress</h4>${stageProgressHtml(task.stage_progress)}</div><div class="box"><h4>Recommended Steps</h4>${suggested}</div><div class="box"><h4>Execution Timeline</h4>${timeline}</div><div class="box"><h4>Stage Artifacts</h4>${artifactsHtml(task.artifacts)}</div></div><div><div class="box"><h4>Quality</h4><p>Verification: ${task.verification}</p><p>Open high findings: ${task.high_findings_open}</p><p>OpenSpec tasks: ${task.progress.complete}/${task.progress.total}</p></div><div class="box"><h4>Review Findings</h4>${findings}</div><div class="box"><h4>Code Delta vs Baseline</h4>${compareHtml(task.compare)}</div><div class="box"><h4>Completion Evidence</h4>${completionHtml(task.completion)}</div><div class="box"><h4>Blockers</h4>${blocked}</div></div></div>`;document.getElementById('continue-step').disabled=state.busy||!task.can_step;document.getElementById('run-verify').disabled=state.busy||!task.can_verify;document.getElementById('record-review').disabled=state.busy||!task.can_review;document.getElementById('continue-autopilot').disabled=state.busy||!task.can_autopilot;document.getElementById('set-baseline').disabled=state.busy;document.getElementById('complete-task').disabled=state.busy||!task.can_complete;}
async function loadTaskList(){const p=await fetchJson('/api/tasks');renderTaskList(p.tasks||[]);}
async function loadTaskDetail(){if(!state.selectedTaskId)return;const p=await fetchJson(`/api/tasks/${encodeURIComponent(state.selectedTaskId)}`);renderTaskDetail(p.task);}
async function refresh(){try{await loadTaskList();await loadTaskDetail();}catch(e){document.getElementById('task-detail').innerHTML=e.message;}}
async function runAction(action,busyText){if(!state.selectedTaskId){flash('Select a task first.');return;}setBusy(true);flash(busyText);try{const p=await fetchJson(`/api/tasks/${encodeURIComponent(state.selectedTaskId)}/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});flash(p.result.message||'Action complete.');renderTaskDetail(p.task);}catch(e){flash(e.message);}finally{setBusy(false);await refresh();}}
async function createTask(){const title=document.getElementById('new-task-title').value.trim();const request=document.getElementById('new-task-request').value.trim();const runAutopilot=document.getElementById('new-task-autopilot').checked;if(!title){flash('Task title is required.');return;}setBusy(true);flash('Creating task...');try{const p=await fetchJson('/api/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,request,run_autopilot:runAutopilot})});state.selectedTaskId=p.task.task_id;flash(p.result.message||'Task created.');document.getElementById('new-task-title').value='';document.getElementById('new-task-request').value='';await refresh();}catch(e){flash(e.message);}finally{setBusy(false);}}
document.getElementById('task-list').addEventListener('click',async e=>{const item=e.target.closest('[data-task-id]');if(!item)return;state.selectedTaskId=item.dataset.taskId;await loadTaskDetail();await loadTaskList();});
document.getElementById('refresh-task').addEventListener('click',refresh);
document.getElementById('create-task').addEventListener('click',createTask);
document.getElementById('continue-step').addEventListener('click',()=>runAction('step','Continuing one workflow step...'));
document.getElementById('run-verify').addEventListener('click',()=>runAction('verify','Running verification...'));
document.getElementById('record-review').addEventListener('click',()=>runAction('review','Recording review...'));
document.getElementById('continue-autopilot').addEventListener('click',()=>runAction('autopilot','Running autopilot...'));
document.getElementById('set-baseline').addEventListener('click',()=>runAction('baseline','Setting baseline commit...'));
document.getElementById('complete-task').addEventListener('click',()=>{if(confirm('This will archive the change, commit, and push to the remote. Continue?'))runAction('complete','Completing task...');});
refresh();setInterval(refresh,5000);
</script></body></html>
"""

    def handle_request(self, method: str, path: str, body: bytes = b"") -> tuple[int, str, bytes]:
        parsed = urlparse(path)
        if method == "GET" and parsed.path == "/":
            return 200, "text/html; charset=utf-8", self.render_index_html().encode("utf-8")
        if method == "GET" and parsed.path == "/api/tasks":
            return 200, "application/json; charset=utf-8", json.dumps(self.build_task_list_payload()).encode("utf-8")
        if method == "POST" and parsed.path == "/api/tasks":
            return self._handle_create_task_request(body)
        if method == "GET" and parsed.path.startswith("/api/tasks/"):
            task_id = unquote(parsed.path.removeprefix("/api/tasks/"))
            try:
                payload = self.build_task_detail_payload(task_id)
            except FileNotFoundError:
                return 404, "application/json; charset=utf-8", json.dumps({"error": "Task not found"}).encode("utf-8")
            return 200, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8")
        if method == "POST" and parsed.path.startswith("/api/tasks/"):
            return self._handle_action_request(parsed.path)
        return 404, "application/json; charset=utf-8", json.dumps({"error": "Not found"}).encode("utf-8")

    def _handle_create_task_request(self, body: bytes) -> tuple[int, str, bytes]:
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            return 400, "application/json; charset=utf-8", json.dumps({"error": "Invalid JSON payload"}).encode("utf-8")

        title = str(payload.get("title", "")).strip()
        request = str(payload.get("request", "")).strip()
        run_autopilot = bool(payload.get("run_autopilot", False))
        if not title:
            return 400, "application/json; charset=utf-8", json.dumps({"error": "title is required"}).encode("utf-8")
        try:
            metadata = self.manager.create_task(title, request)
            result_payload: dict[str, object] = {
                "action": "create_task",
                "task_id": metadata.task_id,
                "message": f"Task {metadata.task_id} created.",
            }
            if run_autopilot:
                autopilot = self.manager.autopilot_task(metadata.task_id)
                result_payload["autopilot_final_stage"] = autopilot.final_stage
                result_payload["autopilot_stop_reason"] = autopilot.stop_reason
                result_payload["message"] = (
                    f"Task {metadata.task_id} created and autopilot stopped at {autopilot.final_stage}."
                )
            task_payload = self.build_task_detail_payload(metadata.task_id)["task"]
            return self._ok_json({"result": result_payload, "task": task_payload})
        except (FileNotFoundError, RuntimeError, ValueError) as error:
            return 400, "application/json; charset=utf-8", json.dumps({"error": str(error)}).encode("utf-8")

    def _handle_action_request(self, path: str) -> tuple[int, str, bytes]:
        match = re.match(r"^/api/tasks/(?P<task_id>[^/]+)/(?P<action>step|verify|review|autopilot|baseline|complete)$", path)
        if not match:
            return 404, "application/json; charset=utf-8", json.dumps({"error": "Not found"}).encode("utf-8")
        task_id = unquote(match.group("task_id"))
        action = match.group("action")

        try:
            if action == "step":
                message = self._step_task(task_id)
                task_payload = self.build_task_detail_payload(task_id)["task"]
                return self._ok_json({"result": {"action": "step", "message": message}, "task": task_payload})
            if action == "verify":
                verification = self.manager.verify_task(task_id)
                task_payload = self.build_task_detail_payload(task_id)["task"]
                return self._ok_json(
                    {
                        "result": {
                            "action": "verify",
                            "passed": verification.passed,
                            "message": f"Verification {'passed' if verification.passed else 'failed'}.",
                        },
                        "task": task_payload,
                    }
                )
            if action == "review":
                summary = self.manager.review_task(task_id)
                task_payload = self.build_task_detail_payload(task_id)["task"]
                return self._ok_json({"result": self._review_result(summary), "task": task_payload})
            if action == "autopilot":
                result = self.manager.autopilot_task(task_id)
                task_payload = self.build_task_detail_payload(task_id)["task"]
                return self._ok_json(
                    {
                        "result": {
                            "action": "autopilot",
                            "final_stage": result.final_stage,
                            "ready_for_completion": result.ready_for_completion,
                            "stop_reason": result.stop_reason,
                            "actions": result.actions,
                            "message": f"Autopilot stopped at {result.final_stage}: {result.stop_reason}",
                        },
                        "task": task_payload,
                    }
                )
            if action == "baseline":
                metadata = self.manager.set_task_baseline(task_id)
                task_payload = self.build_task_detail_payload(task_id)["task"]
                return self._ok_json(
                    {
                        "result": {
                            "action": "baseline",
                            "base_commit": metadata.base_commit,
                            "message": f"Baseline set to {metadata.base_commit}.",
                        },
                        "task": task_payload,
                    }
                )
            result = self.manager.complete_task(task_id)
            task_payload = self.build_task_detail_payload(task_id)["task"]
            return self._ok_json(
                {
                    "result": {
                        "action": "complete",
                        "archive_path": result.archive_path,
                        "commit_message": result.commit_message,
                        "commit_sha": result.commit_sha,
                        "evidence_path": result.evidence_path,
                        "message": f"Task completed and pushed. Archive: {result.archive_path}",
                    },
                    "task": task_payload,
                }
            )
        except (FileNotFoundError, RuntimeError, ValueError) as error:
            return 400, "application/json; charset=utf-8", json.dumps({"error": str(error)}).encode("utf-8")

    def _step_task(self, task_id: str) -> str:
        metadata, _task_dir = self.manager.get_task(task_id)
        if metadata.current_stage == "intake":
            self.manager.advance_task(task_id, "spec")
            return "Advanced to spec."
        if metadata.current_stage == "spec":
            self.manager.advance_task(task_id, "implement")
            return "Advanced to implement."
        if metadata.current_stage == "implement":
            if metadata.last_verified_at is None:
                verification = self.manager.verify_task(task_id)
                return f"Verification {'passed' if verification.passed else 'failed'} in implement stage."
            self.manager.advance_task(task_id, "review")
            return "Advanced to review."
        if metadata.current_stage == "review":
            summary = self.manager.review_task(task_id)
            if summary.open_by_severity.get("high", 0):
                self.manager.advance_task(task_id, "fix")
                return "Review found blocking issues. Advanced to fix."
            self.manager.advance_task(task_id, "release")
            return "Review passed. Advanced to release."
        if metadata.current_stage == "fix":
            refreshed, _ = self.manager.get_task(task_id)
            if refreshed.last_reviewed_at and (
                refreshed.last_verified_at is None or refreshed.last_verified_at <= refreshed.last_reviewed_at
            ):
                verification = self.manager.verify_task(task_id)
                return f"Verification {'passed' if verification.passed else 'failed'} in fix stage."
            self.manager.advance_task(task_id, "review")
            return "Advanced back to review."
        return "Already in release. Use complete when ready."

    def _review_result(self, summary: ReviewSummary) -> dict[str, object]:
        return {
            "action": "review",
            "high": summary.open_by_severity.get("high", 0),
            "medium": summary.open_by_severity.get("medium", 0),
            "low": summary.open_by_severity.get("low", 0),
            "message": "Review state recorded.",
        }

    def _artifact_preview(self, change_name: str, task_dir: Path) -> list[dict[str, str]]:
        previews: list[dict[str, str]] = []
        change_dir = self.manager.changes_dir / change_name

        for filename in ("request.md", "spec.md", "implementation.md", "review.md", "fixes.md", "release.md"):
            path = task_dir / filename
            if path.exists():
                previews.append(
                    {
                        "path": f"tasks/{task_dir.name}/{filename}",
                        "content": self._clip_text(path.read_text(encoding="utf-8")),
                    }
                )

        for filename in ("proposal.md", "design.md", "tasks.md"):
            path = change_dir / filename
            if path.exists():
                previews.append(
                    {
                        "path": f"openspec/changes/{change_name}/{filename}",
                        "content": self._clip_text(path.read_text(encoding="utf-8")),
                    }
                )

        spec_dir = change_dir / "specs"
        if spec_dir.exists():
            for path in sorted(spec_dir.glob("**/*.md"))[:2]:
                previews.append(
                    {
                        "path": path.relative_to(self.root).as_posix(),
                        "content": self._clip_text(path.read_text(encoding="utf-8")),
                    }
                )
        return previews

    def _clip_text(self, text: str, max_lines: int = 60, max_chars: int = 4000) -> str:
        lines = text.splitlines()
        clipped = "\n".join(lines[:max_lines])
        if len(clipped) > max_chars:
            clipped = clipped[:max_chars]
        if len(lines) > max_lines or len(text) > len(clipped):
            clipped += "\n\n... (truncated)"
        return clipped

    def _ok_json(self, payload: dict[str, object]) -> tuple[int, str, bytes]:
        return 200, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8")

    def _task_state(self, current_stage: str, blocked_reasons: list[str], completed: bool) -> dict[str, str]:
        if completed:
            return {"label": "Completed", "tone": "ok"}
        if current_stage == "release":
            return {"label": "Waiting for release confirmation", "tone": "warn"}
        if current_stage == "fix":
            return {"label": "Waiting for code changes", "tone": "bad"}
        if blocked_reasons:
            return {"label": "Waiting for workflow input", "tone": "warn"}
        return {"label": "Ready to continue", "tone": "ok"}

    def _task_conclusion(
        self,
        next_action: str,
        status_label: str,
        blocked_reasons: list[str],
        completed: bool,
    ) -> dict[str, str]:
        if completed:
            return {
                "title": "Task completed",
                "body": "This task has already been archived, committed, and pushed.",
            }
        if blocked_reasons:
            return {
                "title": status_label,
                "body": blocked_reasons[0],
            }
        if next_action == "complete":
            return {
                "title": "Ready for final release",
                "body": "All non-destructive workflow steps are complete. Confirm archive, commit, and push when ready.",
            }
        return {
            "title": "Autopilot can continue",
            "body": f"The next planned action is `{next_action}`. Use Continue One Step or Continue Autopilot.",
        }

    def _stage_progress(self, current_stage: str, completed: bool) -> list[dict[str, str]]:
        if completed:
            return [{"stage": stage, "state": "done"} for stage in STAGES]
        current_index = STAGES.index(current_stage)
        progress: list[dict[str, str]] = []
        for index, stage in enumerate(STAGES):
            if index < current_index:
                state = "done"
            elif index == current_index:
                state = "current"
            else:
                state = "pending"
            progress.append({"stage": stage, "state": state})
        return progress

    def _read_timeline(self, journal_path: Path) -> list[dict[str, str]]:
        if not journal_path.exists():
            return []
        entries: list[dict[str, str]] = []
        pattern = re.compile(r"^- (?P<timestamp>\S+) \[(?P<stage>[^\]]+)\] (?P<message>.+)$")
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            entries.append(match.groupdict())
        entries.reverse()
        return entries

    def _is_completed(self, metadata: object) -> bool:
        return isinstance(metadata.change_path, str) and "openspec/changes/archive/" in metadata.change_path


class DashboardHandler(BaseHTTPRequestHandler):
    app: DashboardApp

    def do_GET(self) -> None:  # noqa: N802
        status, content_type, body = self.app.handle_request("GET", self.path)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else b""
        status, content_type, response = self.app.handle_request("POST", self.path, body)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

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
