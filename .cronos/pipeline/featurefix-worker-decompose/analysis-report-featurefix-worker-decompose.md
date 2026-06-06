---
cc_version: '1.0'
agent: pipeline-analyst
slug: featurefix-worker-decompose
phase: analysis
status: done
confidence: 0.85
inputs_used:
- memory:project_arc_features_fixes_board_setup
- memory:project_s1_data_model_impl
- memory:project_s2_api_impl
- memory:project_architecture_key_modules
- .cronos/pipeline/featurefix-worker-decompose/scout-report-featurefix-worker-decompose.md
- backend/app/worker.py
- backend/app/goal_sync.py
- backend/app/git_ops.py
outputs_produced:
- .cronos/pipeline/featurefix-worker-decompose/analysis-report-featurefix-worker-decompose.md
blockers: []
next_consumer: design
request: 'S4 — Worker: process-from-backlog decomposition + feature_state propagation.
  worker.py _run_one adds a third branch for feature/fix in feature_state=PROCESSING
  calling _run_feature_decompose. Decomposition runs in auto mode with a skill that
  POSTs goal+tasks with realizes=<feature_id>. Outcomes: >=1 realizing item -> processing->planned;
  WAIT/BLOCKED/nothing -> processing->waiting. New backend/app/feature_sync.py (analogue
  of goal_sync.py): propagate_to_feature(item_id, store, pool) called from _finalize
  and tasks.py reply path. Transitions: item->waiting & feature planned => planned->waiting;
  resume => waiting->planned; all items terminal AND branch absent from origin =>
  planned->done + gh_issue_close. git_ops.py: read-only branch_exists_on_origin(space_dir,
  branch).'
has_ui: false
coverage_summary:
  searched:
  - backend/app/worker.py
  - backend/app/goal_sync.py
  - backend/app/git_ops.py
  - backend/app/feature_hooks.py
  - backend/app/storage.py
  - backend/app/api/features.py
  - backend/app/api/tasks.py
  excluded:
  - frontend/: backend-only feature, no UI involvement
  - tests/: coverage at implementation/test phase
  - deploy/: no deployment changes
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: 'Worker._run_one adds a third branch: when task.type in (''feature'',
    ''fix'') AND task.feature_state == PROCESSING, it calls _run_feature_decompose(task_id)
    and never falls through to _run_task.'
  acceptance_criteria:
  - Given a task with type='feature' and feature_state=PROCESSING is dequeued, when
    _run_one executes, then _run_feature_decompose is called and _run_task is not
    called.
  - Given a task with type='feature' and feature_state != PROCESSING, when _run_one
    executes, then it falls through to _run_task (unchanged behavior).
  - Given a task with type='goal', when _run_one executes, then _run_goal is called
    (unchanged behavior).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: Worker._run_feature_decompose runs the feature task in auto mode with
    a decomposition skill that reads the feature brief and creates a goal with child
    tasks, setting realizes=<feature_id> on the root goal.
  acceptance_criteria:
  - Given POST /api/features/{id}/process transitions the feature to PROCESSING and
    enqueues it, when the worker processes the task, then an agent run is spawned
    in auto mode with the decomposition skill and the feature brief.
  - Given the agent run completes successfully, then at least one task/goal with realizes=<feature_id>
    exists in the store.
  - The realizes field is set on the root goal (the directly-created goal), not on
    child tasks within that goal.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R3
  statement: _run_feature_decompose transitions feature_state from PROCESSING to PLANNED
    when the agent run ends with at least one realizing item created.
  acceptance_criteria:
  - Given the decomposition agent returns STATUS:DONE and at least one item with realizes=<feature_id>
    exists, when _run_feature_decompose finalizes, then store.transition_feature(feature_id,
    PLANNED, allowed=FEATURE_WORKER_TRANSITIONS) is called.
  - Given the transition succeeds, then the feature task's feature_state is PLANNED.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: _run_feature_decompose transitions feature_state from PROCESSING to WAITING
    (with a question) when the agent returns STATUS:WAIT, STATUS:BLOCKED, crashes,
    or creates no realizing items.
  acceptance_criteria:
  - Given the agent returns STATUS:WAIT, when _run_feature_decompose finalizes, then
    feature_state transitions to WAITING and waiting_question is set to the agent
    context message.
  - 'Given the agent returns STATUS:BLOCKED, when _run_feature_decompose finalizes,
    then feature_state transitions to WAITING and waiting_question is prefixed ''Blocked:
    <reason>''.'
  - Given the agent exits with non-zero exit code, when _run_feature_decompose finalizes,
    then feature_state transitions to WAITING and waiting_question reflects the crash.
  - Given the agent returns STATUS:DONE but realizing_items(feature_id) is empty,
    then feature_state transitions to WAITING with an appropriate waiting_question.
  - The question derivation reuses the same _finalize status-to-question mapping (lines
    772-800 of worker.py).
  verifying_phase: test
  confidence: 0.9
