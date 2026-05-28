from __future__ import annotations

from dataclasses import dataclass

from scheduler_automation.agents.provider import AgentProvider, AgentResult
from scheduler_automation.agents.service import run_agent_roles
from scheduler_automation.execution import ExecutionRequest, ExecutionResult, execute_task
from scheduler_automation.workflow import WorkflowManager


@dataclass
class OrchestrationResult:
    product_result: AgentResult
    developer_result: AgentResult
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
    metadata, task_dir = manager.get_task(task_id)
    if metadata.requirement_status != "confirmed":
        raise ValueError("Requirements must be confirmed before running the workflow.")

    manager.append_log(task_id, metadata.current_stage, "Workflow orchestration started")

    product_result = (await run_agent_roles(manager, task_id, provider, ["product_manager"]))[0]
    if product_result.status != "completed":
        raise ValueError(product_result.error or "Product manager failed to produce spec.md.")
    spec_path = task_dir / "spec.md"
    if not spec_path.exists() or not spec_path.read_text(encoding="utf-8").strip():
        raise ValueError("spec.md was not generated.")
    manager.advance_task(task_id, "spec")

    developer_result = (await run_agent_roles(manager, task_id, provider, ["developer"]))[0]
    if developer_result.status != "completed":
        raise ValueError(developer_result.error or "Developer failed to produce implementation.md.")
    implementation_path = task_dir / "implementation.md"
    if not implementation_path.exists() or not implementation_path.read_text(encoding="utf-8").strip():
        raise ValueError("implementation.md was not generated.")

    execution_result = await execute_task(
        manager,
        task_id,
        execution_request,
        proposal_func,
        test_runner,
    )

    manager.advance_task(task_id, "review")
    tester_result = (await run_agent_roles(manager, task_id, provider, ["tester"]))[0]
    if tester_result.status != "completed":
        raise ValueError(tester_result.error or "Tester failed to produce review.md.")
    review_path = task_dir / "review.md"
    if not review_path.exists() or not review_path.read_text(encoding="utf-8").strip():
        raise ValueError("review.md was not generated.")

    release_ready = execution_result.test_exit_code == 0 and tester_result.status == "completed"
    final_stage = "release" if release_ready else "fix"
    manager.advance_task(task_id, final_stage)
    manager.append_log(
        task_id,
        final_stage,
        "Workflow orchestration finished"
        + (" and is ready for release" if release_ready else " and requires fixes"),
    )
    return OrchestrationResult(
        product_result=product_result,
        developer_result=developer_result,
        execution_result=execution_result,
        tester_result=tester_result,
        final_stage=final_stage,
        release_ready=release_ready,
    )
