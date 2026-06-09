---
cc_version: '1.0'
agent: pipeline-architect
slug: tasksummary-additions
phase: design
status: done
confidence: 0.88
inputs_used:
- .cronos/pipeline/feature-card-ux-polish/analysis-report-tasksummary-additions.md
- .cronos/pipeline/feature-card-ux-polish/scout-report-feature-card-ux-polish.md
- backend/app/models.py
- backend/app/storage.py
- backend/tests/test_feature_board.py
outputs_produced:
- .cronos/pipeline/feature-card-ux-polish/design-report-tasksummary-additions.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/models.py (TaskSummary, lines 98-137)
  - backend/app/storage.py (summarize L360, board L742, feature_board L768, realizing_items
    L1358)
  - backend/tests/test_feature_board.py (existing realizing_count patterns L75-106)
  excluded:
  - frontend/: SG2 scope (frontend-card-board-fixes); has_ui=false in upstream analysis
  - backend/migrations/: schema unchanged — fields are computed denorm, not persisted
      columns
  - deploy/: infrastructure not affected
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: data
  scope_files:
  - backend/app/models.py
  validation_command: cd backend && pytest tests/test_feature_model.py tests/test_feature_schemas.py
    tests/test_feature_serialization.py -v --override-ini="addopts="
  max_diff_lines: 60
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/storage.py
  validation_command: cd backend && pytest tests/test_feature_board.py tests/test_storage_board_excludes_features.py
    tests/test_feature_realizes.py -v --override-ini="addopts="
  max_diff_lines: 220
  depends_on:
  - I1
- id: I3
  type: backend
  scope_files:
  - backend/tests/test_feature_board.py
  - backend/tests/test_tasksummary_realizes_fields.py
  validation_command: cd backend && pytest tests/test_feature_board.py tests/test_tasksummary_realizes_fields.py
    -v --override-ini="addopts="
  max_diff_lines: 300
  depends_on:
  - I1
  - I2
risks:
- description: O(N) per-task lookup inside summarize() (UUID -> feature_key) becomes
    O(N^2) if implemented as an inner scan over self._by_id for every task summarized
    in board() / feature_board(). At ~hundreds of tasks per space this is invisible,
    but cards-board renders for any space size.
  severity: medium
  mitigation: 'I2 MUST build a single per-call {task_id: feature_key} dict scoped
    to the same space before iterating (mirroring the realizing_counts pre-pass at
    storage.py:776-779). Inject the dict into summarize() via a new optional helper
    signature (e.g. summarize(task, *, feature_key_by_id=None, realized_by_count_by_id=None))
    so all three call sites (board L754, feature_board L794, realizing_items L1369)
    can share one implementation. No call site iterates self._by_id inside the summary
    loop.'
- description: 'R4 AC-3 graceful fallback: a task whose realizes points at a deleted
    task must still serialize with realizes_feature_key=None. A naive dict[task.realizes]
    (KeyError) or .feature_key access on a None lookup result would crash the whole
    board endpoint.'
  severity: high
  mitigation: 'I2 builds the lookup dict via comprehension over only present-and-typed
    tasks ({t.id: t.feature_key for t in self._by_id.values() if t.space_id == space_id
    and t.feature_key is not None}), and the summarize helper uses dict.get(task.realizes)
    with default None. I3 includes an explicit test where T3 has realizes set to a
    non-existent UUID and asserts realizes_feature_key is None and no exception is
    raised.'
- description: 'R5 regression: refactoring summarize() to accept new optional kwargs
    could silently change the existing realizing_count behavior (which is currently
    set AFTER summarize() returns, at storage.py:795). If I2 moves realizing_count
    assignment INTO summarize() to share the pattern, any existing test asserting
    summary.realizing_count == 0 immediately post-summarize() in isolation would break.'
  severity: medium
  mitigation: 'I2 preserves the existing ''set realizing_count after summarize() returns''
    pattern verbatim at the feature_board() call site. The new realized_by_count and
    realizes_feature_key fields follow the SAME pattern: computed by storage method,
    assigned to summary AFTER summarize() returns. summarize() itself is NOT modified
    — only models.py adds the two new fields (default 0 / None). I3 runs the full
    test_feature_board.py file to detect any realizing_count regression immediately.'
