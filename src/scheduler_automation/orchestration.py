from __future__ import annotations

from dataclasses import dataclass, replace

from scheduler_automation.agents.provider import AgentProvider, AgentResult
from scheduler_automation.agents.service import run_agent_roles
from scheduler_automation.execution import ExecutionRequest, ExecutionResult, execute_task
from scheduler_automation.workflow import WorkflowManager

MAX_FIX_ROUNDS = 2


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

    manager.append_log(task_id, metadata.current_stage, "Workflow orchestration started")

    product_result = (await run_agent_roles(manager, task_id, provider, ["product_manager"]))[0]
    _require_completed_artifact(product_result, task_dir / "spec.md", "spec.md", "Product manager")
    manager.advance_task(task_id, "spec")

    developer_result = (await run_agent_roles(manager, task_id, provider, ["developer"]))[0]
    _require_completed_artifact(developer_result, task_dir / "implementation.md", "implementation.md", "Developer")

    execution_result = await execute_task(
        manager,
        task_id,
        execution_request,
        proposal_func,
        test_runner,
    )
    manager.advance_task(task_id, "review")

    tester_result = (await run_agent_roles(manager, task_id, provider, ["tester"]))[0]
    _require_completed_artifact(tester_result, task_dir / "review.md", "review.md", "Tester")

    fix_rounds = 0
    while execution_result.test_exit_code != 0 and fix_rounds < MAX_FIX_ROUNDS:
        fix_rounds += 1
        manager.advance_task(task_id, "fix")
        manager.write_fix_summary(task_id, fix_rounds, execution_result.test_output, tester_result.content)
        manager.append_log(task_id, "fix", f"Starting automatic fix round {fix_rounds}")

        developer_result = (await run_agent_roles(manager, task_id, provider, ["developer"]))[0]
        _require_completed_artifact(developer_result, task_dir / "implementation.md", "implementation.md", "Developer")

        retry_request = _build_fix_execution_request(execution_request, execution_result, tester_result, fix_rounds)
        execution_result = await execute_task(
            manager,
            task_id,
            retry_request,
            proposal_func,
            test_runner,
        )
        manager.advance_task(task_id, "review")
        tester_result = (await run_agent_roles(manager, task_id, provider, ["tester"]))[0]
        _require_completed_artifact(tester_result, task_dir / "review.md", "review.md", "Tester")

    release_ready = execution_result.test_exit_code == 0 and tester_result.status == "completed"
    final_stage = "release" if release_ready else "fix"
    manager.advance_task(task_id, final_stage)
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
    fix_instruction = (
        (base_request.instruction.strip() + "\n\n") if base_request.instruction.strip() else ""
    ) + (
        f"Fix round {round_number}.\n\n"
        f"Tester review:\n{tester_result.content or tester_result.error}\n\n"
        f"Failing test output:\n{execution_result.test_output}\n\n"
        "Update the implementation to resolve the failure while keeping the approved requirement intact."
    )
    return replace(base_request, instruction=fix_instruction)
