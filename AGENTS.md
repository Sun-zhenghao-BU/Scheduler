# AGENTS.md

## Execution Policy

- Default workflow mode is **branch-based**, not git worktree-based.
- For each new product task:
  1. sync `main`
  2. create a dedicated feature branch from `main`
  3. implement and verify only on that branch
  4. merge back to root branch through normal review/PR flow
- Keep test/demo experiments isolated to dedicated test branches.

## Timezone Policy

- All scheduler timestamps must use `Asia/Shanghai` (`+08:00`).
- Timeline and persisted workflow metadata should never use `UTC Z` format.

## Dashboard UX Policy

- Left sidebar lists all tasks, grouped by running/completed.
- Main panel shows selected task detail.
- Stage status should be visual and flow-like with clear current-state highlighting.

