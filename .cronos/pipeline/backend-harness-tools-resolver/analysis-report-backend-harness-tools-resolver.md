---
cc_version: '1.0'
agent: pipeline-analyst
slug: backend-harness-tools-resolver
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:arc6-harness-executor
- .cronos/pipeline/backend-harness-tools-resolver/scout-report-backend-harness-tools-resolver.md
- backend/app/worker.py
- backend/app/tools/scanner.py
- backend/app/api/tools.py
- backend/app/harnesses/brief_composer.py
- backend/app/harnesses/executor.py
outputs_produced:
- .cronos/pipeline/backend-harness-tools-resolver/analysis-report-backend-harness-tools-resolver.md
blockers: []
next_consumer: design
request: 'Implement the harness runtime tools-resolver so agent and skill nodes resolve
  to a real `AiToolEntry`, and briefs are composed with the correct agent header /
  skill prefix.

  Acceptance criteria: 1. **Real resolver.** Replace the stub `_tools_resolver` at
  `backend/app/worker.py:470-471` (signature `(space_id: str, agent_ref: str) -> AiToolEntry
  | None`) with a real implementation. REUSE the existing scanners — do not re-implement
  scanning: `_scan_category` and `_scan_skills` in `backend/app/tools/scanner.py`,
  and `_scan_context` in `backend/app/api/tools.py`. Resolve by matching `agent_ref`
  against agent, skill, command and context entries, searching the space-scoped `.claude`
  directory and the global scope. Return `None` on no match. 2. **Wiring.** The resolver
  is already passed into `HarnessExecutor` and called at `backend/app/harnesses/executor.py:753`;
  confirm the resolved `agent_entry` flows into `compose_brief` so the agent header
  is added. 3. **Skill prefix.** When `agent_ref` resolves to a skill (path under
  `.claude/skills/`), the resolved entry must let `brief_composer._is_skill` detect
  it so the brief is prefixed with `/<skill-name>` (see `backend/app/harnesses/brief_composer.py`).
  Verify agent vs skill vs plain-ref behaviour. 4. **Tests.** Add pytest covering:
  agent match, skill match (asserts `/` prefix in composed brief), command/context
  match, miss → `None`, and space-vs-global scoping. Keep the 60% coverage floor:
  `cd backend && pytest tests/ --cov=app --cov-report=term-missing`.'
has_ui: false
coverage_summary:
  searched:
  - backend/app/worker.py
  - backend/app/tools/scanner.py
  - backend/app/api/tools.py
  - backend/app/harnesses/brief_composer.py
  - backend/app/harnesses/executor.py
  excluded:
  - frontend/: backend-only feature, no UI changes required
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: The `_tools_resolver` function in `backend/app/worker.py` is replaced
    with a real implementation that scans all four tool categories (agents, skills,
    commands, context) and returns an `AiToolEntry | None`.
  acceptance_criteria:
  - Given a `space_id` and `agent_ref`, when `_tools_resolver(space_id, agent_ref)`
    is called, then it returns a matching `AiToolEntry` if one exists in any scanned
    category.
  - The implementation calls `_scan_category(..., 'agents', ...)`, `_scan_skills(...)`,
    `_scan_category(..., 'commands', ..., recursive=True)`, and `_scan_context(...)`
    to gather candidates.
  - When no tool entry matches `agent_ref`, the function returns `None`.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: The resolver searches space-scoped tools (`.claude/` inside space directory)
    before global-scoped tools (`~/.claude/`), returning the first match — space entries
    shadow globals with the same name.
  acceptance_criteria:
  - Given both a space-scoped and a global-scoped tool share the same name, when `_tools_resolver`
    is called with that name, then the space-scoped entry is returned.
  - When no space-scoped match exists but a global match does, the global entry is
    returned.
  - The `scope` field of the returned `AiToolEntry` reflects the actual source (`'space'`
    or `'global'`).
  verifying_phase: test
  confidence: 0.92
