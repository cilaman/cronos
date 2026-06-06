---
cc_version: '1.0'
agent: pipeline-architect
slug: backend-harness-tools-resolver
phase: design
status: done
confidence: 0.9
inputs_used:
- memory:project_pipeline_architect_agent
- memory:project_architecture_key_modules
- memory:project_pipeline_narrow_k_coverage
- .cronos/pipeline/backend-harness-tools-resolver/analysis-report-backend-harness-tools-resolver.md
- .cronos/pipeline/backend-harness-tools-resolver/scout-report-backend-harness-tools-resolver.md
- backend/app/worker.py
- backend/app/tools/scanner.py
- backend/app/api/tools.py
- backend/app/harnesses/brief_composer.py
- backend/app/harnesses/executor.py
- backend/app/space_storage.py
outputs_produced:
- .cronos/pipeline/backend-harness-tools-resolver/design-report-backend-harness-tools-resolver.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/worker.py
  - backend/app/tools/scanner.py
  - backend/app/api/tools.py
  - backend/app/harnesses/brief_composer.py
  - backend/app/harnesses/executor.py
  - backend/app/space_storage.py
  - backend/tests/
  excluded:
  - frontend/: backend-only feature, no UI changes
  - backend/app/harnesses/model.py: Pydantic models are out of scope per task brief
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/worker.py
  validation_command: cd backend && pytest tests/test_worker.py tests/test_harness_executor.py
    -v --override-ini="addopts="
  max_diff_lines: 120
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/tests/test_tools_resolver.py
  validation_command: cd backend && pytest tests/test_tools_resolver.py -v --override-ini="addopts="
  max_diff_lines: 350
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/tests/test_tools_resolver.py
  validation_command: cd backend && pytest tests/ --cov=app --cov-report=term-missing
    --cov-fail-under=60
  max_diff_lines: 60
  depends_on:
  - I2
risks:
- description: Naive call ordering returns a global-scope match before a same-name
    space-scope match, violating R2 (space shadows global). If the implementor scans
    agents-then-skills-then-commands-then-context for space and only on miss falls
    through to global, this is correct; if they instead build one flat list with space
    prepended and iterate, that is also correct — but mixing per-category early-return
    with global-first per category would silently break shadowing.
  severity: high
  mitigation: I1 brief requires the resolver to scan ALL space categories first (agents
    → skills → commands → context), early-return on first space match, only then scan
    global categories in the same order. I2 includes an explicit space-vs-global precedence
    test (R2) that creates same-named entries in both scopes and asserts scope=='space'
    on the returned entry.
- description: A name collision between a global agent and a global skill (or any
    two same-named entries within one scope) makes return order between categories
    load-bearing. The brief composer derives skill vs agent purely from the path substring
    'skills/' — picking the wrong entry gives the wrong brief header.
  severity: medium
  mitigation: I1 brief fixes the intra-scope scan order to agents → skills → commands
    → context (mirrors api/tools.py:166-169 list construction) so behavior is deterministic
    and documented. I2 test_agent_shadows_global_skill asserts the intra-scope ordering.
- description: _scan_context lives in backend/app/api/tools.py, not in backend/app/tools/scanner.py.
    Importing it from api/tools.py couples the worker to the API module and risks
    a circular import (api/tools.py imports stats_store; worker.py is at import-time
    used by main.py which imports the api routers).
  severity: medium
  mitigation: I1 brief requires the resolver to import _scan_context lazily INSIDE
    the resolver closure body (the same place the stub is defined). Lazy import inside
    the closure avoids any new top-of-file dependency from worker.py on app.api.*.
    The validation step runs the full worker + executor tests to flush any circular-import
    regression.
- description: Tests for the global scope cannot rely on Path.home() pointing at the
    real user home directory (the test runner has its own HOME and may contain a real
    ~/.claude tree that pollutes results).
  severity: medium
  mitigation: I2 brief requires every test that exercises global resolution to monkeypatch
    Path.home to a tmp_path subdirectory before constructing the resolver. Tests must
    NEVER read the host's real ~/.claude.
- description: The current stub _tools_resolver is a closure inside _execute_harness_run,
    so it cannot be unit-tested directly without spinning up a full harness run. Lifting
    it to a module-level helper or a Worker method changes the diff shape and risks
    accidental coverage drops elsewhere.
  severity: low
  mitigation: I1 keeps the public surface (closure inside _execute_harness_run) intact
    but extracts the resolution body into a new module-level helper `resolve_tool(claude_dir_space,
    claude_dir_global, agent_ref) -> AiToolEntry | None` in backend/app/worker.py.
    The closure becomes a thin wrapper that supplies the two dirs and delegates. I2
    tests the module-level helper directly with tmp_path .claude trees, avoiding any
    harness scaffolding.
