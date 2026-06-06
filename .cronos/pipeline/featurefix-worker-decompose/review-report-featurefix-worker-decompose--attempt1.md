---
cc_version: "1.0"
agent: pipeline-reviewer
slug: featurefix-worker-decompose--attempt1
phase: review
status: done
confidence: 0.82
inputs_used:
  - memory:project_arc_features_fixes_board_setup
  - memory:project_s4_worker_decompose_impl
  - memory:observation_worktree_main_vs_workspace
  - .cronos/pipeline/featurefix-worker-decompose/design-report-featurefix-worker-decompose.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i1.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i2.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i3.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i4.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i5.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i6.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i7.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i8.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i9.md
  - .cronos/pipeline/featurefix-worker-decompose/impl-report-featurefix-worker-decompose--i10.md
  - .cronos/pipeline/featurefix-worker-decompose/test-report-featurefix-worker-decompose.md
outputs_produced:
  - .cronos/pipeline/featurefix-worker-decompose/review-report-featurefix-worker-decompose--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 22
  files_read: 12
  memory_hits: 3
  diff_lines_reviewed: 3570
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: high
    file: backend/app/main.py
    evidence: "`feature_hooks.configure_pool(pool)` is never called in main.py lifespan. main.py line 378 calls `feature_hooks.configure_store(task_store)` but there is no matching `configure_pool` call. Consequence: `POST /api/features/{id}/process` calls `enqueue_feature_decomposition(task)` which finds `_worker_pool is None`, logs `_worker_pool not configured — enqueue skipped`, and returns. The feature task is never enqueued, the new `_run_one` branch in worker.py is dead code in production, and the entire S4 golden path (process → decompose → realize) does not function. I5 implementor flagged this as 'out-of-scope task for a later iteration, likely I6 or I8' but no subsequent iteration scoped main.py."
    blocking: true
    suggested_action: "Add a follow-up iteration (or fold into I8) that adds `backend/app/main.py` to scope_files and inserts `feature_hooks.configure_pool(pool)` immediately after the existing `feature_hooks.configure_store(task_store)` call at main.py:378, using the same WorkerPool instance already constructed during lifespan startup. Add one focused test asserting `_worker_pool` is non-None after `lifespan` enters, and one integration test asserting `POST /features/{id}/process` results in `pool.enqueue` being called."
  - id: F2
    severity: medium
    file: backend/app/feature_sync.py:80
    evidence: "WAITING branch calls `await store.set_feature_waiting_question(feature_id, waiting_q)` then wraps the whole try block in `except AttributeError` to swallow the case where the method does not exist. `TaskStore` in `backend/app/storage.py` indeed has no `set_feature_waiting_question` method (confirmed via git grep). The result: when a realizing root goal enters WAITING with a `waiting_question`, the feature transitions to WAITING but the question is silently dropped (only logged at DEBUG). Design OQ-D flagged this; I3 noted it as a low out-of-scope finding."
    blocking: false
    suggested_action: "Either (a) add `TaskStore.set_feature_waiting_question(feature_id, question)` to backend/app/storage.py with atomic write and call it without the AttributeError guard, or (b) accept the gap and remove the dead AttributeError branch + drop the unused `waiting_q` copy from the WAITING branch and document the limitation in the design. Option (a) is preferable because the feature card's `waiting_question` is the user-visible surface for why a feature is blocked."
  - id: F3
    severity: medium
    file: backend/app/feature_sync.py:160
    evidence: "`_SPACES_DIR = _DATA_DIR / 'spaces'` is module-level; it is evaluated at import time from `CRONOS_DATA_DIR` env var with `/data` fallback. The done-detection branch then constructs `space_dir = _SPACES_DIR / feature.space_id` and calls `fetch_origin(space_dir)`. There is no validation that `space_dir` exists or is a git working tree, and no check that the space has a configured git remote. If a space was created without a linked repo (Cronos supports unlinked spaces — see `space_storage.py`), `fetch_origin` will fail on every all-terminal call and the feature will be permanently stuck in PLANNED. Design OQ-B flagged this but the implementor chose the 'stay PLANNED' default without adding the empty-remote check."
    blocking: false
    suggested_action: "Add an early check at the top of the done-detection branch using `space_store.get(feature.space_id)` and `space.repo_url` (or equivalent attribute) — if the space has no remote configured, transition PLANNED→DONE without running fetch_origin/branch_exists_on_origin. Alternatively, document explicitly in the SKILL.md and design that DONE detection requires a linked repo. Either resolution is acceptable but the current silent permanent-PLANNED behavior is a usability footgun."
  - id: F4
    severity: low
    file: backend/app/worker.py:430
    evidence: "The `_run_one` branch matches `task.type in ('feature', 'fix') and task.feature_state == FeatureState.PROCESSING`. A feature/fix task with `feature_state=None` (e.g. legacy data or a future state value introduced before transition_feature is called) falls through to `_run_task`, which will attempt to invoke an agent with type='feature'. `_run_task` assumes a goal/task brief shape and may behave inconsistently for a non-PROCESSING feature/fix. The I6 implementor noted this is 'safe per the design' but the brief shape mismatch is not tested."
    blocking: false
    suggested_action: "Add a defensive `elif task.type in ('feature', 'fix'):` branch that logs a warning and returns rather than falling through to `_run_task`, OR extend `_run_task` with a guard that recognises feature/fix tasks and routes them somewhere safe. A unit test in test_worker_run_one_branching.py asserting the new behavior (feature_state=None or feature_state=PLANNED/WAITING) makes the contract explicit."
  - id: F5
    severity: low
    file: backend/app/worker.py
    evidence: "Diff line budgets exceeded for I4 (488 vs 350), I7 (717 vs 500), I8 (331 vs 250), and I10 (449 vs 350). All overages are in test files (e.g. I7 implementation is 171 lines; the test file is 546 lines for 19 tests). No tests were dropped. This is acceptable in substance — comprehensive test coverage is preferred over a strict line budget — but the design's max_diff_lines field is being treated as advisory rather than binding."
    blocking: false
    suggested_action: "Architects should either (a) raise the max_diff_lines budget for iterations whose test scope is intentionally broad, or (b) split overlarge test files across two iterations. No code change required for this attempt."
