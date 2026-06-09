---
cc_version: "1.0"
agent: pipeline-analyst
slug: tasksummary-additions
phase: analysis
status: done
confidence: 0.93
inputs_used:
  - .cronos/pipeline/feature-card-ux-polish/scout-report-feature-card-ux-polish.md
  - backend/app/models.py
  - backend/app/storage.py
outputs_produced:
  - .cronos/pipeline/feature-card-ux-polish/analysis-report-tasksummary-additions.md
blockers: []
next_consumer: design
request: "SG1 Backend TaskSummary Additions.\n\nScope:\n- backend/app/models.py — add to TaskSummary:\n  - realized_by_count: int = 0 (count of tasks/goals that realize this feature)\n  - realizes_feature_key: str | None = None (e.g. \"FEAT-007\" for the feature this task realizes)\n- backend/app/storage.py — populate these fields when building task summaries:\n  - realized_by_count: count of tasks where task.realizes == this task's id\n  - realizes_feature_key: if task.realizes is set, look up the target's feature_key\n- Backend tests: verify the new fields appear correctly in list/board API responses"
has_ui: false
coverage_summary:
  searched:
    - backend/app/models.py (TaskSummary class, lines 88-138)
    - backend/app/storage.py (feature_board method, summarize function)
    - .cronos/pipeline/feature-card-ux-polish/scout-report-feature-card-ux-polish.md
  excluded:
    - frontend/: backend-only change; frontend consumer is out of scope for SG1
    - deploy/: infrastructure not affected
  strategies:
    - memory_retrieval
    - read_targeted
    - grep_symbol
    - requirements_decomposition
    - traceability_mapping
traceability:
  - requirement_id: R1
    statement: "TaskSummary gains a realized_by_count: int = 0 field in backend/app/models.py."
    acceptance_criteria:
      - "TaskSummary definition in models.py includes realized_by_count as an int field defaulting to 0."
      - "Serialised JSON for any task summary includes the realized_by_count key."
    verifying_phase: test
    confidence: 0.98

  - requirement_id: R2
    statement: "TaskSummary gains a realizes_feature_key: str | None = None field in backend/app/models.py."
    acceptance_criteria:
      - "TaskSummary definition in models.py includes realizes_feature_key as str | None defaulting to None."
      - "Serialised JSON for any task summary includes the realizes_feature_key key (null when not set)."
    verifying_phase: test
    confidence: 0.98

  - requirement_id: R3
    statement: "storage.py populates realized_by_count when building summaries for feature_board() and general task list/board endpoints."
    acceptance_criteria:
      - "Given a space where task T1 has realizes == feature F1.id, then F1's summary returned by feature_board() has realized_by_count == 1."
      - "Given a space where zero tasks realize feature F2, then F2's summary has realized_by_count == 0."
      - "Given a space where N tasks realize feature F3, then F3's summary has realized_by_count == N."
      - "General task list/board summaries that are features also expose correct realized_by_count (not always zero)."
    verifying_phase: test
    confidence: 0.92

  - requirement_id: R4
    statement: "storage.py populates realizes_feature_key when building summaries for all task list/board endpoints."
    acceptance_criteria:
      - "Given task T1 with realizes == feature F1.id, T1's summary has realizes_feature_key == F1.feature_key."
      - "Given task T2 with realizes == None, T2's summary has realizes_feature_key == None."
      - "Given task T3 with realizes pointing to a deleted/missing feature, T3's summary has realizes_feature_key == None (graceful fallback)."
    verifying_phase: test
    confidence: 0.90

  - requirement_id: R5
    statement: "Existing realizing_count denormalization in feature_board() is preserved unchanged."
    acceptance_criteria:
      - "feature_board() still sets realizing_count on each feature summary as before (lines 776-794 of storage.py)."
      - "No regression in tests that reference realizing_count."
    verifying_phase: test
    confidence: 0.99

  - requirement_id: R6
    statement: "Backend tests cover the new fields in list and board API responses."
    acceptance_criteria:
      - "At least one test asserts realized_by_count is correct for a feature task in the feature_board response."
      - "At least one test asserts realizes_feature_key is correct for a task with a non-null realizes field."
      - "At least one test asserts realizes_feature_key is None for a task without realizes set."
      - "Tests exercise the graceful fallback when realized target is missing."
    verifying_phase: test
    confidence: 0.90

metrics:
  tool_calls: 5
  files_read: 3
  memory_hits: 0
---

## Summary

SG1 adds two denormalized fields to `TaskSummary` — `realized_by_count` and `realizes_feature_key` — to give frontend consumers the data they need without a second API call. The pattern mirrors the existing `realizing_count` field (models.py:127, storage.py:794). `realized_by_count` aggregates how many tasks point at a feature via `realizes`, while `realizes_feature_key` translates a raw UUID in `task.realizes` to a human-readable feature key (e.g. "FEAT-007"). Both fields default to safe values (0 and None respectively), making the change fully additive with no breaking API effect.

---

## Scope