metrics:
  tool_calls: 12
  files_read: 8
  memory_hits: 3
  iterations_planned: 3
---

## Summary

Replace the stub `_tools_resolver` closure inside `_execute_harness_run` (worker.py:642–643) with a real implementation that reuses the existing scanners and returns `AiToolEntry | None`. To make the resolver unit-testable without spinning up a harness run, lift the resolution body into a module-level helper `resolve_tool(space_claude_dir, global_claude_dir, agent_ref)`; the closure keeps the original `(space_id, agent_ref) -> AiToolEntry | None` signature, derives the two `.claude` directories from `self.space_store.spaces_dir / space_id` and `Path.home() / ".claude"`, and delegates. Skills are recognized downstream by `brief_composer._is_skill` via the `"skills/"` path substring; no changes to `brief_composer.py` or `executor.py` are needed. The plan is three iterations: resolver implementation, dedicated test file with the six required scenarios, then a coverage-floor sanity check.

## Components

### Data
- No new data model. `AiToolEntry` (backend/app/models.py:289-294) is reused unchanged; `path` substring `"skills/"` is the only discriminator the brief composer needs.

### Backend
- `backend/app/worker.py::resolve_tool` (new module-level helper): pure function that takes two `Path` objects (`space_claude_dir`, `global_claude_dir`) plus `agent_ref: str` and returns `AiToolEntry | None`. Scans space scope first (agents → skills → commands → context, early-return on first name match), then global scope in the same order. Imports `_scan_context` lazily from `app.api.tools` to avoid top-of-file coupling.
- `backend/app/worker.py::_tools_resolver` (replaces existing stub at lines 642–643): a thin closure over `self` that resolves `space_claude_dir = self.space_store.spaces_dir / space_id / ".claude"` and `global_claude_dir = Path.home() / ".claude"`, then calls `resolve_tool(...)`. Preserves the existing `(space_id: str, agent_ref: str) -> AiToolEntry | None` signature so `HarnessExecutor` wiring at executor.py:753 is untouched.
- `backend/app/harnesses/brief_composer.py` (read-only): no changes. `_is_skill` already returns `True` when the resolved entry path contains `"skills/"`.
- `backend/app/harnesses/executor.py` (read-only): no changes. The agent_entry returned by the resolver already flows unchanged into `compose_brief(node, interpolated_prompt, agent_entry)` at line 758 (R5).

### Tests
- `backend/tests/test_tools_resolver.py` (new): pytest module with at least six test cases covering R1, R2, R4, R6 acceptance criteria. Uses `tmp_path` to build fake `.claude/` trees for both space and global; monkeypatches `Path.home` so global resolution is isolated from the host environment. Tests target the module-level `resolve_tool` directly for fast, scaffolding-free coverage.

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)             | Validation                                                                              |
|-----|---------|------------|------------------------------------|-----------------------------------------------------------------------------------------|
| I1  | backend | -          | backend/app/worker.py              | cd backend && pytest tests/test_worker.py tests/test_harness_executor.py -v --override-ini="addopts=" |
| I2  | backend | I1         | backend/tests/test_tools_resolver.py | cd backend && pytest tests/test_tools_resolver.py -v --override-ini="addopts="          |
| I3  | backend | I2         | backend/tests/test_tools_resolver.py | cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=60     |

### I1 — Resolver implementation

**Brief.** Replace the two-line stub `def _tools_resolver(space_id, agent_ref): return None` at `backend/app/worker.py:642-643` with a real implementation, and add a new module-level helper `resolve_tool` at module scope in the same file.