- requirement_id: R5
  statement: A new module backend/app/feature_sync.py is created with a propagate_to_feature(item_id,
    store, pool) function, modelled after goal_sync.propagate_to_parent.
  acceptance_criteria:
  - The module exists at backend/app/feature_sync.py and exports propagate_to_feature.
  - propagate_to_feature accepts item_id (str), store (TaskStore), and pool (WorkerPool
    | None).
  - The function resolves the realizes link by finding the root goal whose realizes
    == feature_id, acting only on directly-linked items (not nested children).
  - If the item has no realizes link or the linked feature does not exist, the function
    is a no-op.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R6
  statement: propagate_to_feature transitions feature_state from PLANNED to WAITING
    (copying the item waiting_question) when a realizing item transitions to WAITING
    while the feature is PLANNED.
  acceptance_criteria:
  - Given a realizing root goal transitions to TaskState.WAITING and the linked feature
    is PLANNED, when propagate_to_feature is called, then transition_feature(feature_id,
    WAITING) is called and the feature waiting_question is set to the item waiting_question.
  - Given the feature is not in PLANNED state, then no transition is attempted.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R7
  statement: propagate_to_feature transitions feature_state from WAITING to PLANNED
    when a realizing item resumes (transitions to ACTIVE) while the feature is WAITING.
  acceptance_criteria:
  - Given a realizing root goal transitions to TaskState.ACTIVE and the linked feature
    is WAITING, when propagate_to_feature is called, then transition_feature(feature_id,
    PLANNED) is called.
  - Given the feature is not in WAITING state, then no transition is attempted.
  verifying_phase: test
  confidence: 0.85
- requirement_id: R8
  statement: propagate_to_feature performs done-detection and transitions feature_state
    from PLANNED to DONE when all realizing items are terminal (DONE or ARCHIVED)
    AND the feature branch does not exist on origin.
  acceptance_criteria:
  - Given all realizing items are DONE or ARCHIVED, when propagate_to_feature is called,
    then fetch_origin is called to refresh remote refs.
  - Given fetch succeeds and branch_exists_on_origin(space_dir, 'feature/<slug>')
    returns False, then transition_feature(feature_id, DONE) is called.
  - Given branch_exists_on_origin returns True (branch not yet merged), then no transition
    occurs and feature remains PLANNED.
  - Given at least one realizing item is not terminal, done-detection is not attempted.
  - 'Slug derivation: date prefix stripped from feature id (e.g., ''2026-06-03-1234-widget''
    becomes ''widget'').'
  verifying_phase: test
  confidence: 0.85
- requirement_id: R9
  statement: propagate_to_feature triggers gh_issue_close (closes the linked GitHub
    issue) when the feature transitions to DONE.
  acceptance_criteria:
  - Given the feature transitions to DONE and has issue_number set, then the GitHub
    issue close action is invoked.
  - Given the feature has no issue_number, the close action is silently skipped.
  - Issue close uses the slug (date prefix stripped) consistent with S2 issue creation.
  verifying_phase: test
  confidence: 0.8
