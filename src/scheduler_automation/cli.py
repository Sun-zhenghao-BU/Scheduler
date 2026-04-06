from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from scheduler_automation.workflow import STAGES, WorkflowManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Scheduler automation workflow.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_task = subparsers.add_parser("new-task", help="Create a new workflow task.")
    new_task.add_argument("--title", required=True, help="Task title.")
    new_task.add_argument("--request", default="", help="Raw request text.")

    subparsers.add_parser("status", help="List existing tasks.")

    show = subparsers.add_parser("show", help="Show a task summary.")
    show.add_argument("--task", required=True, help="Task identifier.")

    advance = subparsers.add_parser("advance", help="Move a task to another stage.")
    advance.add_argument("--task", required=True, help="Task identifier.")
    advance.add_argument("--stage", required=True, choices=STAGES, help="Target stage.")

    log_cmd = subparsers.add_parser("log", help="Append an entry to the task journal.")
    log_cmd.add_argument("--task", required=True, help="Task identifier.")
    log_cmd.add_argument("--stage", required=True, choices=STAGES, help="Stage for the log entry.")
    log_cmd.add_argument("--message", required=True, help="Log message.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manager = WorkflowManager(Path.cwd())

    if args.command == "new-task":
        metadata = manager.create_task(args.title, args.request)
        print(f"Created task: {metadata.task_id}")
        return 0

    if args.command == "status":
        tasks = manager.list_tasks()
        if not tasks:
            print("No tasks found.")
            return 0
        for task in tasks:
            print(f"{task.task_id} | {task.current_stage} | {task.title}")
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

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