- requirement_id: R3
  statement: The resolver obtains the space directory by reading `self.space_store.spaces_dir
    / space_id` (the pattern already used at `worker.py:626`), then derives `.claude/`
    subdirectory from it.
  acceptance_criteria:
  - The implementation does not introduce a new module-level constant for the spaces
    directory — it reuses the already-available `self.space_store.spaces_dir` via
    closure over the `Worker` instance.
  - The global `.claude/` directory is derived as `Path.home() / '.claude'` — consistent
    with `api/tools.py:37`.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R4
  statement: When `agent_ref` resolves to a skill entry (path contains `'skills/'`),
    `brief_composer._is_skill()` returns `True` and `compose_brief()` prefixes the
    brief with `/<skill-name>`.
  acceptance_criteria:
  - Given an `agent_ref` matching a skill directory-based entry (path like `.claude/skills/foo/SKILL.md`),
    when `compose_brief(node, prompt, agent_entry)` is called, then the result starts
    with `/foo`.
  - 'Given an `agent_ref` matching an agent entry (path like `.claude/agents/bar.md`),
    when `compose_brief` is called, then the result starts with `Agent: bar`.'
  - 'Given `agent_entry=None`, the brief contains only `Agent: <agent_ref>` header
    (raw ref) and the prompt.'
  verifying_phase: test
  confidence: 0.95
- requirement_id: R5
  statement: 'The wiring in `executor.py` is confirmed correct: the `agent_entry`
    returned by `self.tools_resolver(space.id, agent_ref)` at line 753 flows unchanged
    into `compose_brief(node, interpolated_prompt, agent_entry)` at line 758.'
  acceptance_criteria:
  - No intermediate transformation of `agent_entry` occurs between resolver call and
    `compose_brief` invocation.
  - If `tools_resolver` raises, the exception is caught and `agent_entry` remains
    `None` (existing try/except at executor.py:754).
  verifying_phase: review
  confidence: 0.98
- requirement_id: R6
  statement: 'Pytest tests are added covering: agent match, skill match (asserts `/<name>`
    prefix in composed brief), command match, context match, miss → `None`, and space-vs-global
    scope precedence.'
  acceptance_criteria:
  - A test file `tests/test_tools_resolver.py` (or equivalent) exists with at least
    6 distinct test cases matching the specified scenarios.
  - All new tests pass and the overall coverage remains at or above 60% (`--cov-fail-under=60`).
  - Tests use temporary directories (e.g. `tmp_path`) to create mock `.claude/` trees
    — no live filesystem dependency.
  verifying_phase: test
  confidence: 0.9
metrics:
  tool_calls: 9
  files_read: 6
  memory_hits: 1
---

## Summary

The harness runtime needs a working tools-resolver to replace the stub `return None` at `backend/app/worker.py:642-643`. The resolver maps an `agent_ref` string to an `AiToolEntry` by scanning space-local and global `.claude/` directories using existing scanner functions (`_scan_category`, `_scan_skills`, `_scan_context`). The executor wiring is already in place — `agent_entry` flows directly into `compose_brief()` — so only the resolver body and its tests need to be written. Skills are identified by the `"skills/"` substring in the `AiToolEntry.path` and automatically receive the `/<skill-name>` brief prefix.

## Scope

### In scope
- Replace stub `_tools_resolver` in `backend/app/worker.py` with a real implementation
- Reuse `_scan_category`, `_scan_skills` from `backend/app/tools/scanner.py` and `_scan_context` from `backend/app/api/tools.py`
- Space-before-global scope precedence for name matching
- Derive space directory from `self.space_store.spaces_dir / space_id` (closure over Worker instance)
- Add pytest tests for all six required scenarios
- Confirm wiring: executor passes resolver result unchanged into `compose_brief`

### Out of scope
- Modifying `backend/app/harnesses/executor.py` — wiring is already correct
- Modifying `backend/app/harnesses/brief_composer.py` — `_is_skill` and `compose_brief` are already correct
- Modifying Pydantic models (`AiToolEntry`, harness models)
- Frontend changes
- Caching or performance optimization of the resolver
- Case-insensitive matching (scanners are case-sensitive; keep consistent)

