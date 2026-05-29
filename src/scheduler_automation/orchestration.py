from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace

from scheduler_automation.agents.provider import AgentProvider, AgentResult
from scheduler_automation.agents.service import run_agent_roles
from scheduler_automation.execution import ExecutionRequest, ExecutionResult, execute_task
from scheduler_automation.workflow import ReleaseGateCheck, WorkflowIssue, WorkflowManager, utc_timestamp

MAX_FIX_ROUNDS = 2
MAX_SPEC_ROUNDS = 1


@dataclass
class TesterDecision:
    summary: str
    blocking: bool
    severity: str
    recommended_action: str
    issues: list[WorkflowIssue]


@dataclass
class ReleaseGateDecision:
    ready: bool
    status: str
    reason: str
    checks: list[ReleaseGateCheck]


@dataclass
class OrchestrationResult:
    product_result: AgentResult
    developer_result: AgentResult
    execution_result: ExecutionResult
    tester_result: AgentResult
    final_stage: str
    release_ready: bool
    fix_rounds: int
    spec_rounds: int


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
    state.max_rounds = MAX_FIX_ROUNDS + MAX_SPEC_ROUNDS
    state.current_stage = metadata.current_stage
    state.active_step = "starting"
    state.step_message = "正在初始化自动流程。"
    state.release_ready = False
    state.requires_human_review = False
    state.last_error = ""
    state.release_gate_status = "running"
    state.release_gate_reason = ""
    state.release_gate_checks = []
    state.updated_at = utc_timestamp()
    state.issues = []
    manager.save_workflow_state(task_id, state)
    manager.append_log(task_id, metadata.current_stage, "自动流程开始执行")

    product_result = await _run_product_stage(manager, task_id, provider, task_dir)
    developer_result = await _run_developer_stage(manager, task_id, provider, task_dir)

    _set_progress(manager, task_id, "implement", "execution", "正在生成代码修改并写回项目。")
    manager.append_log(task_id, "implement", "开始执行代码修改")
    execution_result = await execute_task(manager, task_id, execution_request, proposal_func, test_runner)
    manager.append_log(task_id, "implement", "代码修改已完成，准备进入测试评审")

    _set_progress(manager, task_id, "review", "test_execution", "代码修改已完成，正在执行测试命令。")
    manager.note_file_progress(task_id, "review.md", "执行状态", "正在执行测试命令，请稍候。")
    tester_result, tester_decision = await _run_tester_stage(manager, task_id, provider, task_dir, execution_result, 0)

    fix_rounds = 0
    spec_rounds = 0

    while True:
        if tester_decision.recommended_action == "spec" and spec_rounds < MAX_SPEC_ROUNDS:
            spec_rounds += 1
            manager.advance_task(task_id, "spec")
            manager.write_spec_feedback(task_id, spec_rounds, tester_decision.summary, execution_result.test_output)
            manager.append_log(task_id, "spec", f"开始方案回流，第 {spec_rounds} 轮")

            product_result = await _run_product_stage(manager, task_id, provider, task_dir)
            developer_result = await _run_developer_stage(manager, task_id, provider, task_dir)
            retry_request = _build_spec_execution_request(execution_request, execution_result, tester_result, spec_rounds)

            _set_progress(manager, task_id, "implement", "execution", "方案已修订，正在重新生成代码修改。")
            execution_result = await execute_task(manager, task_id, retry_request, proposal_func, test_runner)
            _set_progress(manager, task_id, "review", "test_execution", "方案回流后的代码已写入，正在重新执行测试。")
            tester_result, tester_decision = await _run_tester_stage(
                manager,
                task_id,
                provider,
                task_dir,
                execution_result,
                fix_rounds + spec_rounds,
            )
            continue

        if _should_retry_fix(execution_result, tester_decision, fix_rounds):
            fix_rounds += 1
            manager.advance_task(task_id, "fix")
            manager.write_fix_summary(task_id, fix_rounds, execution_result.test_output, tester_result.content)
            manager.append_log(task_id, "fix", f"开始自动修复，第 {fix_rounds} 轮")

            developer_result = await _run_developer_stage(manager, task_id, provider, task_dir)
            retry_request = _build_fix_execution_request(execution_request, execution_result, tester_result, fix_rounds)

            _set_progress(manager, task_id, "implement", "execution", "正在根据测试结果自动修复并重新写回代码。")
            execution_result = await execute_task(manager, task_id, retry_request, proposal_func, test_runner)
            _set_progress(manager, task_id, "review", "test_execution", "修复后的代码已写入，正在重新执行测试。")
            tester_result, tester_decision = await _run_tester_stage(
                manager,
                task_id,
                provider,
                task_dir,
                execution_result,
                fix_rounds + spec_rounds,
            )
            continue

        break

    gate = _evaluate_release_gate(execution_result, tester_decision)
    release_ready = gate.ready
    final_stage = "release" if release_ready else ("spec" if tester_decision.recommended_action == "spec" else "fix")
    manager.advance_task(task_id, final_stage)

    state = manager.load_workflow_state(task_id)
    state.status = "completed" if release_ready else "needs_attention"
    state.current_round = fix_rounds + spec_rounds
    state.max_rounds = MAX_FIX_ROUNDS + MAX_SPEC_ROUNDS
    state.current_stage = final_stage
    state.active_step = "completed" if release_ready else "waiting_attention"
    state.step_message = "自动流程已完成。" if release_ready else f"自动流程停在 {final_stage}，需要继续处理。"
    state.release_ready = release_ready
    state.requires_human_review = not release_ready and (
        (tester_decision.recommended_action == "spec" and spec_rounds >= MAX_SPEC_ROUNDS)
        or (tester_decision.recommended_action == "fix" and fix_rounds >= MAX_FIX_ROUNDS)
        or tester_decision.recommended_action not in {"release", "fix", "spec"}
    )
    state.release_gate_status = gate.status
    state.release_gate_reason = gate.reason
    state.release_gate_checks = gate.checks
    state.updated_at = utc_timestamp()
    manager.save_workflow_state(task_id, state)

    if release_ready:
        manager.write_release_summary(
            task_id,
            "自动流程确认本任务满足当前发布条件。",
            execution_result.test_command,
            execution_result.test_output,
        )
        manager.append_log(task_id, "release", "发布门禁通过，已生成发布记录")
    else:
        manager.append_log(task_id, final_stage, f"自动流程停在 {final_stage}，门禁原因：{gate.reason}")

    manager.append_log(
        task_id,
        final_stage,
        "自动流程结束" + ("，已达到发布条件" if release_ready else "，需要继续处理"),
    )
    return OrchestrationResult(
        product_result=product_result,
        developer_result=developer_result,
        execution_result=execution_result,
        tester_result=tester_result,
        final_stage=final_stage,
        release_ready=release_ready,
        fix_rounds=fix_rounds,
        spec_rounds=spec_rounds,
    )


