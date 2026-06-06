---
cc_version: '1.0'
agent: pipeline-architect
slug: featurefix-worker-decompose
phase: design
status: done
confidence: 0.82
inputs_used:
- memory:project_arc_features_fixes_board_setup
- memory:project_s1_data_model_impl
- memory:project_s2_api_impl
- memory:project_architecture_key_modules
- memory:project_goal_workflow
- memory:project_git_rootgoal_standard
- memory:feedback_pipeline_narrow_k_coverage
- memory:observation_worktree_main_vs_workspace
- .cronos/pipeline/featurefix-worker-decompose/analysis-report-featurefix-worker-decompose.md
- .cronos/pipeline/featurefix-worker-decompose/scout-report-featurefix-worker-decompose.md
- backend/app/worker.py
- backend/app/goal_sync.py
- backend/app/git_ops.py
- backend/app/feature_hooks.py
- backend/app/feature_state.py
- backend/app/storage.py
- backend/app/api/tasks.py
outputs_produced:
- .cronos/pipeline/featurefix-worker-decompose/design-report-featurefix-worker-decompose.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/worker.py
  - backend/app/goal_sync.py
  - backend/app/git_ops.py
  - backend/app/feature_hooks.py
  - backend/app/feature_state.py
  - backend/app/api/tasks.py
  excluded:
  - 'frontend/: backend-only feature, has_ui=false'
  - 'deploy/: no deployment changes'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/git_ops.py
  - backend/tests/test_git_ops_branch_exists.py
  validation_command: cd backend && pytest tests/test_git_ops_branch_exists.py -v
    --override-ini="addopts="
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/feature_sync.py
  - backend/tests/test_feature_sync_resolution.py
  validation_command: cd backend && pytest tests/test_feature_sync_resolution.py -v
    --override-ini="addopts="
  max_diff_lines: 250
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - backend/app/feature_sync.py
  - backend/tests/test_feature_sync_waiting_resume.py
  validation_command: cd backend && pytest tests/test_feature_sync_waiting_resume.py
    -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I2
- id: I4
  type: backend
  scope_files:
  - backend/app/feature_sync.py
  - backend/tests/test_feature_sync_done_detection.py
  validation_command: cd backend && pytest tests/test_feature_sync_done_detection.py
    -v --override-ini="addopts="
  max_diff_lines: 350
  depends_on:
  - I1
  - I3
- id: I5
  type: backend
  scope_files:
  - backend/app/feature_hooks.py
  - backend/tests/test_feature_hooks_enqueue.py
  validation_command: cd backend && pytest tests/test_feature_hooks_enqueue.py -v
    --override-ini="addopts="
  max_diff_lines: 200
  depends_on: []
- id: I6
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_worker_run_one_branching.py
  validation_command: cd backend && pytest tests/test_worker_run_one_branching.py
    -v --override-ini="addopts="
  max_diff_lines: 300
  depends_on:
  - I5
- id: I7
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_worker_run_feature_decompose.py
  validation_command: cd backend && pytest tests/test_worker_run_feature_decompose.py
    -v --override-ini="addopts="
  max_diff_lines: 500
  depends_on:
  - I6
- id: I8
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/app/api/tasks.py
  - backend/tests/test_feature_sync_integration.py
  validation_command: cd backend && pytest tests/test_feature_sync_integration.py
    -v --override-ini="addopts="
  max_diff_lines: 250
  depends_on:
  - I4
  - I7
- id: I9
  type: backend
  scope_files:
  - .claude/skills/feature-decompose/SKILL.md
  - .claude/skills/feature-decompose/decompose.md
  validation_command: python -c "import pathlib; p = pathlib.Path('.claude/skills/feature-decompose/SKILL.md');
    assert p.exists() and 'realizes' in p.read_text(), 'skill missing or lacks realizes
    contract'"
  max_diff_lines: 300
  depends_on: []
- id: I10
  type: backend
  scope_files:
  - backend/tests/test_feature_decompose_e2e.py
  validation_command: cd backend && pytest tests/test_feature_decompose_e2e.py -v
    --override-ini="addopts="
  max_diff_lines: 350
  depends_on:
  - I8
  - I9