### In scope
- Add `realized_by_count: int = 0` to `TaskSummary` in `backend/app/models.py`
- Add `realizes_feature_key: str | None = None` to `TaskSummary` in `backend/app/models.py`
- Populate `realized_by_count` in `storage.py` `feature_board()` (the primary feature consumer)
- Populate `realizes_feature_key` in `storage.py` for all task summary builds where `task.realizes` is non-null — this includes both `feature_board()` and the general task list/board methods
- Preserve existing `realizing_count` field and all population logic unchanged
- Backend unit/integration tests for the new fields

### Out of scope
- Frontend changes (`types.ts`, `Card.tsx`) — those belong to SG2 (frontend-card-board-fixes)
- API schema changes beyond what Pydantic serialisation already provides automatically
- Renaming or replacing the existing `realizing_count` field

### Deferred
- Exposing `realized_by_count` on non-feature task types (tasks, goals, issues) — currently zero by definition and not needed by any consumer
- Pagination or caching concerns for very large realization graphs

---

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Add `realized_by_count: int = 0` field to TaskSummary |
| R2 | Add `realizes_feature_key: str | None = None` field to TaskSummary |
| R3 | Populate `realized_by_count` in storage summary builders |
| R4 | Populate `realizes_feature_key` in storage summary builders |
| R5 | Preserve existing `realizing_count` logic unchanged |
| R6 | Backend tests cover new fields in list/board responses |

---

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array. Compact summary:

- R1 — `realized_by_count` present as int=0 default in TaskSummary; appears in serialised JSON
- R2 — `realizes_feature_key` present as str|None=None in TaskSummary; appears as null in serialised JSON when unset
- R3 — `feature_board()` counts correctly; count matches N tasks with `realizes==feature_id`; general endpoints also show non-zero counts for features
- R4 — Summary for any task with `realizes` set shows the target feature's `feature_key`; None for tasks without `realizes`; None when realizes target is missing (graceful fallback)
- R5 — Existing `realizing_count` test suite still green; no regression
- R6 — Tests cover correct value, zero value, missing-target fallback, and list/board API responses

---

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | TaskSummary gains a `realized_by_count: int = 0` field |
| R2 | test | TaskSummary gains a `realizes_feature_key: str \| None = None` field |
| R3 | test | `realized_by_count` is populated correctly in feature_board() and general list/board endpoints |
| R4 | test | `realizes_feature_key` is populated from the target task's `feature_key`, with None fallback |
| R5 | test | Existing `realizing_count` logic is preserved unchanged |
| R6 | test | Backend tests cover new fields in list and board API responses |

---

## Assumptions

- **has_ui=false rationale**: All changes are in Python backend models and storage. Frontend consumption (types.ts, Card.tsx) is SG2 scope. No user-visible screen changes in this subgoal.
- **Additive-only change**: Both new fields default to non-breaking values (0 / None), so no migration or backwards-compatibility layer is needed.
- **Existing pattern is canonical**: `realizing_count` (models.py:127, storage.py:776-794) is the implementation reference. The design agent should follow this pattern for the new fields.
- **realized_by_count ≠ realizing_count**: Despite identical semantics, the task brief explicitly requests `realized_by_count` as a new field. This is treated as a distinct addition; `realizing_count` is not renamed. If the design agent finds they are truly redundant, that is a design-phase decision.
- **Graceful fallback for missing realizes target**: The brief does not specify what happens if `task.realizes` points to a deleted task. Treating it as None (R4 AC-3) is the safest default and consistent with nullable foreign-key patterns elsewhere in the codebase.
- **General task endpoints include list_tasks_board / list_tasks**: The brief says "list/board API responses"; these correspond to the GET /tasks and GET /tasks/board endpoints. The design agent should confirm which storage methods underlie those endpoints.

---

## Open questions

- None. Scope is fully bounded by the task brief and scout findings.

---

## Next consumer brief

**Design agent:** read `traceability[]` for all six requirements and `## Scope` for the OUT items (frontend changes are SG2).

Key decision points not derivable from the header:

1. **Which storage methods to update for R3/R4**: `feature_board()` (lines 768-800) is the primary consumer; also confirm whether `list_tasks_board()` and `list_tasks()` call `summarize()` directly and whether they need a separate realization-count pass (same pattern as lines 776-779 but space-wide).

2. **realizes_feature_key lookup**: `summarize()` currently maps `task.realizes` (a UUID) into the summary unchanged. To populate `realizes_feature_key`, storage needs a UUID→feature_key lookup. This can be done as a pre-pass (build a `{task_id: feature_key}` dict) or inline per task. Design should pick the pattern that avoids O(N²) for large task sets.

3. **realized_by_count for general endpoints**: Today only `feature_board()` counts realizing items. For the general board/list to show the same count, the same pre-pass must be applied. Design should evaluate whether a shared helper is cleaner than duplicating the counting logic.

4. **Test placement**: New tests belong in `backend/tests/` — likely alongside the existing feature_board tests. The design agent should identify the exact test file.
