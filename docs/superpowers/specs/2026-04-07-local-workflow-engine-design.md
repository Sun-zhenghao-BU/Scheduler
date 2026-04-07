# Local Workflow Engine Design

## Goal

Build a local workflow engine that drives each repository change through an OpenSpec-backed delivery loop:

1. create one OpenSpec change per implementation
2. bind that change to one local task workspace
3. track progress through `intake -> spec -> implement -> review -> fix -> release`
4. require self-review and bug-fix loops before release
5. archive the change only after release gates pass
6. commit and push automatically after archive succeeds

## Scope

This design covers the first complete local workflow engine milestone:

- automatic OpenSpec change creation during task creation
- local task metadata enriched with OpenSpec linkage and progress state
- stage gating for the main lifecycle
- verification, review, and completion commands
- release gating based on OpenSpec task completion, review findings, and verification
- README refresh to describe the bilingual workflow

## Out Of Scope

- generating OpenSpec proposal/design/tasks content automatically
- multi-user coordination
- remote deployment orchestration beyond `git push`
- a dedicated interactive `fix` subcommand

## Architecture

The workflow stays centered on `tasks/<task-id>/` as the durable local execution record. Each task binds to exactly one OpenSpec change through metadata.

`WorkflowManager` becomes the orchestration layer for:

- creating task workspaces and OpenSpec changes
- parsing OpenSpec artifacts and task checkbox progress
- validating whether a stage transition is allowed
- recording verification and review evidence
- completing the release flow by archiving the change and driving git commit/push

The CLI remains thin. Each command delegates to `WorkflowManager` and prints a concise operational summary.

## Data Model Changes

`metadata.json` is extended with:

- `change_name`
- `change_path`
- `blocked`
- `blocked_reasons`
- `last_verified_at`
- `last_reviewed_at`
- `ready_for_release`

The task workspace keeps these files:

- `request.md`: original request
- `spec.md`: summary of the bound OpenSpec change and local scope notes
- `implementation.md`: implementation notes and verification trail
- `review.md`: structured findings with severity and status
- `fixes.md`: fix notes mapped to findings
- `release.md`: final release checklist and delivery notes
- `journal.md`: timestamped timeline

## Stage Gates

### intake -> spec

- bound OpenSpec change exists
- local request content exists

### spec -> implement

- OpenSpec change contains `proposal.md`, `design.md`, and `tasks.md`
- OpenSpec tasks file contains at least one unchecked task item
- local `spec.md` has a populated OpenSpec summary section

### implement -> review

- implementation notes include at least one non-placeholder entry
- verification has been run at least once

### review -> fix

- at least one open finding exists

### review -> release

- all OpenSpec tasks are complete
- no open `high` severity findings remain
- most recent verification passed

### fix -> review

- fixes file contains a non-placeholder update
- verification has been run again after fixes

### release -> complete

- release notes are populated
- release gate still passes at execution time

## Review And Fix Loop

Review findings are stored in `review.md` as a predictable checklist format. Each finding contains:

- finding id
- severity: `high`, `medium`, or `low`
- status: `open` or `resolved`
- summary

`high` findings block release. `medium` and `low` findings remain visible but do not block the transition.

## Verification

The first workflow milestone uses one configured verification command:

`$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`

The `verify` command records:

- timestamp
- command
- pass/fail state
- command output summary

## Completion Flow

`complete --task <id>` performs a final release gate check and then:

1. archives the bound OpenSpec change into `openspec/changes/archive/YYYY-MM-DD-<change-name>/`
2. writes release notes with archive and git results
3. commits repository changes with a deterministic message tied to the task and change
4. pushes to the current remote branch

If any step fails, the command stops and returns the error without claiming completion.

## Testing Strategy

- extend unit tests around `WorkflowManager`
- stub external commands through an injectable command runner
- test success and failure paths for:
  - task creation with change binding
  - stage gating
  - review finding parsing
  - verification recording
  - completion gating and archive/git orchestration

## Risks

- OpenSpec CLI output may vary; parsing must stay defensive
- git push can fail due to auth or remote state; completion must surface that clearly
- markdown parsing must distinguish placeholders from real content without being brittle