---

## Summary

S4 ships 10 implementation iterations across `feature_sync.py` (new module), `worker.py` (third `_run_one` branch + `_run_feature_decompose` body), `git_ops.py` (`branch_exists_on_origin`), `feature_hooks.py` (`enqueue_feature_decomposition` body + `configure_pool` injection point), `api/tasks.py` (reply path wiring), and a new `feature-decompose` skill, with comprehensive test coverage (8+5+6+11+12+14+19+6+pass+4 = 85+ new test cases). Scope discipline is clean: the 16 files in the S4 commit (`7d72d64`) match the union of `iterations[].scope_files[]` exactly, no escapes. The test gate is green (3398p / 0f / 84.88% coverage). However, one substantive blocking issue remains: `feature_hooks.configure_pool(pool)` is never wired in `main.py` lifespan, so the production `POST /features/{id}/process` → `enqueue_feature_decomposition` path is a silent no-op and the entire `_run_feature_decompose` branch is unreachable. This was flagged by the I5 implementor as a follow-up but the design never scheduled the wiring iteration. Recommended verdict: `needs_fix` — small, well-scoped fix to add main.py to a follow-up iteration.

## Findings

- **F1 (high, blocking)** — `feature_hooks.configure_pool` not wired in `main.py` lifespan; `_worker_pool` stays None in production; `POST /features/{id}/process` is a no-op WARNING; `_run_feature_decompose` is dead code. See YAML for evidence and suggested action.
- **F2 (medium, non-blocking)** — `set_feature_waiting_question` referenced but not present on `TaskStore`; silently swallowed via `AttributeError`. WAITING-state feature cards will not show the realizing goal's blocking question.
- **F3 (medium, non-blocking)** — done-detection requires a configured git remote on the space; spaces without a remote remain permanently PLANNED with no user-facing signal.
- **F4 (low, non-blocking)** — `_run_one` branch silently falls through to `_run_task` for feature/fix tasks in any non-PROCESSING state, including `None`; behavior under that fall-through is not tested.
- **F5 (low, non-blocking)** — `max_diff_lines` budgets exceeded in I4/I7/I8/I10, entirely in test files; substantive but worth noting for architect planning.

## Verdict

`needs_fix`. The S4 implementation is substantively correct and well-tested in isolation, but production traffic to `POST /features/{id}/process` does not actually trigger decomposition because `_worker_pool` is never injected. A single follow-up iteration adding `feature_hooks.configure_pool(pool)` to `main.py` lifespan resolves F1.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union (16 files); no per-iteration scope-escape verification was done at attempt time by the implementors, but the union-level union check confirms no escapes across the whole S4 cycle.
- The S4 diff range under review is `60178a2..7d72d64` on branch `feature/features-and-fixes` (the single commit by the pipeline-implementor agent on top of the merged S3 doc-sync commit).
- Test gate is authoritative: 3398p / 0f / 0e / coverage 84.88% from `test-report-featurefix-worker-decompose.md` with `gate_decision: pass`.
- `WorkerPool.enqueue` is a no-op when the worker for that space has not been started; analysis of `autopilot.pickup_next` confirms autopilot only picks BACKLOG tasks, so a feature/fix in PROCESSING is never picked up that way — the only path is via `enqueue_feature_decomposition` → `WorkerPool.enqueue`, which makes the missing `configure_pool` wiring functionally blocking.
- Memory entry `project_s4_worker_decompose_impl` corroborates the impl-report claims at the commit level (commit 7d72d64 on feature/features-and-fixes matches the inputs declared).
- Diff line budget overages are acceptable because they are entirely in test files with concrete acceptance coverage, not in implementation code.

## Open questions

- None.

## Next consumer brief

Implementor: address F1 by opening a new iteration `I11` (or folding into a hand-fix on attempt 2) with `scope_files: [backend/app/main.py, backend/tests/test_main_lifespan_configure_pool.py]`. Insert `feature_hooks.configure_pool(pool)` immediately after the existing `feature_hooks.configure_store(task_store)` call at `backend/app/main.py:378`, using the `WorkerPool` instance already constructed during lifespan startup. Add one test asserting `_worker_pool` is non-None after lifespan startup, and one integration test asserting `POST /features/{id}/process` results in `pool.enqueue` being called with `(task.space_id, task.id)`. F2-F5 are non-blocking and may be addressed in this attempt or deferred to a follow-up; F2 (atomic `set_feature_waiting_question`) is the most user-visible of the non-blocking set.
