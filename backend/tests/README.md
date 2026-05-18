# Cronos Test Suite

This directory contains the pytest test suite for the Cronos backend.

## Running the tests

```bash
cd backend
pip install -e ".[dev]"
pytest
```

## Task-level test trigger pattern

After an implementation task completes, `test-architect` can be invoked as a
follow-up task to exercise the code that was just written.

### How it works

1. An implementation task runs and completes (state → `done`).
2. A new Cronos task is created for `test-architect` with `scope: task` in the
   brief, referencing the completed task.
3. `test-architect` reads the implementation, identifies gaps, writes new
   tests, runs them via the `tester` sub-agent, and POSTs a `TestReport` to
   `/api/spaces/{space_id}/test-reports`.

### Required fields in the task brief

```
space_id: <space where the implementation task lives>
task_id:  <ID of the completed implementation task>
scope:    task
```

Pass these under a `## Test context` heading so `test-architect` picks them up
without ambiguity.

### Example task brief template

```markdown
## Goal
Run the test suite for the changes introduced by task <task_id>.

## Test context
space_id: my-space
task_id:  2026-05-18-1234-implement-something
scope:    task

## Acceptance criteria
- All existing tests still pass.
- New tests cover the public surface of the changed modules.
- A TestReport is posted to the API on completion.
```

### What test-architect does in task-level mode

| Step | Action |
|------|--------|
| 1 | Reads the task workspace to identify changed files |
| 2 | Checks existing test coverage for those modules |
| 3 | Writes new tests targeting uncovered paths |
| 4 | Spawns the `tester` agent to run `pytest` |
| 5 | Parses the JSON report and POSTs it to `/api/spaces/{space_id}/test-reports` |
| 6 | Transitions its own task to `done` |

### Wiring this into your workflow

You can create the follow-up task programmatically after an implementation task
completes, or include the brief above as a template in your project's
`CLAUDE.md` under a `## Post-implementation testing` section.