- description: 'Scope drift: realized_by_count semantically duplicates realizing_count.
    An implementor reading the brief might delete or alias realizing_count, breaking
    SG2''s frontend (which already reads realizing_count) and any cross-pipeline assumption.'
  severity: medium
  mitigation: 'Analysis Assumption #4 is explicit: realized_by_count is ADDED as a
    distinct field; realizing_count is NEVER renamed, removed, or aliased. I2 scope_files
    includes only storage.py (no models.py field removal). I3 adds an assertion that
    BOTH realizing_count and realized_by_count are present on the same summary and
    hold the same value for feature tasks in feature_board() output.'
- description: 'Cross-space leakage: a {task_id: feature_key} lookup built without
    space_id scoping would let a task in space A read realizes_feature_key from a
    feature in space B. validate_realizes() already prevents cross-space realizes
    assignment, but a stale UUID match would still resolve.'
  severity: low
  mitigation: I2 scopes the lookup dict by space_id when called from board(scope)
    / feature_board(space_id). For board() with scope=None ('all'), realizes_feature_key
    resolution is still safe because the lookup spans all tasks (matching the same
    boundary as the data shown). I3 includes a cross-space test asserting a UUID matching
    a feature in space B does not leak into a summary for space A's board().
metrics:
  tool_calls: 10
  files_read: 5
  memory_hits: 0
  iterations_planned: 3
---

## Summary

SG1 backend addition: extend `TaskSummary` with two denormalized fields and populate them from `storage.py` without touching `summarize()` itself. The plan is intentionally narrow (3 iterations) because the change mirrors the existing `realizing_count` pattern: I1 adds the model fields (additive, fully backwards-compatible); I2 wires per-space pre-pass dictionaries into `board()` and `feature_board()` and assigns the new fields onto each summary AFTER `summarize()` returns; I3 covers all six requirements in tests including the R4 graceful-fallback path. The DAG is the canonical data -> backend -> test chain. The key risk is O(N^2) lookups inside the summary loop; the mitigation is a per-call lookup dict mirroring the existing `realizing_counts` pre-pass at storage.py:776-779.

## Components

### Data
- `TaskSummary` (backend/app/models.py): add `realized_by_count: int = 0` (mirrors `realizing_count` at L137) and `realizes_feature_key: str | None = None` (parallel to `realizes` at L125). Both serialize automatically via Pydantic; no schema migration required.