risks:
- description: feature_sync.propagate_to_feature is called from _finalize AFTER goal_sync.propagate_to_parent.
    If goal_sync re-enqueues the parent goal (causing _run_goal to run synchronously
    in the same tick), feature_sync may observe a stale child state and miss the WAITING→PLANNED
    or DONE transition.
  severity: high
  mitigation: I8 wires feature_sync STRICTLY after goal_sync inside the same try/except
    in worker._finalize so ordering is deterministic; the propagate function reads
    task state via store.get() at call time (not cached); the _finalize integration
    test in I8 exercises a child→DONE chain and asserts feature_state transitions
    to DONE in the same finalize cycle.
- description: Race between the decomposition agent's POST /tasks (creating the realizing
    goal) and propagate_to_feature firing from the child goal's own _finalize. If
    the realizing goal's set_realizes call races with the first child's terminal transition,
    done-detection could fire before realizes is set and short-circuit to DONE with
    zero realizing items.
  severity: high
  mitigation: I2/I4 design propagate_to_feature with an explicit zero-items guard
    — if realizing_items(feature_id) returns an empty list, the done-detection path
    is skipped entirely (cannot transition PLANNED→DONE on an empty set). I9 specifies
    that the decomposition skill MUST call set_realizes on the root goal BEFORE creating
    any child tasks, so the realizes link is established prior to any child being
    enqueued.
- description: branch_exists_on_origin requires a prior `git fetch origin` to be accurate.
    If fetch is skipped or fails, a merged-and-deleted branch may still appear to
    exist locally, blocking PLANNED→DONE indefinitely.
  severity: medium
  mitigation: I4 places fetch_origin INSIDE feature_sync's done-detection path immediately
    before branch_exists_on_origin, wrapped in try/except; on fetch failure, log and
    skip the DONE transition (stay PLANNED — safe default, will retry next time a
    realizing item finishes). Test in I4 mocks fetch_origin failure and asserts feature
    stays PLANNED.
- description: gh CLI may not be installed or authenticated when feature transitions
    to DONE, causing gh_issue_close to raise and abort the DONE transition.
  severity: medium
  mitigation: I4 wraps the gh_issue_close call in try/except inside feature_sync;
    failure is logged at WARNING but does NOT roll back the feature_state=DONE transition
    (same defensive pattern as feature_hooks.mirror_feature_to_github). Test in I4
    patches gh_issue_close to raise and asserts feature still becomes DONE.
- description: 'Auto-mode skill resolution: claude code CLI must be able to locate
    `.claude/skills/feature-decompose/` from the worker''s working directory. If skill
    discovery fails silently, the agent runs without the decomposition skill and returns
    no realizing items, causing PROCESSING→WAITING with a confusing message.'
  severity: medium
  mitigation: I7 constructs the agent invocation with an explicit skill prefix in
    the prompt body (e.g. `Use the feature-decompose skill to ...`) and passes the
    feature brief verbatim; I10 e2e test asserts that a feature with a real (mocked)
    agent run produces ≥1 realizing item and transitions to PLANNED.
- description: 'Concurrent realizing items entering WAITING simultaneously: the second
    propagate_to_feature call attempts PLANNED→WAITING on a feature already in WAITING,
    which is not in FEATURE_WORKER_TRANSITIONS and will raise InvalidTransition.'
  severity: low
  mitigation: I3 catches InvalidTransition in propagate_to_feature (same pattern as
    goal_sync.propagate_to_parent line 49-50) and logs at DEBUG — idempotent. Test
    in I3 simulates two consecutive child→WAITING events and asserts no exception
    escapes.
- description: Slug derivation strips the `YYYY-MM-DD-HHMM-` date prefix from the
    feature id; if the feature id format ever changes (e.g. lacks the prefix), the
    slug-based branch name `feature/<slug>` will not match the actual branch, and
    done-detection will incorrectly conclude the branch is absent.
  severity: low
  mitigation: I4 implements a regex-based prefix-strip with a fallback to the raw
    id when the prefix is absent; if branch_exists_on_origin returns False with the
    raw id slug, the test in I4 asserts that done-detection still works correctly
    using the unmodified id.
metrics:
  tool_calls: 12
  files_read: 9
  memory_hits: 8
  iterations_planned: 10
---

## Summary

