from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace

from scheduler_automation.agents.provider import AgentProvider, AgentResult
from scheduler_automation.agents.service import run_agent_roles
from scheduler_automation.execution import ExecutionRequest, ExecutionResult, execute_task
from scheduler_automation.workflow import WorkflowIssue, WorkflowManager, WorkflowState, utc_timestamp

MAX_FIX_ROUNDS = 2


@dataclass
class TesterDecision:
    summary: str
    blocking: bool
    severity: str
    recommended_action: str
    issues: list[WorkflowIssue]


@dataclass
class OrchestrationResult:
    product_result: AgentResult
    developer_result: AgentResult
    execution_result: ExecutionResult
    tester_result: AgentResult
    final_stage: str
    release_ready: bool
    fix_rounds: int


async def run_task_orchestration(
    manager: WorkflowManager,
    task_id: str,
    provider: AgentProvider,
    execution_request: ExecutionRequest,
    proposal_func,
    test_runner,
) -> OrchestrationResult:
    metadata, task_dir = manager.get_task(task_id)
    if metadata.requirement_status != "confirmed":
        raise ValueError("Requirements must be confirmed before running the workflow.")

    state = manager.load_workflow_state(task_id)
    state.status = "running"
    state.current_round = 0
    state.max_rounds = MAX_FIX_ROUNDS
    state.current_stage = metadata.current_stage
    state.release_ready = False
    state.requires_human_review = False
    state.last_error = ""
    state.updated_at = utc_timestamp()
    state.issues = []
    manager.save_workflow_state(task_id, state)

    manager.append_log(task_id, metadata.current_stage, "Workflow orchestration started")

    product_result = (await run_agent_roles(manager, task_id, provider, ["product_manager"]))[0]
    _require_completed_artifact(product_result, task_dir / "spec.md", "spec.md", "Product manager")
    manager.advance_task(task_id, "spec")

    developer_result = (await run_agent_roles(manager, task_id, provider, ["developer"]))[0]
    _require_completed_artifact(developer_result, task_dir / "implementation.md", "implementation.md", "Developer")

    execution_result = await execute_task(manager, task_id, execution_request, proposal_func, test_runner)
    manager.advance_task(task_id, "review")

    tester_result = (await run_agent_roles(manager, task_id, provider, ["tester"]))[0]
    _require_completed_artifact(tester_result, task_dir / "review.md", "review.md", "Tester")
    tester_decision = _parse_tester_decision(tester_result, execution_result)
    _update_state_from_decision(manager, task_id, tester_decision, execution_result, 0)

    fix_rounds = 0
    while _should_retry(execution_result, tester_decision, fix_rounds):
        fix_rounds += 1
        manager.advance_task(task_id, "fix")
        manager.write_fix_summary(task_id, fix_rounds, execution_result.test_output, tester_result.content)
        manager.append_log(task_id, "fix", f"Starting automatic fix round {fix_rounds}")

        developer_result = (await run_agent_roles(manager, task_id, provider, ["developer"]))[0]
        _require_completed_artifact(developer_result, task_dir / "implementation.md", "implementation.md", "Developer")

        retry_request = _build_fix_execution_request(execution_request, execution_result, tester_result, fix_rounds)
        execution_result = await execute_task(manager, task_id, retry_request, proposal_func, test_runner)
        manager.advance_task(task_id, "review")
        tester_result = (await run_agent_roles(manager, task_id, provider, ["tester"]))[0]
        _require_completed_artifact(tester_result, task_dir / "review.md", "review.md", "Tester")
        tester_decision = _parse_tester_decision(tester_result, execution_result)
        _update_state_from_decision(manager, task_id, tester_decision, execution_result, fix_rounds)

    release_ready = execution_result.test_exit_code == 0 and not tester_decision.blocking and tester_decision.recommended_action != "fix"
    final_stage = "release" if release_ready else ("spec" if tester_decision.recommended_action == "spec" else "fix")
    manager.advance_task(task_id, final_stage)

    state = manager.load_workflow_state(task_id)
    state.status = "completed" if release_ready else "needs_attention"
    state.current_round = fix_rounds
    state.current_stage = final_stage
    state.release_ready = release_ready
    state.requires_human_review = (not release_ready) and (fix_rounds >= MAX_FIX_ROUNDS or tester_decision.recommended_action == "spec")
    state.updated_at = utc_timestamp()
    manager.save_workflow_state(task_id, state)

    if release_ready:
        manager.write_release_summary(
            task_id,
            "自动流程确认本任务满足当前发布条件。",
            execution_result.test_command,
            execution_result.test_output,
        )
    manager.append_log(
        task_id,
        final_stage,
        "Workflow orchestration finished"
        + (" and is ready for release" if release_ready else " and still requires fixes"),
    )
    return OrchestrationResult(
        product_result=product_result,
        developer_result=developer_result,
        execution_result=execution_result,
        tester_result=tester_result,
        final_stage=final_stage,
        release_ready=release_ready,
        fix_rounds=fix_rounds,
    )


