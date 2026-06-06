# S1 — Data model: types + feature_state machine + numbering + realizes

**Title:** `Features&Fixes/S1 — model, feature_state, numbering, realizes` · **has_ui:** no

Extend `Task` model + storage (no API, no UI).
- models.py: add `"feature"`/`"fix"` to `TaskType`; new `FeatureState(str,Enum)` =
  `backlog/processing/planned/waiting/done`. Flat fields on `Task`/`TaskSummary`:
  `feature_state: FeatureState|None`, `feature_key: str|None` (`FEAT-001`), `realizes: str|None`,
  `issue_number: int|None`, `issue_url: str|None`, `proposed_issue_path: str|None` (mirror
  `pr_url`/`proposed_pr_path`).
- storage.py: `parse_file`/`dump_task` serialize the new keys (optional via `meta.get` → old files
  unchanged); **widen the type guards** (note 2). SQLite: add nullable cols
  `feature_state/feature_key/realizes` via the idempotent `ALTER TABLE ADD COLUMN` loop (~418-426) +
  index `idx_tasks_space_realizes(space_id, realizes)`; update **both** insert paths (`_db_upsert`
  ~437-455 and `reload_all` ~520-533).
- **Transition tables** (like storage.py:41-57): `FEATURE_USER_TRANSITIONS` (`backlog→processing`,
  `processing→backlog`, `planned→processing`, `waiting→processing`, `waiting→planned`, `planned→done`,
  `done→backlog`) and `FEATURE_WORKER_TRANSITIONS` (`processing→planned`, `processing→waiting`,
  `planned→waiting`, `waiting→planned`, `planned→done`). New `transition_feature(task_id, new_state,
  allowed)` — do **not** reuse `transition()`.
- `_next_feature_key(space_id, type)` = `max(existing per space+type)+1`, computed **inside `self._lock`**
  in `create()` (no counter file), zero-padded to 3.
- **Exclude feature/fix from `board()`/`counts_by_space()`** (note 1); add `feature_board(space_id)`
  (bucket by `feature_state`) + `realizing_items(feature_id)`.
- `set_realizes(item_id, feature_id|None)` (mirror `set_parent`) with a same-space + target-is-feature/fix
  guard (model on `validate_parent`).

**Scope files:** models.py, storage.py (+ optional `feature_state.py`).
**Acceptance:** creating a `feature` in a git-linked space → `feature_key=FEAT-001`,
`feature_state=backlog`, `state=backlog`, parseable MD + SQLite row; FEAT/FIX counters independent per
space; existing MD files load unchanged after `reload_all`; feature/fix excluded from `board()`; the
transition table is enforced; `set_realizes` rejects cross-space/non-feature targets.

---

## Standing Rules (apply to all phases)

**Branch:** all phase work commits to `feature/features-and-fixes` (from `main` if
missing; never branch from another base, never merge to `main`). Use [[goal-task-commit]]
after review passes.
**Locked design:** apply the parent goal's **Locked decisions** + **Locked design notes 1–7** verbatim
(reuse `Task` with `feature`/`fix`; `feature_state` machine; per-space `FEAT-`/`FIX-`; `realizes` field;
one-way `gh` mirror, MD canonical; git-linked only). No new SQLite tables (index columns only), no Redis,
no HTTP issue API.
**Test gate:** the pipeline's `test`+`review` phases gate — pytest (≥60%) and vitest/`tsc --strict`
must pass before `doc`; commit only on a `pass` verdict. **STATUS/gating** is owned by [[pipeline-gate]].