async def _run_product_stage(manager: WorkflowManager, task_id: str, provider: AgentProvider, task_dir) -> AgentResult:
    _set_progress(manager, task_id, "spec", "product_manager", "正在生成产品规划（spec.md）。")
    manager.note_file_progress(task_id, "spec.md", "生成状态", "正在生成产品规划，请稍候。")
    manager.append_log(task_id, "spec", "开始生成产品规划")
    product_result = (await run_agent_roles(manager, task_id, provider, ["product_manager"]))[0]
    _require_completed_artifact(product_result, task_dir / "spec.md", "spec.md", "产品经理")
    manager.advance_task(task_id, "spec")
    manager.append_log(task_id, "spec", "产品规划已生成")
    return product_result


async def _run_developer_stage(manager: WorkflowManager, task_id: str, provider: AgentProvider, task_dir) -> AgentResult:
    _set_progress(manager, task_id, "implement", "developer", "正在生成实施方案（implementation.md）。")
    manager.note_file_progress(task_id, "implementation.md", "生成状态", "正在生成实施方案，请稍候。")
    manager.append_log(task_id, "implement", "开始生成实施方案")
    developer_result = (await run_agent_roles(manager, task_id, provider, ["developer"]))[0]
    _require_completed_artifact(developer_result, task_dir / "implementation.md", "implementation.md", "开发代理")
    manager.append_log(task_id, "implement", "实施方案已生成")
    return developer_result


async def _run_tester_stage(
    manager: WorkflowManager,
    task_id: str,
    provider: AgentProvider,
    task_dir,
    execution_result: ExecutionResult,
    round_number: int,
) -> tuple[AgentResult, TesterDecision]:
    _set_progress(manager, task_id, "review", "tester", "正在生成测试评审（review.md）。")
    manager.note_file_progress(task_id, "review.md", "生成状态", "正在生成测试评审，请稍候。")
    manager.advance_task(task_id, "review")
    manager.append_log(task_id, "review", "开始生成测试评审")
    tester_result = (await run_agent_roles(manager, task_id, provider, ["tester"]))[0]
    _require_completed_artifact(tester_result, task_dir / "review.md", "review.md", "测试代理")
    tester_decision = _parse_tester_decision(tester_result, execution_result)
    _update_state_from_decision(manager, task_id, tester_decision, execution_result, round_number)
    manager.append_log(task_id, "review", "测试评审已生成")
    return tester_result, tester_decision