def _require_completed_artifact(result: AgentResult, path, file_name: str, owner: str) -> None:
    if result.status != "completed":
        raise ValueError(result.error or f"{owner} failed to produce {file_name}.")
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        raise ValueError(f"{file_name} was not generated.")


def _build_fix_execution_request(
    base_request: ExecutionRequest,
    execution_result: ExecutionResult,
    tester_result: AgentResult,
    round_number: int,
) -> ExecutionRequest:
    fix_instruction = ((base_request.instruction.strip() + "\n\n") if base_request.instruction.strip() else "") + (
        f"Fix round {round_number}.\n\n"
        f"Tester review:\n{tester_result.content or tester_result.error}\n\n"
        f"Failing test output:\n{execution_result.test_output}\n\n"
        "Update the implementation to resolve the failure while keeping the approved requirement intact."
    )
    return replace(base_request, instruction=fix_instruction)


def _extract_json_object(content: str) -> dict[str, object] | None:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = content[start : end + 1]
    if not candidate:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_tester_decision(result: AgentResult, execution_result: ExecutionResult) -> TesterDecision:
    data = _extract_json_object(result.content)
    if data:
        issues: list[WorkflowIssue] = []
        for item in data.get("issues", []):  # type: ignore[assignment]
            if not isinstance(item, dict):
                continue
            issues.append(
                WorkflowIssue(
                    title=str(item.get("title", "Unnamed issue")),
                    severity=str(item.get("severity", "medium")),
                    blocking=bool(item.get("blocking", True)),
                    source="tester",
                )
            )
        return TesterDecision(
            summary=str(data.get("summary", "")).strip() or "Tester completed review.",
            blocking=bool(data.get("blocking", execution_result.test_exit_code != 0)),
            severity=str(data.get("severity", "medium")),
            recommended_action=str(data.get("recommended_action", "fix")),
            issues=issues,
        )

    fallback_blocking = execution_result.test_exit_code != 0
    return TesterDecision(
        summary=result.content.strip() or ("Tests passed." if not fallback_blocking else "Tests failed and require fixes."),
        blocking=fallback_blocking,
        severity="high" if fallback_blocking else "low",
        recommended_action="fix" if fallback_blocking else "release",
        issues=(
            [WorkflowIssue(title="Test command failed", severity="high", blocking=True, source="tester")]
            if fallback_blocking
            else []
        ),
    )


def _update_state_from_decision(
    manager: WorkflowManager,
    task_id: str,
    tester_decision: TesterDecision,
    execution_result: ExecutionResult,
    round_number: int,
) -> None:
    state = manager.load_workflow_state(task_id)
    state.current_round = round_number
    state.current_stage = "review"
    state.last_test_exit_code = execution_result.test_exit_code
    state.last_test_command = execution_result.test_command
    state.last_test_output = execution_result.test_output
    state.tester_summary = tester_decision.summary
    state.recommended_action = tester_decision.recommended_action
    state.release_ready = execution_result.test_exit_code == 0 and not tester_decision.blocking
    state.last_error = execution_result.test_output if execution_result.test_exit_code != 0 else ""
    state.issues = tester_decision.issues
    state.updated_at = utc_timestamp()
    manager.save_workflow_state(task_id, state)


def _should_retry(execution_result: ExecutionResult, tester_decision: TesterDecision, fix_rounds: int) -> bool:
    return (
        fix_rounds < MAX_FIX_ROUNDS
        and (execution_result.test_exit_code != 0 or tester_decision.blocking)
        and tester_decision.recommended_action == "fix"
    )