- requirement_id: R10
  statement: propagate_to_feature is called from worker._finalize immediately after
    goal_sync.propagate_to_parent, and from the tasks.py API reply path after the
    existing goal_sync call.
  acceptance_criteria:
  - Given worker._finalize completes for any task, then feature_sync.propagate_to_feature(task_id,
    self.store, self._pool) is called after goal_sync.propagate_to_parent.
  - Given the tasks.py reply endpoint calls goal_sync, then feature_sync.propagate_to_feature(task_id,
    store, pool) is also called.
  - Errors in propagate_to_feature are caught and logged without aborting the caller
    (same pattern as existing goal_sync wrapper in _finalize).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R11
  statement: git_ops.py gains a read-only async function branch_exists_on_origin(space_dir,
    branch) that returns True if the branch ref exists on origin, with no internal
    fetch.
  acceptance_criteria:
  - 'Signature: async def branch_exists_on_origin(space_dir: Path, branch: str) ->
    bool.'
  - It calls validate_branch(branch) before any git operation.
  - It executes 'git rev-parse --verify origin/<branch>' and returns True iff exit
    code == 0.
  - It does not call fetch_origin internally; caller is responsible for fetching first.
  - On any exception or non-zero exit, it returns False (safe default, never raises).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R12
  statement: feature_hooks.enqueue_feature_decomposition (currently a no-op stub)
    is implemented to enqueue the feature task with the worker so _run_feature_decompose
    is eventually called.
  acceptance_criteria:
  - Given POST /api/features/{id}/process sets feature_state=PROCESSING and calls
    enqueue_feature_decomposition(task), the hook enqueues the task via the worker
    pool.
  - The existing function signature is preserved so the call site in features.py requires
    no change.
  - The hook performs no feature_state transition (already done by the API).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R13
  statement: A decomposition skill (new or adapted) accepts a feature brief and realizes=<feature_id>,
    creates a goal with child tasks via the API, and sets the realizes field on the
    root goal.
  acceptance_criteria:
  - The skill reads the feature brief from its input.
  - The skill creates at least one goal via POST tasks with type='goal'.
  - The skill calls set_realizes (or equivalent API endpoint) to link the root goal
    to the feature_id.
  - The skill emits STATUS:DONE on success, STATUS:WAIT or STATUS:BLOCKED on failure.
  verifying_phase: design
  confidence: 0.75
metrics:
  tool_calls: 8
  files_read: 4
  memory_hits: 4
---

## Summary

S4 implements the worker-side execution path that processes a feature from PROCESSING to PLANNED: when a feature or fix task with feature_state=PROCESSING is dequeued, a new _run_feature_decompose method runs a decomposition skill that creates a goal and child tasks linked via the realizes field. A new feature_sync.py module (modelled after goal_sync.py) propagates feature_state transitions as realizing items change state — bubbling WAITING upward, resuming to PLANNED, and detecting DONE only when all items are terminal and the feature branch has been merged (absent from origin). A read-only branch_exists_on_origin function is added to git_ops.py. The feature_hooks.enqueue_feature_decomposition stub is implemented to complete the end-to-end dispatch chain from POST /process through the worker.

## Scope

### In scope
- worker.py: third branch in _run_one for feature/fix tasks in PROCESSING state
- worker.py: new _run_feature_decompose method with outcome-based state transitions
- backend/app/feature_sync.py: new module with propagate_to_feature covering four state transition cases
- worker._finalize: call feature_sync.propagate_to_feature after existing goal_sync call
- backend/app/api/tasks.py reply path: call feature_sync.propagate_to_feature after existing goal_sync call
- git_ops.py: add branch_exists_on_origin read-only async function
- feature_hooks.enqueue_feature_decomposition: implement the no-op stub
- A decomposition skill that creates a goal+tasks and sets the realizes link

