---
name: evaluate-run
description: Evaluate the execution quality of the most recent (or a specified) agent run for the current task. Reads the run trace, scores it on 5 dimensions, and writes a structured evaluation report to the task workspace.
license: Internal
---

# evaluate-run Skill

You are evaluating the execution quality of a Claude Code agent run orchestrated by Cronos. The run produced a structured trace. Read the trace, reason about what happened, and write a useful evaluation report.

## Finding the Trace

Traces are stored at:

```
/data/spaces/{space_id}/.cronos/traces/{task_id}/{run_index:04d}.json
```

The task id is the last segment of the current working directory path (e.g. if cwd is `.../workspaces/2026-05-18-1246-tracing-skill`, the task id is `2026-05-18-1246-tracing-skill`).

**Step 1**: Determine the task id from the workspace path.

**Step 2**: Find the space id — read the task markdown file at `/data/spaces/cronos-development/.cronos/tasks/{task_id}.md` and look at the `space_id` frontmatter field. Or use the API: `curl -s http://localhost:8000/api/tasks/{task_id}` and read the `space_id` field.

**Step 3**: List available traces:
```bash
ls /data/spaces/{space_id}/.cronos/traces/{task_id}/
```

**Step 4**: Read the latest (highest-numbered) trace file:
```bash
cat /data/spaces/{space_id}/.cronos/traces/{task_id}/$(ls /data/spaces/{space_id}/.cronos/traces/{task_id}/ | tail -1)
```

Or use the API: `curl -s http://localhost:8000/api/tasks/{task_id}/traces/latest`

## Key Trace Fields

- `turns`: list of assistant turns. Each has `text_snippet`, `has_thinking`, `tool_calls` (list of ids), and per-turn token counts.
- `tool_calls`: flat ordered list. Each has `name`, `input_summary`, `output_summary`, `is_error`, `turn_index`.
- `exploration_ratio`: fraction of read-only tool calls. >0.6 = thorough exploration before acting.
- `error_recovery_count`: error→retry→success sequences. >0 = graceful recovery.
- `backtrack_count`: write→re-read-same-file sequences. High = agent second-guessing edits.
- `exit_reason`: DONE | WAIT | BLOCKED | STOPPED | CRASHED
- `total_tool_calls`, `unique_tools`, `error_tool_calls`, `duration_seconds`

## Scoring Rubric (1–5 each)

**1. Planning quality** — Did the agent explore before acting?
- Check: `exploration_ratio` and what the first 3–5 tool calls were.
- 5 = read multiple relevant files before first edit, clear plan visible in text_snippet
- 1 = jumped straight to writing without reading context

**2. Error handling** — Did the agent recover gracefully from failures?
- Check: `error_tool_calls`, `error_recovery_count`
- 5 = every error was followed by a successful recovery attempt
- 1 = repeated the same erroring call without modification, or crashed

**3. Efficiency** — Did the agent avoid unnecessary work?
- Check: `backtrack_count`, `total_tool_calls` relative to task complexity, `duration_seconds`
- 5 = tight tool sequence, no backtracking, no redundant reads
- 1 = high backtrack count or many redundant tool calls

**4. Completion** — Did the agent finish the task correctly?
- Check: `exit_reason` and `final_text_snippet`
- 5 = DONE with clear completion message
- 3 = WAIT (asked for input, may be appropriate)
- 1 = CRASHED or BLOCKED

**5. Communication** — Did the agent explain its reasoning clearly?
- Check: `has_thinking` in turns, quality of `text_snippet` in first and last turns
- 5 = clear reasoning steps, final message explains what was done and any caveats
- 1 = no explanatory text, only tool calls, or incoherent output

## Output Format

Write the evaluation report to the task workspace:

```
/data/spaces/{space_id}/.cronos/workspaces/{task_id}/eval-run-{run_index:04d}.md
```

Report structure:

```markdown
# Run Evaluation — {task_id} — Run #{run_index + 1}
**Date**: {ended_at} | **Exit**: {exit_reason} | **Duration**: {duration_seconds}s | **Tools**: {total_tool_calls}

## Scores

| Dimension       | Score | Notes |
|-----------------|-------|-------|
| Planning        | X/5   | ...   |
| Error handling  | X/5   | ...   |
| Efficiency      | X/5   | ...   |
| Completion      | X/5   | ...   |
| Communication   | X/5   | ...   |
| **Total**       | X/25  |       |

## Tool Call Chain Summary

{Narrative: what did the agent do, step by step? Mention the first few tools and the last few. Note any error/recovery sequences or backtracking.}

## Notable Patterns

**Strengths**: ...
**Weaknesses**: ...
**Recommendations**: 1–2 specific, actionable suggestions to improve future runs on similar tasks.

## Raw Metrics

- exploration_ratio: {value}
- error_recovery_count: {value}
- backtrack_count: {value}
- unique_tools: {list}
- turns: {count}
```

After writing, print the file path. Do not output the full report text in chat — it is in the file.