def _set_progress(manager: WorkflowManager, task_id: str, stage: str, active_step: str, step_message: str) -> None:
    state = manager.load_workflow_state(task_id)
    state.status = "running"
    state.current_stage = stage
    state.active_step = active_step
    state.step_message = step_message
    state.updated_at = utc_timestamp()
    manager.save_workflow_state(task_id, state)


def _require_completed_artifact(result: AgentResult, path, file_name: str, owner: str) -> None:
    if result.status != "completed":
        raise ValueError(result.error or f"{owner} 未能生成 {file_name}。")
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        raise ValueError(f"{file_name} 未生成。")


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


def _build_spec_execution_request(
    base_request: ExecutionRequest,
    execution_result: ExecutionResult,
    tester_result: AgentResult,
    round_number: int,
) -> ExecutionRequest:
    spec_instruction = ((base_request.instruction.strip() + "\n\n") if base_request.instruction.strip() else "") + (
        f"Spec round {round_number}.\n\n"
        f"Tester review:\n{tester_result.content or tester_result.error}\n\n"
        f"Recent test output:\n{execution_result.test_output}\n\n"
        "Refine the implementation based on the revised product plan. Resolve requirement gaps before coding."
    )
    return replace(base_request, instruction=spec_instruction)


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
                    category=str(item.get("category", "")),
                    evidence=str(item.get("evidence", "")),
                )
            )
        return TesterDecision(
            summary=str(data.get("summary", "")).strip() or "测试代理已完成评审。",
            blocking=bool(data.get("blocking", execution_result.test_exit_code != 0)),
            severity=str(data.get("severity", "medium")),
            recommended_action=str(data.get("recommended_action", "fix")),
            issues=issues,
        )

    fallback_blocking = execution_result.test_exit_code != 0
    return TesterDecision(
        summary=result.content.strip() or ("测试通过。" if not fallback_blocking else "测试失败，需要修复。"),
        blocking=fallback_blocking,
        severity="high" if fallback_blocking else "low",
        recommended_action="fix" if fallback_blocking else "release",
        issues=(
            [WorkflowIssue(title="测试命令失败", severity="high", blocking=True, source="tester", category="test_env")]
            if fallback_blocking
            else []
        ),
    )


def _evaluate_release_gate(execution_result: ExecutionResult, tester_decision: TesterDecision) -> ReleaseGateDecision:
    blocking_issues = [issue for issue in tester_decision.issues if issue.blocking]
    high_severity_issues = [issue for issue in tester_decision.issues if issue.severity.lower() == "high"]
    checks = [
        ReleaseGateCheck(
            name="tests_passed",
            passed=execution_result.test_exit_code == 0,
            detail="测试退出码必须为 0。",
        ),
        ReleaseGateCheck(
            name="tester_not_blocking",
            passed=not tester_decision.blocking,
            detail="测试代理不能给出阻塞发布结论。",
        ),
        ReleaseGateCheck(
            name="recommended_release",
            passed=tester_decision.recommended_action == "release",
            detail="测试代理建议动作必须是 release。",
        ),
        ReleaseGateCheck(
            name="no_blocking_issues",
            passed=not blocking_issues,
            detail="不能存在 blocking=true 的问题项。",
        ),
        ReleaseGateCheck(
            name="no_high_severity_issues",
            passed=not high_severity_issues,
            detail="不能存在 high 严重级别问题项。",
        ),
    ]
    failed = [check for check in checks if not check.passed]
    if not failed:
        return ReleaseGateDecision(
            ready=True,
            status="passed",
            reason="所有发布门禁均已通过。",
            checks=checks,
        )
    return ReleaseGateDecision(
        ready=False,
        status="blocked",
        reason="；".join(check.detail for check in failed),
        checks=checks,
    )


def _should_retry_fix(execution_result: ExecutionResult, tester_decision: TesterDecision, fix_rounds: int) -> bool:
    return (
        fix_rounds < MAX_FIX_ROUNDS
        and (
            execution_result.test_exit_code != 0
            or tester_decision.blocking
            or tester_decision.recommended_action == "fix"
        )
        and tester_decision.recommended_action != "spec"
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
    state.active_step = "tester_review"
    state.step_message = "测试评审已生成，正在判断下一步动作。"
    state.last_test_exit_code = execution_result.test_exit_code
    state.last_test_command = execution_result.test_command
    state.last_test_output = execution_result.test_output
    state.tester_summary = tester_decision.summary
    state.recommended_action = tester_decision.recommended_action
    state.issues = tester_decision.issues
    state.updated_at = utc_timestamp()
    manager.save_workflow_state(task_id, state)