### Out of scope
- UI changes: feature_state transitions already rendered by S1/S2; no new frontend components
- GitHub issue creation: handled by S2; S4 only closes on DONE
- feature_state transitions from non-worker paths (manual admin override)
- Multi-feature concurrency guarantees across simultaneous decompositions
- Retry logic if decomposition skill fails permanently

### Deferred
- Polling mechanism for done-detection when branch deletion is slow
- Full parallelism guarantees when multiple realizing goals run concurrently
- Automatic re-trigger of decomposition if feature returns to PROCESSING after WAITING

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | worker._run_one routes feature/fix tasks in PROCESSING state to _run_feature_decompose, not _run_task |
| R2 | _run_feature_decompose spawns an auto-mode agent run with the decomposition skill and feature brief |
| R3 | _run_feature_decompose transitions PROCESSING to PLANNED when at least one realizing item is created |
| R4 | _run_feature_decompose transitions PROCESSING to WAITING with question on WAIT/BLOCKED/crash/no-items |
| R5 | New backend/app/feature_sync.py exports propagate_to_feature(item_id, store, pool) |
| R6 | propagate_to_feature transitions PLANNED to WAITING copying the question when a realizing item goes WAITING |
| R7 | propagate_to_feature transitions WAITING to PLANNED when a realizing item resumes to ACTIVE |
| R8 | propagate_to_feature transitions PLANNED to DONE via done-detection (all items terminal + branch absent) |
| R9 | propagate_to_feature triggers gh_issue_close when the feature transitions to DONE |
| R10 | propagate_to_feature is wired into worker._finalize and the tasks.py reply path |
| R11 | git_ops.branch_exists_on_origin(space_dir, branch) is read-only, validates branch, safe-defaults False |
| R12 | feature_hooks.enqueue_feature_decomposition stub is implemented to enqueue the worker task |
| R13 | A decomposition skill creates a goal+tasks via API and sets realizes on the root goal |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — _run_one routes PROCESSING feature/fix to _run_feature_decompose; other types/states unchanged
- R2 — agent is spawned in auto mode with skill and brief; resulting root goal has realizes set
- R3 — feature_state becomes PLANNED when realizes count >= 1 after agent STATUS:DONE
- R4 — feature_state becomes WAITING with appropriate question for WAIT/BLOCKED/crash/zero-realizes
- R5 — module exists, function exported, resolves realizes on root goal only, no-op if no link
- R6 — PLANNED to WAITING fires when realizing item enters WAITING; question is copied up
- R7 — WAITING to PLANNED fires when realizing item resumes to ACTIVE
- R8 — PLANNED to DONE fires only when all items terminal AND branch absent; branch present keeps PLANNED
- R9 — issue close fires on DONE when issue_number is set; silently skipped otherwise
- R10 — both _finalize and reply path call propagate_to_feature; errors caught and logged
- R11 — validates branch name, queries origin/branch via rev-parse, returns False on any error
- R12 — stub implemented; features.py call site unchanged; no state transition in hook
- R13 — skill emits STATUS:DONE on success, STATUS:WAIT/BLOCKED on failure; realizes set on root goal

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | worker._run_one adds a third branch for feature/fix tasks in PROCESSING state |
| R2 | test | _run_feature_decompose spawns an auto-mode agent run with decomposition skill and feature brief |
| R3 | test | _run_feature_decompose transitions PROCESSING to PLANNED when at least one realizing item exists |
| R4 | test | _run_feature_decompose transitions PROCESSING to WAITING with question on failure outcomes |
| R5 | test | New backend/app/feature_sync.py exports propagate_to_feature(item_id, store, pool) |
| R6 | test | propagate_to_feature transitions PLANNED to WAITING when a realizing item goes WAITING |
| R7 | test | propagate_to_feature transitions WAITING to PLANNED when a realizing item resumes to ACTIVE |
| R8 | test | propagate_to_feature transitions PLANNED to DONE only when all items terminal and branch absent |
| R9 | test | propagate_to_feature closes the GitHub issue when the feature transitions to DONE |
| R10 | test | propagate_to_feature is wired into _finalize and tasks.py reply path |
| R11 | test | git_ops.branch_exists_on_origin is read-only, validates branch, safe-defaults to False |
| R12 | test | feature_hooks.enqueue_feature_decomposition enqueues the worker task without state mutation |
| R13 | design | Decomposition skill creates goal+tasks via API with realizes link on root goal |