### Backend
- `feature_board()` (backend/app/storage.py:768-800): extend the existing per-space pre-pass at L776-779 with a `feature_key_by_id` dict. Assign `summary.realized_by_count = realizing_counts.get(task.id, 0)` (semantic duplicate of existing `realizing_count` — both set) and `summary.realizes_feature_key = feature_key_by_id.get(task.realizes) if task.realizes else None`.
- `board()` (backend/app/storage.py:742-766): extend the existing loop with a same-scope `feature_key_by_id` pre-pass. Assign `summary.realizes_feature_key` for any task with non-null `realizes`. `realized_by_count` stays 0 here because `board()` excludes features (L752-753) — features cannot appear so the field is by definition 0.
- `realizing_items()` (backend/app/storage.py:1358-1370): cross-space helper — populate `realizes_feature_key` so realizes-driven UI surfaces consistent values. Same lookup pattern but unscoped (matches the method's existing cross-space behavior).

<!-- Frontend section omitted: has_ui=false in upstream analysis -->

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                                       | Validation                                                                                                                  |
|-----|----------|------------|------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| I1  | data     | -          | backend/app/models.py                                                        | cd backend && pytest tests/test_feature_model.py tests/test_feature_schemas.py tests/test_feature_serialization.py -v        |
| I2  | backend  | I1         | backend/app/storage.py                                                       | cd backend && pytest tests/test_feature_board.py tests/test_storage_board_excludes_features.py tests/test_feature_realizes.py -v |
| I3  | backend  | I1, I2     | backend/tests/test_feature_board.py, backend/tests/test_tasksummary_realizes_fields.py | cd backend && pytest tests/test_feature_board.py tests/test_tasksummary_realizes_fields.py -v                              |

## Risks

| Risk                                                                                       | Severity | Mitigation                                                                                                                                                                              |
|--------------------------------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| O(N^2) lookup if UUID->feature_key resolved inside summary loop                            | medium   | Per-call `{task_id: feature_key}` dict built once, mirroring realizing_counts pre-pass; injected via shared helper signature                                                              |
| R4 AC-3 fallback (realizes target deleted) could crash board                               | high     | Lookup dict only contains feature_key-bearing tasks; resolution via `dict.get(..., None)`; I3 test covers missing-target path                                                            |
| R5 regression on realizing_count if summarize() is refactored                              | medium   | Preserve existing "assign realizing_count AFTER summarize() returns" pattern; new fields follow same post-assign pattern; do NOT modify summarize() signature                              |
| Scope drift — implementor renames/aliases realizing_count thinking realized_by_count replaces it | medium   | Analysis Assumption #4 binding: both fields coexist; I3 asserts both fields present and equal on feature summaries                                                                       |
| Cross-space UUID match leaks realizes_feature_key from another space                       | low      | Lookup dict scoped by space_id in board()/feature_board(); I3 cross-space test asserts no leakage                                                                                       |

## Assumptions

- `summarize()` (storage.py:360) is NOT modified in I2. New fields are assigned onto the returned TaskSummary instance after summarize() returns, matching the existing realizing_count pattern at storage.py:795. This keeps the helper signature stable for any other call sites.
- `realized_by_count` semantically equals `realizing_count` for feature tasks; both are set to the SAME value in feature_board(). Analysis Assumption #4 binds: realizing_count is preserved as-is; we add realized_by_count as a parallel new field rather than renaming.
- `board()` excludes features (storage.py:752-753), so `realized_by_count` stays 0 for any summary it returns by definition. Only `realizes_feature_key` is populated there.
- The model addition (I1) is non-breaking: both new fields have default values so existing test fixtures and JSON deserialization paths continue to work without modification.
- No new SQLite migration is required — these fields are derived in Python at summary build time, not persisted on the Task row.
- Test file naming: I3 creates a new `backend/tests/test_tasksummary_realizes_fields.py` for the cross-space, missing-target, and `realizes_feature_key`-specific cases; existing `backend/tests/test_feature_board.py` is extended only for the R5-protective assertions and the realized_by_count counterpart of the existing realizing_count tests.

## Open questions

- None.

## Next consumer brief

Implementor (per iteration) should read these YAML fields first: `iterations[].scope_files` (hard diff boundary), `iterations[].validation_command` (what the tester will run), `iterations[].max_diff_lines` (budget), and `risks[]` (especially risks 2 and 3 — both are load-bearing for I2 correctness).

Cross-iteration invariants not derivable from the YAML alone:

1. I2 MUST NOT modify `summarize()` at storage.py:360. New fields are assigned on the returned summary AFTER the function returns, mirroring the existing realizing_count pattern at storage.py:795.
2. I2 MUST preserve `realizing_count` exactly. Both `realizing_count` AND `realized_by_count` are assigned on the same feature summary with the same value — neither replaces the other.
3. I2 lookup dict pattern is binding: `feature_key_by_id = {t.id: t.feature_key for t in self._by_id.values() if t.space_id == space_id and t.feature_key is not None}` for `feature_board()`; the same pattern (scoped or unscoped to match the calling context) is replicated in `board()` and `realizing_items()`.
4. I3 must test the R4 AC-3 missing-target path explicitly — create a task with `realizes` set to a UUID that does not exist in `self._by_id` and assert no exception is raised AND `realizes_feature_key` is None on its summary.

No open questions remain. Proceed to implementation; the tester will run each iteration's `validation_command` verbatim.
