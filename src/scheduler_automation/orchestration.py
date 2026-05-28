from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from scheduler_automation.agents.provider import AgentProvider, AgentResult
from scheduler_automation.agents.service import run_agent_roles
from scheduler_automation.execution import ExecutionRequest, ExecutionResult, execute_task
from scheduler_automation.workflow import WorkflowManager

ProposalFunc = Callable[[str, list[str], str], Awaitable[tuple[str, list[object]]]]
TestRunner = Callable[[str, str], object]


@dataclass
class OrchestrationResult:
    product_result: AgentResult
    execution_result: ExecutionResult
    tester_result: AgentResult
    final_stage: str
    release_ready: bool


async def run_task_orchestration(
    manager: WorkflowManager,
    task_id: str,
    provider: AgentProvider,
    execution_request: ExecutionRequest,
    proposal_func,
    test_runner,
) -> OrchestrationResult:
    metadata, _ = manager.get_task(task_id)
    if metadata.requirement_status != "confirmed":
        raise ValueError("Requirements must be confirmed before running the workflow.")

    manager.append_log(task_id, metadata.current_stage, "Workflow orchestration started")

    product_results = await run_agent_roles(manager, task_id, provider, ["product_manager"])
    product_result = product_results[0]
    metadata = manager.advance_task(task_id, "spec")

    execution_result = await execute_task(
        manager,
        task_id,
        execution_request,
        proposal_func,
        test_runner,
    )

    if execution_result.stage != "review":
        metadata = manager.advance_task(task_id, "review")
    tester_results = await run_agent_roles(manager, task_id, provider, ["tester"])
    tester_result = tester_results[0]

    release_ready = execution_result.test_exit_code == 0 and tester_result.status == "completed"
    final_stage = "release" if release_ready else "fix"
    metadata = manager.advance_task(task_id, final_stage)
    manager.append_log(
        task_id,
        metadata.current_stage,
        "Workflow orchestration finished"
        + (" and is ready for release" if release_ready else " and requires fixes"),
    )
    return OrchestrationResult(
        product_result=product_result,
        execution_result=execution_result,
        tester_result=tester_result,
        final_stage=metadata.current_stage,
        release_ready=release_ready,
    )