### Deferred
- Category-prefixed `agent_ref` (e.g. `skill:foo` or `agent:bar`) — not in the request; plain name matching is sufficient for now
- Resolver telemetry / hit-rate tracking
- Multi-space resolution or cross-space tool shadowing

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Replace stub resolver with real multi-category scanner using existing `_scan_*` functions |
| R2 | Space-scoped tools shadow global-scoped tools with the same name |
| R3 | Derive space directory from `self.space_store.spaces_dir / space_id` (closure, no new constant) |
| R4 | Skill entries produce `/<skill-name>` brief prefix via existing `_is_skill` + `compose_brief` |
| R5 | Confirm executor wiring: `agent_entry` passes unchanged from resolver to `compose_brief` |
| R6 | Add pytest with 6 scenarios: agent, skill (prefix assert), command, context, miss, scope precedence |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — Resolver scans agents + skills + commands + context; returns matching entry or `None`
- R2 — Space-scoped entry wins over identically-named global entry; global used only when no space match
- R3 — Space dir derived from `space_store.spaces_dir / space_id`; global dir is `Path.home() / ".claude"`
- R4 — Skill path triggers `_is_skill` → brief starts with `/<name>`; agent path gives `Agent: <name>`; `None` falls back to raw `agent_ref`
- R5 — No transformation between resolver return value and `compose_brief` call; existing try/except preserves `None` on exception
- R6 — `tests/test_tools_resolver.py` with ≥6 test cases; all pass; coverage ≥60%

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Stub replaced with real multi-category scanner implementation |
| R2 | test | Space-scoped tools shadow global tools with matching name |
| R3 | review | Space dir derived via Worker's `space_store.spaces_dir`; global dir via `Path.home()` |
| R4 | test | Skill entries trigger `/<name>` prefix; agent entries give `Agent: <name>` |
| R5 | review | Executor wiring confirmed correct — no intermediate transformation |
| R6 | test | Test file with 6 scenarios covering all required cases |

## Assumptions

- `has_ui=false` rationale: the request is exclusively backend, touching `worker.py` and adding test files only; no frontend routes, components, or API contracts are modified.
- The `_tools_resolver` closure over `self` (the `Worker` instance) is the right pattern because `self.space_store.spaces_dir` is available at the call site (`worker.py:616-626` confirms `self.space_store` is not `None` before `_tools_resolver` is defined in the same function body).
- The stub is at line 642-643 in current main-branch code (scout found it at 642-643; the task brief says 470-471, which was an older line number — using the actual current position confirmed by code read).
- The `GLOBAL_CLAUDE_DIR = Path.home() / ".claude"` pattern from `api/tools.py:37` is the canonical way to find global tools; the resolver should replicate this locally rather than importing the module-level constant.
- No category-prefix disambiguation is needed: the request says to match by `agent_ref` name across all categories.
- The `_scan_context` function lives in `backend/app/api/tools.py`, not in `backend/app/tools/scanner.py`; the implementation must import it from there.

## Open questions

- None. All scout open questions are resolved: case-sensitivity keeps existing behavior; space-wins-global is confirmed by the pattern in `api/tools.py:129-174`; performance is not a concern for interactive harness execution.

## Next consumer brief

The **design agent** should read `traceability[]` and `## Scope` first.

Key design decision points:
1. **Closure vs module-level function**: The resolver is currently defined as a nested function inside `_execute_harness_run` (worker.py:642). The real implementation should remain a closure over `self` (Worker instance) to access `self.space_store.spaces_dir` — no need to refactor to a class method or module-level helper.
2. **Import placement**: `_scan_category` and `_scan_skills` come from `backend/app/tools/scanner.py`; `_scan_context` comes from `backend/app/api/tools.py`. Both are already in the backend package. Use local imports inside the function body or move to top-of-file — the design agent should decide which is cleaner given existing import style at the top of `worker.py`.
3. **Iteration order for matching**: scan order within a scope should be: agents → skills → commands → context (mirrors `api/tools.py` list construction order). Return on first name match.
4. **Test isolation**: R6 tests should use `tmp_path` (pytest fixture) to build fake `.claude/` trees; the resolver must accept an override for the global `.claude/` dir path (or be tested by monkeypatching `Path.home()`) — the design agent should pick the cleanest seam.
5. No open blockers; design agent can proceed directly to an iteration plan.
