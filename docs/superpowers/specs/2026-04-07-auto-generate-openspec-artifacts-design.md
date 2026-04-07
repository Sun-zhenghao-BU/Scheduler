# Auto Generate OpenSpec Artifacts Design

## Goal

Generate `proposal.md`, `design.md`, `specs/.../spec.md`, and `tasks.md` automatically during `new-task` by using the local OpenSpec template system, preview the generated content in the terminal, and only write the files after explicit user confirmation.

## Scope

This change covers:

- an OpenSpec-template-backed artifact generator
- `new-task` orchestration updates to call the generator automatically
- terminal preview plus confirmation before writing generated artifacts
- failure handling for missing templates, invalid generated output, and rejected confirmation
- tests for the generation and confirmation flow

## Out Of Scope

- web-based preview
- remote AI providers
- automatic archival or approval of generated artifacts
- changing the existing release/review/fix workflow

## User Flow

1. User runs `new-task --title ... --request ...`
2. The workflow manager creates the local task and bound OpenSpec change
3. The system resolves OpenSpec template paths through the local CLI
4. The system generates draft artifacts:
   - proposal
   - design
   - spec
   - tasks
5. The terminal prints the generated content in a readable preview
6. The user confirms whether the generated artifacts should be written
7. If confirmed, the files are written into `openspec/changes/<change-name>/`
8. If rejected, the task and change remain, but the artifact files stay untouched

## Architecture

### Artifact Generator

Introduce a generator interface so the workflow code depends on a simple contract rather than directly on CLI plumbing.

The first implementation is `OpenSpecArtifactGenerator`, which:

- resolves template paths with `openspec templates --json`
- validates the required template files exist
- builds deterministic initial content from the task title, request text, and change name
- returns generated proposal, design, spec, and tasks artifacts

### Workflow Integration

`WorkflowManager.create_task()` remains the main entrypoint, but the generation flow should be moved into a dedicated helper so task creation logic does not become monolithic.

The creation flow becomes:

1. create local task directory
2. create bound OpenSpec change
3. call artifact generator
4. render preview
5. request confirmation
6. write artifacts if approved
7. record what happened in the journal

### CLI Integration

`new-task` remains the user-facing command. The confirmation prompt is terminal-based and blocks until the user responds.

Expected prompt:

`Write generated artifacts to openspec/changes/<change-name>/? [y/N]`

## Preview Format

The preview should be simple and scannable:

- a heading per artifact
- full content shown inline in the terminal
- a clear confirmation prompt after all sections are displayed

No partial writes should happen before confirmation.

## Error Handling

### Template Resolution Failure

Fail immediately and preserve the created task/change so the user can retry or fill files manually.

### Invalid Generated Output

If any required artifact is missing or empty, treat the generation as failed and do not write files.

### User Rejects Confirmation

Leave the task and change in place, log that generation was rejected, and return a clear message.

## File Changes

Expected additions or changes:

- `src/scheduler_automation/artifact_generation.py`
- `src/scheduler_automation/workflow.py`
- `src/scheduler_automation/cli.py`
- `tests/test_workflow.py`
- `README.md`

## Testing Strategy

Add tests for:

- successful artifact generation path
- preview confirmation accepted
- preview confirmation rejected
- invalid generator output
- `new-task` behavior when generation fails

Mock the OpenSpec-template-facing layer so tests stay deterministic and offline.

## Risks

- deterministic drafts may still need manual refinement
- printing large previews may be noisy in the terminal
- a failed generation after task creation leaves partially initialized state, which must be explained clearly