S4 splits into 10 iterations across three layers of the DAG: foundational helpers (git_ops.branch_exists_on_origin, feature_sync resolution and state-transition cases, feature_hooks.enqueue stub) in the first layer; worker wiring (_run_one branch + _run_feature_decompose method) and the decomposition skill in the middle layer; and integration tests (_finalize + tasks.py reply path + end-to-end) in the final layer. The DAG is intentionally wide so multiple implementors can run in parallel — I1, I2, I5, I9 have no deps. The dominant design tradeoff is placing `fetch_origin` inside feature_sync's done-detection path (network I/O on the finalize hot path) versus deferring to a background task; we accept the inline fetch with a hard try/except guard because the alternative (background poll) introduces a new lifecycle to maintain. The risk register flags the ordering of feature_sync vs goal_sync in _finalize as the highest-severity concern.

## Components

### Data
- (none — S1 already added all required Task fields, FeatureState enum, FEATURE_WORKER_TRANSITIONS, transition_feature, realizing_items, set_realizes, set_issue_refs)

### Backend
- backend/app/git_ops.py: add `branch_exists_on_origin(space_dir, branch) -> bool` (read-only, validates branch, returns False on any error)
- backend/app/feature_sync.py (new): `propagate_to_feature(item_id, store, pool)` with four branches — item→WAITING+feature PLANNED, item→ACTIVE+feature WAITING, item→terminal+feature PLANNED (done-detection), else no-op; mirrors goal_sync.py shape
- backend/app/feature_hooks.py: implement `enqueue_feature_decomposition(task)` — currently a no-op stub — to enqueue the feature task via the worker pool
- backend/app/worker.py: add third branch in `_run_one` for type in (feature, fix) AND feature_state==PROCESSING → `_run_feature_decompose`; add `_run_feature_decompose` method that spawns an auto-mode agent run with the decomposition skill, then transitions feature_state based on realizing_items count and agent STATUS (mirroring _finalize lines 772-800 for the question mapping)
- backend/app/worker.py:_finalize: call `feature_sync.propagate_to_feature` after `goal_sync.propagate_to_parent` (~line 890), same try/except wrapper pattern
- backend/app/api/tasks.py reply path: call `feature_sync.propagate_to_feature` after `goal_sync.propagate_to_parent` (~line 535)

### Skill
- .claude/skills/feature-decompose/SKILL.md (new): decomposition skill that reads the feature brief, designs a goal with child tasks, POSTs them via the Cronos API, and calls `set_realizes` on the root goal with the feature_id; emits STATUS:DONE on success, STATUS:WAIT or STATUS:BLOCKED on inability to proceed

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                                    | Validation                                                                                  |
|-----|----------|------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| I1  | backend  | -          | backend/app/git_ops.py, tests/test_git_ops_branch_exists.py               | cd backend && pytest tests/test_git_ops_branch_exists.py -v --override-ini="addopts="       |
| I2  | backend  | -          | backend/app/feature_sync.py, tests/test_feature_sync_resolution.py        | cd backend && pytest tests/test_feature_sync_resolution.py -v --override-ini="addopts="     |
| I3  | backend  | I2         | backend/app/feature_sync.py, tests/test_feature_sync_waiting_resume.py    | cd backend && pytest tests/test_feature_sync_waiting_resume.py -v --override-ini="addopts=" |
| I4  | backend  | I1, I3     | backend/app/feature_sync.py, tests/test_feature_sync_done_detection.py    | cd backend && pytest tests/test_feature_sync_done_detection.py -v --override-ini="addopts=" |
| I5  | backend  | -          | backend/app/feature_hooks.py, tests/test_feature_hooks_enqueue.py         | cd backend && pytest tests/test_feature_hooks_enqueue.py -v --override-ini="addopts="       |
| I6  | backend  | I5         | backend/app/worker.py, tests/test_worker_run_one_branching.py             | cd backend && pytest tests/test_worker_run_one_branching.py -v --override-ini="addopts="    |
| I7  | backend  | I6         | backend/app/worker.py, tests/test_worker_run_feature_decompose.py         | cd backend && pytest tests/test_worker_run_feature_decompose.py -v --override-ini="addopts="|
| I8  | backend  | I4, I7     | backend/app/worker.py, backend/app/api/tasks.py, tests/test_feature_sync_integration.py | cd backend && pytest tests/test_feature_sync_integration.py -v --override-ini="addopts="   |
| I9  | backend  | -          | .claude/skills/feature-decompose/SKILL.md, .claude/skills/feature-decompose/decompose.md | python -c "import pathlib; p = pathlib.Path('.claude/skills/feature-decompose/SKILL.md'); assert p.exists() and 'realizes' in p.read_text()" |
| I10 | backend  | I8, I9     | backend/tests/test_feature_decompose_e2e.py                               | cd backend && pytest tests/test_feature_decompose_e2e.py -v --override-ini="addopts="       |

