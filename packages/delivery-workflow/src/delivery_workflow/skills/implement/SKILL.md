---
name: implement
description: Method for executing one design iteration — scope-boundary discipline, scope-escape detection, validation_command execution, diff-line budget enforcement, and recon invocation pattern. Loaded by the implementor agent.
---

# implement

How to execute one design iteration. The `implementor` agent owns the role and the hard rules; this skill owns the method.

## 0. Recon pass
Before reading any files, invoke scout for a focused map of the iteration's scope:
```
result = Agent("scout", brief="<one-sentence question about the files/APIs in this iteration's scope_files[]>")
# Use result as transient grounding context ONLY — do not add to artifact_paths
# Emit telemetry: telemetry.emit({tokens: ..., usd: ..., seconds: ...})
```
This is granted by `recon: on` in the workflow node; do NOT add `Agent` to the agent's `tools` list.
See `packages/delivery-workflow/recon/README.md` for the full isolation contract.

## 1. Memory-first preflight
Scan injected memory before reading any file. Naming conventions, prior bugs, security constraints, and architectural standards are binding.

## 2. Read the design
From the design artifact, extract the assigned iteration entry:
- `scope_files[]` — your hard boundary
- `depends_on[]` — prerequisite iterations (their changes are already committed)
- `validation_command` — what you must run
- `max_diff_lines` — your size budget

## 3. Scope boundary discipline
Before writing a single line:
- List every file you plan to touch.
- Verify each file is in `scope_files[]`.
- **Scope escape** = touching a file not in the list. Stop immediately. Surface the gap: either the design's `scope_files[]` is wrong (→ open question; do NOT write) or you have found a broader change (→ same).

## 4. Implement
Write the changes file by file. Prefer minimal diffs — satisfy the iteration's validation_command without adding scope. Do not refactor unrelated code, add error handling for impossible cases, or introduce abstractions beyond what the iteration requires.

## 5. Run the validation_command
Run the iteration's `validation_command` verbatim. Capture exit code and output.
- Exit 0 → `validation_command_passed: true`.
- Non-zero → do NOT set passed to true. Record the failure in `open_questions`; include the output snippet.

## 6. Diff-line budget check
Count `diff_lines_added` and `diff_lines_removed` (`git diff --stat` or line counts). If the total exceeds `max_diff_lines`:
- Do not abort silently — surface the overage as an open question.
- The gate may still accept the diff; that is the harness's decision, not yours.

## 7. Write the implementation artifact
Body sections:
- **Summary** — ≤ 3 sentences: what you implemented, the validation result, any scope or budget notes.
- **Files changed** — one bullet per file with a line-count delta.
- **Validation output** — the validation_command's stdout/stderr (truncated to ≤ 500 chars).
- **Open questions** — any blockers, scope escapes, or budget overruns.