**Required invariants:**
1. **Signature preserved.** `_tools_resolver(space_id: str, agent_ref: str) -> AiToolEntry | None` — same closure shape, same call site, same callers. `HarnessExecutor` wiring at `backend/app/harnesses/executor.py:753` is NOT modified.
2. **Module-level helper.** A pure function `def resolve_tool(space_claude_dir: Path, global_claude_dir: Path, agent_ref: str) -> AiToolEntry | None:` is added at module scope in `backend/app/worker.py` (above `class Worker`). It contains the actual scan-and-match logic so the closure becomes a 3-line delegation.
3. **Scope precedence (R2).** Space-scoped entries shadow global-scoped entries with the same name. The helper scans ALL space categories first, returns on the first name match, and only falls through to global categories when no space match exists.
4. **Intra-scope order.** Within each scope, scan in this order: agents → skills → commands → context. This mirrors the `api/tools.py:166-169` list construction order and makes same-name collisions across categories deterministic.
5. **Scanner reuse (R1).** Call `_scan_category(claude_dir, "agents", scope)`, `_scan_skills(claude_dir, scope)`, `_scan_category(claude_dir, "commands", scope, recursive=True)`, and `_scan_context(claude_dir, scope)`. Do not re-implement directory walking.
6. **Lazy import of `_scan_context`.** `_scan_context` lives in `backend/app/api/tools.py`. Import it inside the body of `resolve_tool` (not at the top of `worker.py`) to avoid a circular import with `app.api.*` modules that depend on the worker indirectly via `main.py`. `_scan_category` and `_scan_skills` may be imported at the top from `app.tools.scanner` (already a low-level module with no upward dependencies).
7. **Empty / missing-directory handling.** If `space_claude_dir` (or `global_claude_dir`) does not exist, the existing scanners already return `[]` — no extra guard needed. The helper must not raise on missing directories.
8. **Empty `agent_ref`.** When `agent_ref == ""` or `agent_ref is None`, return `None` without scanning.
9. **Space dir derivation (R3).** The closure derives `space_claude_dir = self.space_store.spaces_dir / space_id / ".claude"` (reuses the pattern already at worker.py:626) and `global_claude_dir = Path.home() / ".claude"` (matches `api/tools.py:37`). Do not introduce a new module-level constant.
10. **Diff budget.** Implementation should fit comfortably under 120 diff lines (resolver helper ~40 LOC + closure replacement ~6 LOC + 1–2 import lines).

**Acceptance criteria covered:** R1, R2, R3, R5 (verifies wiring unchanged).

**Validation.** Run the existing worker and harness-executor test suites to confirm no regression in the wider harness execution path. Coverage gate (`--cov-fail-under=60`) is deferred to I3 because narrow `-k` runs always fail the floor (per memory `feedback_pipeline_narrow_k_coverage`).

### I2 — Resolver unit tests

**Brief.** Add `backend/tests/test_tools_resolver.py` with at least six pytest cases that exercise every acceptance criterion in R1, R2, R4, R6.

**Required invariants:**
1. **Targets the module-level helper.** Tests import `resolve_tool` from `backend.app.worker` directly and call it with `tmp_path`-built `.claude` trees. No `HarnessExecutor`, no `Worker`, no harness scaffolding.
2. **Six required scenarios.**
   - `test_agent_match`: Space `.claude/agents/foo.md` exists → returns `AiToolEntry(name="foo", scope="space")` with path containing `"agents/"`.
   - `test_skill_match_directory_based`: Space `.claude/skills/bar/SKILL.md` exists → returns entry with path containing `"skills/"`; then composes a brief via `brief_composer.compose_brief(HarnessNode(...), "do work", entry)` and asserts the returned string starts with `/bar` (closes R4).
   - `test_command_match`: Space `.claude/commands/baz.md` exists → returns entry with path containing `"commands/"`.
   - `test_context_match`: Space `.claude/CONTEXT.md` exists and `agent_ref="CONTEXT"` → returns entry with `name=="CONTEXT"`.
   - `test_miss_returns_none`: No matching entry in either scope → returns `None`.
   - `test_space_shadows_global`: Both `<space>/.claude/agents/qux.md` and `<global>/.claude/agents/qux.md` exist → returned entry has `scope=="space"`. Add a sister test `test_global_match_when_no_space` confirming the global is returned when only the global exists.