### Per-iteration acceptance

- **I1 — `git_ops.branch_exists_on_origin`** (covers R11):
  - Signature `async def branch_exists_on_origin(space_dir: Path, branch: str) -> bool` exists.
  - Calls `validate_branch(branch)` before any git operation.
  - Executes `git rev-parse --verify origin/<branch>` and returns True iff exit code == 0.
  - Does NOT call `fetch_origin` internally.
  - On any exception or non-zero exit, returns False (never raises).
  - Tests cover: branch present → True; branch absent → False; invalid branch name → False; subprocess raises → False.

- **I2 — `feature_sync.propagate_to_feature` resolution & no-op cases** (covers R5):
  - Module exists at `backend/app/feature_sync.py` with the function exported.
  - Resolves the realizes link by walking from `item_id` to the root goal (no `parent_id`) and reading `root.realizes`; if absent or feature not found → no-op return.
  - Honors realizes only on the directly-linked root goal; child tasks within a realizing goal do NOT independently trigger feature transitions (test confirms a leaf child's transition does not affect the feature).
  - Tests cover: item has no realizes → no-op; realizes target missing → no-op; child of a realizing goal → no-op; root goal with realizes → resolution succeeds.

- **I3 — `feature_sync` WAITING/RESUME branches** (covers R6, R7):
  - Item→WAITING while feature PLANNED → `transition_feature(feature_id, WAITING, allowed=FEATURE_WORKER_TRANSITIONS)` and copies `item.waiting_question` to feature's `waiting_question`.
  - Item→ACTIVE while feature WAITING → `transition_feature(feature_id, PLANNED, allowed=FEATURE_WORKER_TRANSITIONS)`.
  - InvalidTransition is caught and logged at DEBUG (idempotent under races).
  - Other (state, feature_state) combinations are no-ops.
  - Tests cover both happy paths, both no-op guards, and the concurrent WAITING race.

- **I4 — `feature_sync` done-detection** (covers R8, R9):
  - When all realizing items are terminal (DONE or ARCHIVED) AND feature is PLANNED: calls `fetch_origin(space_dir)` then `branch_exists_on_origin(space_dir, f"feature/{slug}")`.
  - Slug = feature.id with leading `YYYY-MM-DD-HHMM-` regex prefix stripped (fallback: raw id when prefix absent).
  - Branch absent → `transition_feature(feature_id, DONE)`; branch present → stay PLANNED.
  - On DONE transition with `issue_number` set, calls `gh_issue_close(space_dir, issue_number)` inside try/except (failure does NOT roll back DONE).
  - Zero realizing items guard: never attempts done-detection if `realizing_items(feature_id)` is empty.
  - `fetch_origin` failure caught and logged; stays PLANNED.
  - Tests cover: all happy paths, branch-present-stay-PLANNED, fetch-failure-stay-PLANNED, gh-close-failure-still-DONE, zero-items-no-op, partial-terminal-no-op.

- **I5 — `feature_hooks.enqueue_feature_decomposition` body** (covers R12):
  - Signature unchanged: `async def enqueue_feature_decomposition(task: "Task") -> None`.
  - Resolves the worker pool (module-level injection, mirroring `_task_store` pattern in same file) and calls `pool.enqueue(task.space_id, task.id)`.
  - Does NOT mutate `feature_state` (API has already done so).
  - No-op with WARNING log when pool is not configured (graceful degradation for tests).
  - Tests cover: pool configured → enqueue called once with correct args; pool None → WARNING logged, no exception.

- **I6 — `worker._run_one` third branch** (covers R1):
  - After the `task.type == "goal"` check, add: `elif task.type in ("feature", "fix") and task.feature_state == FeatureState.PROCESSING: await self._run_feature_decompose(task_id, user_message)`.
  - `_run_feature_decompose` stub may be added in this iteration (real body lands in I7).
  - Feature/fix tasks NOT in PROCESSING state fall through to `_run_task` (existing behavior preserved).
  - Goal tasks unchanged.
  - Tests cover all three task.type × feature_state combinations.

- **I7 — `worker._run_feature_decompose` body** (covers R2, R3, R4):
  - Spawns an agent run in auto mode using the existing `agent.run_agent` invocation pattern (mirrors `_run_task` agent setup, lines ~580-730).
  - Constructs the prompt with the feature brief and an explicit `Use the feature-decompose skill ...` prefix.
  - On agent completion: if `realizing_items(feature_id)` returns ≥1 AND `result.status == Status.DONE` → `transition_feature(feature_id, PLANNED, allowed=FEATURE_WORKER_TRANSITIONS)`.
  - Otherwise: derives `waiting_question` using the same mapping as _finalize lines 772-800 (DONE-but-no-items, WAIT, BLOCKED, crash, no-STATUS) and calls `transition_feature(feature_id, WAITING, allowed=FEATURE_WORKER_TRANSITIONS)` with the question persisted via `store.set_waiting_question` (or whatever store method S1 provides for feature waiting_question).
  - History entry is appended via the same `finalize_run`-style helper (or equivalent) so the run trail is preserved.
  - Tests cover all 5 outcome branches (success-with-items, success-zero-items, WAIT, BLOCKED, crash).

- **I8 — `_finalize` + `tasks.py` reply path wiring** (covers R10):
  - In `worker._finalize` at ~line 890, immediately after the existing `goal_sync.propagate_to_parent` try/except, add a second try/except calling `feature_sync.propagate_to_feature(task_id, self.store, self._pool)`; errors are logged via `log.exception` and never abort the caller.
  - In `backend/app/api/tasks.py` reply path at ~line 535, after the existing `goal_sync.propagate_to_parent` call, add `await feature_sync.propagate_to_feature(task_id, store, pool)` wrapped in try/except with the same logging pattern.
  - Tests cover: a realizing goal child transition triggers feature_sync from _finalize; an API reply on a realizing item triggers feature_sync from the reply path; errors in propagate_to_feature do NOT abort either caller.

- **I9 — `.claude/skills/feature-decompose/` skill** (covers R13):
  - SKILL.md describes the skill's purpose, inputs (feature brief, feature_id passed via `realizes` arg), and outputs (POST /tasks calls + set_realizes on the root goal).
  - decompose.md (or equivalent runbook) details the step-by-step: read brief → design goal + child tasks → POST /api/tasks with `type=goal` → POST `set_realizes` (or equivalent) with the new goal id and the feature_id → POST child tasks under the goal → emit STATUS:DONE.
  - Failure modes documented: STATUS:WAIT when human input is needed; STATUS:BLOCKED when the feature is incoherent or duplicated.
  - Validation: file existence + the literal substring `realizes` appears in SKILL.md (machine-checked).

- **I10 — End-to-end integration test** (synthesizes R1-R13):
  - Mocks the agent run (or uses a recorded fixture) to simulate the decomposition skill creating a realizing goal with `realizes=<feature_id>`.
  - Drives the feature task from PROCESSING through PLANNED (after decomposition) → WAITING (when a realizing child waits) → PLANNED (resume) → DONE (when all children terminal and branch absent).
  - Asserts `gh_issue_close` is invoked when `issue_number` is set.
  - Asserts the entire flow respects scope file boundary (no writes outside scope_files).

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| feature_sync ordering vs goal_sync in _finalize may observe stale state when goal_sync re-enqueues | high | I8 wires feature_sync STRICTLY after goal_sync in a deterministic try/except; propagate reads state fresh via store.get(); I8 integration test exercises the full chain |
| Race between decomposition POST and propagate_to_feature firing could fire done-detection on empty realizing set | high | I2/I4 enforce zero-items guard (cannot transition PLANNED→DONE on empty set); I9 skill MUST call set_realizes BEFORE creating child tasks |
| branch_exists_on_origin needs prior fetch; missed fetch blocks DONE indefinitely | medium | I4 places fetch_origin inside done-detection in try/except; fetch failure stays PLANNED (retried on next finalize); test mocks fetch failure |
| gh CLI may be unavailable or unauthenticated when DONE fires | medium | I4 wraps gh_issue_close in try/except; failure logged but DONE transition is NOT rolled back; matches mirror_feature_to_github pattern |
| Auto-mode skill resolution may silently miss the feature-decompose skill | medium | I7 explicitly prefixes the prompt with `Use the feature-decompose skill ...`; I10 e2e asserts ≥1 realizing item |
| Concurrent realizing items both attempt PLANNED→WAITING (second is InvalidTransition) | low | I3 catches InvalidTransition and logs at DEBUG (idempotent, same pattern as goal_sync) |
| Slug derivation breaks if feature id format changes | low | I4 implements regex prefix strip with raw-id fallback; test asserts both paths |

## Assumptions

- S1's storage extensions (`transition_feature`, `realizing_items`, `set_realizes`, `FEATURE_WORKER_TRANSITIONS`, `set_issue_refs`) are present and stable per scout's confirmed reads (storage.py lines 819, 1308, 1322, 1082; feature_state.py).
- `FEATURE_WORKER_TRANSITIONS` contains all six required transitions (PROCESSING→PLANNED, PROCESSING→WAITING, PLANNED→WAITING, WAITING→PLANNED, PLANNED→DONE), verified from feature_state.py read.
- A `set_waiting_question` (or equivalent atomic helper) exists on TaskStore to persist `feature_waiting_question` alongside `transition_feature`; if not, I7 must extend storage.py (would expand its scope — implementor should escalate via blockers if this is missing).
- Slug derivation: feature ids follow the `YYYY-MM-DD-HHMM-<slug>` convention (matches `project_git_rootgoal_standard` memory).
- The decomposition skill is implemented as a new `.claude/skills/feature-decompose/` rather than extending `pipeline-scaffold` — resolves OQ1 from analysis. Rationale: clean separation, the realizes link is a feature-specific contract, and pipeline-scaffold's existing flow (Phase 0 with 7 phase tasks) is the wrong shape for an arbitrary feature decomposition.
- Done-detection runs inline (event-driven on each realizing-item terminal transition), NOT via a polling background loop — resolves a deferred item from analysis. Acceptable cost: one `fetch_origin` per finalize-with-all-terminal call.
- has_ui=false from analysis is respected: no frontend iterations.
- All iterations commit on `feature/features-and-fixes` per the parent goal contract.

## Open questions

- OQ-A (resolves analysis OQ1): I9 specifies a NEW `.claude/skills/feature-decompose/` skill. If the implementor prefers reusing `pipeline-scaffold`/`create-goal` with a `realizes` argument, that is acceptable provided R13's acceptance is met; flag in impl-report.
- OQ-B (resolves analysis OQ2): When the space has no git remote configured, `fetch_origin` will fail; under I4's design this means the feature stays PLANNED (never DONE). If product wants "no remote → go DONE immediately on all-terminal", the implementor should add a `_space_remote_url(space_dir)` check before the fetch and skip the branch check (going DONE) when empty. Defaulting to "stay PLANNED" is safer.
- OQ-C (resolves analysis OQ3): I3's InvalidTransition catch handles the concurrent WAITING race idempotently; no additional locking needed.
- OQ-D: Whether `transition_feature` persists a `feature_waiting_question` field atomically. If not, I7 needs a small storage extension (not currently in scope_files) — implementor should escalate.

## Next consumer brief

Implementors should read `iterations[]`, `iterations[].scope_files`, `iterations[].validation_command`, and `risks[]` from the YAML header. Cross-iteration invariants not derivable from the YAML:

1. Feature id → branch slug derivation MUST be identical across I4 and the skill in I9 (regex strip of `^\d{4}-\d{2}-\d{2}-\d{4}-`); both implementors must use the exact same regex.
2. The `realizes` field MUST be set on the directly-created root goal only (no `parent_id`); the skill in I9 and the resolution logic in I2 must agree on this — child tasks of the realizing goal do NOT carry a realizes link.
3. Error-swallowing pattern in I8 wiring must mirror the existing `goal_sync.propagate_to_parent` wrapper exactly (`try/except` + `log.exception`, never re-raise).
4. Per `feedback_pipeline_narrow_k_coverage`: every iteration's `validation_command` uses `--override-ini="addopts="` to bypass the 60% coverage floor since narrow -k runs trivially fail it; the test phase will run the full suite with coverage.
5. Per `observation_worktree_main_vs_workspace`: implementors editing files in the main worktree must `cp` to the workspace worktree before `goal-task-commit`.
6. OQ-D is the only un-pre-validated assumption; if `transition_feature` cannot persist a waiting_question atomically, I7 must escalate (do not silently extend storage.py out of scope).