## Assumptions

- has_ui=false rationale: S4 is entirely backend worker logic. All state transitions are rendered by S1/S2 frontend; no new frontend components or API response schemas are introduced.
- S1 storage extensions (transition_feature, realizing_items, set_realizes, FEATURE_WORKER_TRANSITIONS) are present and stable per scout confirmation.
- propagate_to_feature honors realizes only on the directly-linked root goal (the goal with no parent_id whose realizes == feature_id). Child tasks within the realizing goal do not independently link to the feature.
- Slug derivation: strip the leading date prefix (YYYY-MM-DD-HHMM-) from the feature task id to obtain the branch slug. This matches the goal branch lifecycle convention from project_git_rootgoal_standard memory.
- fetch_origin before branch_exists_on_origin is the caller's responsibility (feature_sync done-detection path), not git_ops's. This avoids redundant fetches when multiple realizing items finish close together.
- The decomposition skill design (reuse pipeline-scaffold vs. new feature-specific skill) is deferred to the design phase per scout open question 1. R13 specifies the behavioral contract regardless of implementation choice.
- Done-detection is event-driven (triggered each time a realizing item transitions to DONE/ARCHIVED), not polling. A feature with a merged goal but an undeleted remote branch will stay PLANNED until the branch is deleted.
- FEATURE_WORKER_TRANSITIONS is assumed to include all six required transitions. If any are missing, the implementor must extend the set in storage.py.
- The first realizing item to enter WAITING causes the feature to transition PLANNED to WAITING. This is the "at least one blocked" signal; other concurrently running realizing items continue unaffected.

## Open questions

- OQ1: Decomposition skill: reuse pipeline-scaffold with a realizes argument vs. new feature-decompose skill? Design agent must decide. Recommend new skill for clean separation.
- OQ2: No git remote configured: should done-detection skip the branch check and go DONE immediately, or remain PLANNED? Recommend skip branch check and go DONE when no remote is configured.
- OQ3: Concurrent realizing items entering WAITING simultaneously: both propagate_to_feature calls attempt PLANNED to WAITING. The second call should receive InvalidTransition (idempotent). Confirm FEATURE_WORKER_TRANSITIONS and transition_feature raise InvalidTransition consistently with goal_sync pattern.
- OQ4: Request cites _finalize mapping at lines 364-392; actual mapping is at lines 772-800 in the current codebase. Implementor should read current lines, not the request's stale numbers.

## Next consumer brief

Read traceability[] for the full requirement list and the Scope section for hard boundaries. Key design decisions to resolve:

1. Decomposition skill (OQ1): choose between adapting pipeline-scaffold (add realizes arg) or a new feature-decompose skill. R13 defines the behavioral contract either way.
2. _run_feature_decompose structure: mirror _run_task for agent invocation but bypass _finalize TaskState machine — call transition_feature() directly. The method needs space_dir for fetch + branch check in done-detection.
3. feature_sync.py layout: four handler branches — (a) item WAITING + feature PLANNED: PLANNED to WAITING; (b) item ACTIVE + feature WAITING: WAITING to PLANNED; (c) item DONE/ARCHIVED + feature PLANNED: done-detection path; (d) all other combos: no-op. Module is ~90 lines modelled on goal_sync.py.
4. Integration wiring: two call sites at _finalize (after line 890) and tasks.py apply_reply (after ~line 535). Both use the same error-swallowing try/except log.exception pattern.
5. Risk: done-detection path calls fetch_origin (network I/O) inside the finalize hot path. Design agent should evaluate whether to defer this to a background task.
6. Validate FEATURE_WORKER_TRANSITIONS in storage.py covers all six transitions before specifying implementation details.