3. **Test isolation for global scope.** Tests build the global tree under a `tmp_path` subdirectory and pass it as the `global_claude_dir` argument to `resolve_tool` directly. They do NOT rely on `Path.home()`. (No monkeypatching of `Path.home` is required because the module-level helper takes both dirs as explicit arguments — the closure inside `_execute_harness_run` is what reads from `Path.home()`, and that path is exercised by the broader test_harness_executor tests in I1's validation.)
4. **Brief-composer assertion (R4).** The `test_skill_match_directory_based` case MUST construct a real `HarnessNode` via the existing Pydantic constructor (mirror the pattern in `backend/tests/test_harness_brief_composer.py`) and call `compose_brief(node, "the prompt", entry)`. Assert the result startswith `"/bar"` and contains `"the prompt"`.
5. **No host filesystem dependence.** Tests must not read or assume the presence of `~/.claude` on the test runner.
6. **Pytest style.** Use `tmp_path` fixture, plain `def test_*` functions (no test classes unless mirroring existing convention), no async (the resolver is sync).
7. **Diff budget.** Test file targets ~200–300 LOC including helper setup.

**Acceptance criteria covered:** R1, R2, R4, R6.

**Validation.** `cd backend && pytest tests/test_tools_resolver.py -v --override-ini="addopts="` — must report all new tests pass; `--override-ini` strips the project-level `--cov-fail-under=60` so a narrow file-scoped run does not fail the coverage gate (per memory `feedback_pipeline_narrow_k_coverage`). The coverage floor is re-checked in I3.

### I3 — Full-suite coverage sanity check

**Brief.** Re-run the full backend pytest suite with coverage to confirm the 60% floor still holds after I1 + I2.

**Required invariants:**
1. **No code changes.** I3 is a verification-only iteration. If the suite fails or coverage dips below 60%, the implementor adds targeted additional tests to `backend/tests/test_tools_resolver.py` (or augments existing tests) until the gate passes. No production code is touched in I3.
2. **Validation gate.** The full-suite command `cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=60` exits 0.
3. **If the floor is missed** by less than ~2 percentage points, add one or two additional resolver-helper edge-case tests (e.g. empty `agent_ref`, missing space dir, missing global dir, non-string `agent_ref`). Avoid adding tests unrelated to the resolver — that is scope creep.
4. **Diff budget.** ≤60 lines; expected to be 0 if I1 + I2 already keep coverage above the floor.

**Acceptance criteria covered:** R6 (coverage ≥60%).

**Validation.** The full suite passes with the coverage floor enforced.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Naive scope handling returns a global entry before a same-name space entry (violates R2). | high | I1 brief mandates: scan ALL space categories before ANY global category; I2 includes a dedicated `test_space_shadows_global` case. |
| Intra-scope category collision (e.g. same name as agent and skill within one scope) is non-deterministic. | medium | I1 fixes scan order to agents → skills → commands → context (mirrors api/tools.py:166-169). |
| Importing `_scan_context` from `app.api.tools` at module top of `worker.py` risks circular import. | medium | I1 brief requires lazy import of `_scan_context` inside the `resolve_tool` body. |
| Test cases that exercise global scope might read the host's real `~/.claude` tree and produce flaky results. | medium | I2 brief requires tests to pass an explicit `global_claude_dir=tmp_path/...` to the helper rather than relying on `Path.home()`. |
| The stub is a closure, hard to test directly without harness scaffolding — lifting to a module helper changes the diff shape. | low | I1 extracts the body into a module-level pure function `resolve_tool`; the closure remains a 3-line wrapper so the harness call site is untouched. |

## Assumptions

- The `_tools_resolver` closure inside `_execute_harness_run` keeps its original `(space_id, agent_ref) -> AiToolEntry | None` signature — no callers besides `HarnessExecutor.__init__` need to change.
- `_scan_context` is safe to import lazily from `backend/app/api/tools.py` (the module is loaded eagerly by `main.py` during FastAPI startup so by the time the resolver runs at harness execution time, the module is already imported and the lazy import is cheap).
- The existing `test_harness_brief_composer.py` constructs `HarnessNode` via the Pydantic constructor in a stable way that I2's tests can mirror — the implementor should read that test file before writing the new one.
- No category-prefix disambiguation (`"skill:foo"`, `"agent:bar"`) is needed in this slice — analyst marked this deferred.
- Case-sensitive matching keeps parity with the scanners — analyst marked this resolved.

## Open questions

- None. The analyst report enumerated all open questions and resolved them; the design proceeds directly to implementation.

## Next consumer brief

The implementor should read the YAML `iterations[]` array first, then this section. Key cross-iteration invariants not captured in YAML:

1. **Module-level helper name and signature are load-bearing across iterations.** I1 must export `resolve_tool(space_claude_dir: Path, global_claude_dir: Path, agent_ref: str) -> AiToolEntry | None` from `backend/app/worker.py` exactly as named — I2 imports it by that name. If the implementor changes the name or signature in I1, I2's tests will fail at import.
2. **Skill detection is path-based, not category-based.** `brief_composer._is_skill` checks for `"skills/"` substring in `AiToolEntry.path`. The resolver must return entries produced by `_scan_skills` (which builds paths like `.claude/skills/<name>/SKILL.md`) unmodified — do NOT post-process or rewrite the `path` field.
3. **Intra-scope scan order is documented as part of the contract.** Agents → skills → commands → context. This is asserted by the `test_agent_shadows_global_skill` sister test in I2.
4. **The `executor.py` and `brief_composer.py` files are read-only across all three iterations.** Touching them is out of scope and would expand the diff beyond what the design plan permits.
5. **Coverage floor is checked in I3, not I2.** I2's validation command uses `--override-ini="addopts="` to strip the project-level `--cov-fail-under=60` so a narrow file-scoped run does not falsely fail (per the project memory on narrow `-k` coverage gates). The floor is enforced in I3 via the full-suite run.
