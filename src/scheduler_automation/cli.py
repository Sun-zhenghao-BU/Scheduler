from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from scheduler_automation.artifact_generation import GeneratedArtifacts, OpenSpecArtifactGenerator
from scheduler_automation.workflow import STAGES, WorkflowManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Scheduler automation workflow.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_task = subparsers.add_parser("new-task", help="Create a new workflow task bound to an OpenSpec change.")
    new_task.add_argument("--title", required=True, help="Task title.")
    new_task.add_argument("--request", default="", help="Raw request text.")

    subparsers.add_parser("status", help="List existing tasks with workflow state.")

    show = subparsers.add_parser("show", help="Show a task summary.")
    show.add_argument("--task", required=True, help="Task identifier.")

    advance = subparsers.add_parser("advance", help="Move a task to another stage.")
    advance.add_argument("--task", required=True, help="Task identifier.")
    advance.add_argument("--stage", required=True, choices=STAGES, help="Target stage.")

    log_cmd = subparsers.add_parser("log", help="Append an entry to the task journal.")
    log_cmd.add_argument("--task", required=True, help="Task identifier.")
    log_cmd.add_argument("--stage", required=True, choices=STAGES, help="Stage for the log entry.")
    log_cmd.add_argument("--message", required=True, help="Log message.")

    verify = subparsers.add_parser("verify", help="Run workflow verification and record the result.")
    verify.add_argument("--task", required=True, help="Task identifier.")

    review = subparsers.add_parser("review", help="Record self-review state from review.md.")
    review.add_argument("--task", required=True, help="Task identifier.")

    autopilot = subparsers.add_parser(
        "autopilot",
        help="Automatically advance a task until release readiness or a manual code-change stop point.",
    )
    autopilot.add_argument("--task", required=True, help="Task identifier.")

    complete = subparsers.add_parser("complete", help="Archive the change, commit, and push when release gates pass.")
    complete.add_argument("--task", required=True, help="Task identifier.")

    return parser


def confirm_generated_artifacts(change_name: str, artifacts: GeneratedArtifacts) -> bool:
    for filename, content in artifacts.preview_items():
        print(f"\nGenerated {filename} for {change_name}\n")
        print(content.rstrip())
        print()
    print(f"Write generated artifacts to openspec/changes/{change_name}/? [y/N] ", end="")
    response = input()
    return response.strip().lower() == "y"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "new-task":
            root = Path.cwd()
            generator = OpenSpecArtifactGenerator(root)
            manager = WorkflowManager(root, artifact_generator=generator, confirm_write=confirm_generated_artifacts)
            metadata = manager.create_task(args.title, args.request)
            print(f"Created task: {metadata.task_id} | change={metadata.change_name}")
            return 0

        manager = WorkflowManager(Path.cwd())

        if args.command == "status":
            tasks = manager.list_task_snapshots()
            if not tasks:
                print("No tasks found.")
                return 0
            for snapshot in tasks:
                state = "BLOCKED" if snapshot.blocked_reasons else "READY"
                print(
                    f"{snapshot.metadata.task_id} | {snapshot.metadata.current_stage} | "
                    f"{state} | {snapshot.metadata.change_name} | {snapshot.metadata.title}"
                )
            return 0

        if args.command == "show":
            print(manager.render_task(args.task))
            return 0

        if args.command == "advance":
            metadata = manager.advance_task(args.task, args.stage)
            print(f"{metadata.task_id} -> {metadata.current_stage}")
            return 0

        if args.command == "log":
            manager.append_log(args.task, args.stage, args.message)
            print(f"Logged message for {args.task}")
            return 0

        if args.command == "verify":
            result = manager.verify_task(args.task)
            print(f"{args.task} verification {'passed' if result.passed else 'failed'}")
            return 0 if result.passed else 1

        if args.command == "review":
            summary = manager.review_task(args.task)
            print(
                f"{args.task} review recorded | "
                f"high={summary.open_by_severity['high']} "
                f"medium={summary.open_by_severity['medium']} "
                f"low={summary.open_by_severity['low']}"
            )
            return 0

        if args.command == "autopilot":
            result = manager.autopilot_task(args.task)
            print(f"{args.task} autopilot stopped at {result.final_stage} | {result.stop_reason}")
            for action in result.actions:
                print(f"- {action}")
            return 0

        if args.command == "complete":
            result = manager.complete_task(args.task)
            print(f"{args.task} completed | archive={result.archive_path}")
            return 0
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
