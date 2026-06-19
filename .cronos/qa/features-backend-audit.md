# Features Backend Audit

**Date:** 2026-06-07
**Auditor:** backend-features-audit task (goal `2026-06-07-1049-backend-features-and-fixes-deep-qa-review`)
**Scope:** `backend/app/feature_state.py`, `backend/app/api/features.py`, `backend/app/feature_sync.py`, `backend/app/feature_hooks.py`, `backend/app/storage.py` (feature methods), `backend/app/models.py` (Feature* schemas), `backend/app/worker.py::_run_feature_decompose`.

This audit walks the 10 specific risks called out in the task brief (A–J) and a handful of adjacent findings surfaced during reading. Each finding cites the file + line(s) where the issue lives.

---

## Critical Issues (P0 — breaks production)

_None of the audited paths crash production unconditionally._ The known
"missing storage method" risk from the goal brief is real but contained by an
`except AttributeError` in the only caller; see **F1** in P1.

---

## High Priority Issues (P1 — feature incomplete)

### F1. `set_feature_waiting_question` is called but never defined (A)

- **Where called:** `backend/app/feature_sync.py:100`
  ```python
  await store.set_feature_waiting_question(feature_id, waiting_q)
  ```
- **Where defined:** nowhere in `backend/app/storage.py`. `grep set_feature_waiting_question backend/app` returns three hits — the call (line 100) and two comments inside the `except AttributeError` block (lines 108, 111).
- **Why it does not crash today:** the call sits inside a `try` that explicitly catches `AttributeError` (`feature_sync.py:107-115`) and downgrades to a `log.debug` line. So a feature *does* transition `PLANNED → WAITING` cleanly; the question is silently dropped.
- **Why this is still P1:** the design intent (per the surrounding comments and the goal-brief memory) is that the realizing goal's `waiting_question` should surface on the feature card. Today it does not — the feature lane shows a `WAITING` card with no blocking question. Combined with **F2** below (FeatureRead does not expose `waiting_question` at all), this means the user has no way to see *why* a feature is blocked.
- **Recommended fix (sketch):**
  - Add an `async def set_feature_waiting_question(self, task_id: str, question: str | None) -> Task` method to `TaskStore` that takes the lock, validates `task.type in ("feature","fix")`, atomically writes `task.waiting_question`, and re-indexes.
  - Remove the `except AttributeError` graceful path in `feature_sync.py:107-115` — silent absence of a contract method is a worse failure mode than a stack trace.

### F2. `FeatureRead` omits `waiting_question` (J)

- **Where:** `backend/app/models.py:199-223`. The schema lists `id, space_id, title, state, created_at, updated_at, brief, priority, manual_order, type, parent_id, depends_on, pr_url, proposed_pr_path, feature_state, feature_key, realizes, issue_number, issue_url, proposed_issue_path, realizing_items`. `waiting_question` is **not** included.
- **Why this matters:** the worker *does* persist a meaningful waiting question on a feature task — `worker.py:597-600` (`_run_feature_decompose`) calls `store.finalize_run(... waiting_question=waiting_question ...)` with one of five derived strings ("Decomposition agent crashed", "Decomposition blocked", `result.context`, etc.). That value lives on `Task.waiting_question` but never reaches the frontend through `FeatureRead`.
- **Recommended fix:** add `waiting_question: str | None = None` to `FeatureRead` (models.py:199) and copy it through in `_build_feature_read` (api/features.py:91-96 — the `model_dump` spread already passes it through once the schema accepts it).

### F3. `process_feature` re-fires mirror + decomposition when feature is already PROCESSING (C)

- **Where:** `backend/app/api/features.py:330-368` (handler) + `backend/app/storage.py:861-862` (early-return inside `transition_feature`).
- **Root cause:** `transition_feature` short-circuits silently when `current_feature_state == new_feature_state`:
  ```python
  current_feature_state = task.feature_state
  if current_feature_state == new_feature_state:
      return task
  ```
  No `InvalidTransition` is raised. The endpoint then unconditionally runs:
  ```python
  _fire_mirror(updated_task, space, "state_change")
  await enqueue_feature_decomposition(updated_task)
  ```
- **Observable bug:** POST `/api/features/{id}/process` on an already-PROCESSING feature:
  1. Returns 200 (not 409, despite the docstring claim on line 337).
  2. Fires a second GitHub mirror call (extra rate-limit hit; minor).
  3. Enqueues a second decomposition agent run on the same task. The worker pool's `enqueue` (`worker_pool.py:93-99`) blindly forwards to `worker.enqueue(task_id)` with no de-dup. If the prior run is still mid-flight, the second run will execute right after and may double-create realizing items, doubling the goal tree.
- **Even more concerning:** `PLANNED → PROCESSING` *is* a legal user transition. A user re-clicking "Process" on a feature that already has realizing items will spawn another decomposition on top of the existing tree.
- **Recommended fix:** in `process_feature`, before calling `transition_feature`, refuse early if `task.feature_state == FeatureState.PROCESSING` (return 409 with "Feature is already being processed") and additionally guard against `PLANNED` having pre-existing realizing items (or document and accept the "re-decompose" semantics explicitly). Alternatively, change `transition_feature` to raise `InvalidTransition` on no-op transitions instead of silently returning — but that has wider blast radius.

### F4. `validate_realizes` only prevents 1-hop self-cycles (D)

- **Where:** `backend/app/storage.py:202-230`.
- **What it does cover:** `feature_id == item_id` (1-hop self ref, line 220-221); target existence; same-space; target type ∈ {"feature","fix"}.
- **What it does NOT cover:** longer cycles. Nothing prevents feature `A.realizes = B`, `B.realizes = C`, `C.realizes = A`. The realizes pointer is single-valued so there is at most one outgoing edge per node, but cycles of length ≥ 2 are still constructible if the *target* is itself a feature/fix.
- **Why this matters less than depends_on cycles:** the propagation code (`feature_sync.py::_find_root`, line 233-250) walks `parent_id` not `realizes`, and `realizing_items` is a single-hop reverse scan. So a cycle does not cause a real infinite loop today.
- **Adjacent design smell:** `validate_realizes` permits a *feature* to realize another *feature*. Reading the rest of the system (worker decomposes a feature into goals/tasks; UI surfaces realizing items under a feature card) suggests realizes is intended as "task realizes feature", not "feature realizes feature". Worth confirming product intent and locking it down.
- **Recommended fix (low cost):** add a BFS cycle check mirroring `_dep_cycle_path` (storage.py around line 197) but walking the `realizes` field. And/or reject `item.type in ("feature","fix")` outright if the product intent is "tasks realize features, full stop".

---

## Medium Priority Issues (P2 — quality/reliability)

### F5. `patch_feature_state` returns 404 for "space not found" even though the task exists (I)

- **Where:** `backend/app/api/features.py:223-225` (and the same pattern in `patch_feature`, `process_feature`).
  ```python
  space = space_store.get(task.space_id)
  if space is None:
      raise HTTPException(status_code=404, detail=f"Space {task.space_id} not found")
  ```
- **Why it's odd:** the task already exists with a `space_id` field, which by storage invariants means the space exists on disk. The 404 here is functionally unreachable in steady state but if it ever fires (data corruption, race with space delete) the response will mislead a client into thinking the *feature_id* is bad. A 500 with a clear "data invariant violated" message would be more honest.
- **Recommended fix:** either drop the check (and trust the invariant) or raise a 500 with a clearer message — do not return 404 for an unreachable internal state.

### F6. `transition_feature` silently no-ops on same-state transitions (cross-cutting; underlies F3)

- **Where:** `backend/app/storage.py:861-862`.
- **Symptom:** callers cannot distinguish "transition succeeded" from "no-op because already in target state". This is the root cause of F3 above and also means `feature_sync.py` propagation can fire spurious `_fire_mirror` calls upstream if a future caller ever wraps it.
- **Today the only callers are:**
  - `api/features.py::patch_feature_state` (correctness depends on user-initiated transitions being non-no-op — usually fine; but a double-PATCH to the same state will fire two mirrors).
  - `api/features.py::process_feature` (broken — see F3).
  - `feature_sync.py::propagate_to_feature` (uses worker transitions; idempotent races are OK here).
  - `worker.py::_run_feature_decompose` (fires once per decomposition run).
- **Recommended fix:** add a "treat-as-error" mode or return a sentinel from `transition_feature` so callers can choose to raise when current == new. Lowest-risk path: keep the silent return, but have `process_feature` explicitly guard `if task.feature_state == FeatureState.PROCESSING: raise HTTPException(409, ...)` (see F3 fix).

### F7. `feature_state` filter on `feature_board` silently drops malformed features

- **Where:** `backend/app/storage.py:762-763`.
  ```python
  if task.feature_state is None:
      continue
  ```
- **Why it matters:** any feature/fix task that lost its `feature_state` (e.g. hand-edited markdown, partial migration) silently disappears from the board. There is no log line, no alert. Combined with F8 below (storage allows a feature to be created via legacy `store.create` paths that don't set `feature_state`), this is a low-likelihood-high-recovery-cost data loss path.
- **Recommended fix:** log at WARNING for any feature/fix that has `feature_state is None` so the operator notices a malformed task; optionally surface them in a "needs attention" bucket.

### F8. `update` allows changing `type` to feature/fix without setting `feature_state` or `feature_key`

- **Where:** `backend/app/storage.py:934-976`. `update(... type='feature' ...)` will flip the type but never allocate a `feature_key` or set an initial `feature_state`. Only `create()` (line 904-908) populates those fields.
- **Why it matters:** an API caller that promotes a task to a feature via PATCH /api/tasks (if such a path exists or is added) would create a feature in invalid state — invisible on the feature board (F7), no FEAT-NNN key, etc.
- **Recommended fix:** either reject `type` changes to "feature"/"fix" in `update`, or initialize `feature_key`/`feature_state` symmetrically with `create`.

### F9. Mirror error handling is broad — masks programming errors

- **Where:** `backend/app/feature_hooks.py:195-201`.
  ```python
  except Exception as exc:  # noqa: BLE001
      log.warning("mirror_feature_to_github: task=%s reason=%s error=%r", task.id, reason, exc)
  ```
- **Why it matters:** the broad-except is documented as deliberate (R8) and is paired with a fire-and-forget call site that also logs failures. But typos in attribute access (e.g. `task.feture_key`) get swallowed at WARNING. A second log channel routed to a structured store (or at least `log.exception` with `exc_info=True` so the stack trace makes it into the log) would help diagnose silent mirror failures.
- **Recommended fix:** use `log.exception(...)` (or `log.warning(..., exc_info=True)`) so the traceback is captured.

### F10. `_fire_mirror` uses a bare `# type: ignore[arg-type]` to paper over Task vs ABC mismatch

- **Where:** `backend/app/api/features.py:86`.
  ```python
  coro = mirror_feature_to_github(task, space=space, reason=reason)  # type: ignore[arg-type]
  ```
- **Why it matters:** the ignore comment masks a real or perceived type mismatch. If it is a real mismatch, the call could blow up at runtime if Pydantic strictness ever changes. If it is a false positive, the comment is misleading.
- **Recommended fix:** remove the ignore and resolve the mismatch (likely just a forward-ref / TYPE_CHECKING import gap).

---

## Low Priority / Future Work (P3)

### F11. `DELETE /api/features/{id}` is a 501 stub (B)

- **Where:** `backend/app/api/features.py:371-374`. Returns `_NOT_IMPLEMENTED` (`JSONResponse(status_code=501, ...)`).
- **Status:** by design — docstring says "soft-delete / archive feature (future iteration)". `TaskStore.delete` (storage.py:1361-1376) exists and does soft-delete via `.trash/` for ordinary tasks; wiring it up for features is straightforward, but the team apparently wanted to keep the API contract honest with a 501 rather than a half-implementation. **Frontend audit task should verify the UI hides or disables the delete affordance for features.**
- **Recommended fix:** decide whether to wire `store.delete` (with the realizing-items cleanup question: do realizing tasks lose their link? become orphaned? become tasks-without-features?) or formally remove the route until a design exists.

### F12. `proposed_issue_path` is persisted but never used in a fallback render

- **Where:** `backend/app/feature_hooks.py:148-179`. The MD fallback is written to `.cronos/issues/{task.id}.md` before any `gh` call. If `gh` fails, `proposed_issue_path` is set. **Frontend audit** should verify whether the UI surfaces this so the user can see "your gh CLI isn't configured, here's the issue MD we drafted".

### F13. `_DATE_PREFIX_RE` in feature_sync.py is duplicated logic

- **Where:** `backend/app/feature_sync.py:22`.
- **Why:** task id format (`YYYY-MM-DD-HHMM-slug`) is centralized in `storage.generate_task_id`. The regex here re-parses it to derive a branch name. If the id format ever changes, two places must move together.
- **Recommended fix:** add a `slug_from_task_id(task_id) -> str` helper to `storage.py` and use it here.

### F14. `_find_root` cap of 50 hops is generous but undocumented in the user surface

- **Where:** `backend/app/feature_sync.py:240-250`.
- **Why:** 50 hops is fine for any realistic goal tree, but if a deeper tree ever appears the warning log line is the only signal and the propagation silently no-ops. Consider raising a typed error or a metric.

### F15. `_NOT_IMPLEMENTED` is a module-level singleton — reused across calls

- **Where:** `backend/app/api/features.py:103-106`. The `JSONResponse` is created once at import time and returned by reference. FastAPI is fine with this today, but a future Starlette change that mutates response state per-call would break it. Cheap fix: build it inside the handler.

---

## What Works Well

- **`_fire_mirror` funnel pattern (api/features.py:60-88).** Concentrating every mirror invocation in one helper enforces R13 (single fire per mutating endpoint) and makes call-count assertions in tests deterministic. The fire-and-forget with `add_done_callback` for error logging is the right shape.
- **State-machine module separation (`feature_state.py`).** Tables live in a tiny pure data module; storage and worker import the same frozensets, so there is zero risk of the two layers disagreeing on what is legal. Comment at line 4-6 ("Never import from app.storage here") prevents the circular dependency cleanly.
- **Per-(space, type) FEAT/FIX counter with lock-protected create() (storage.py:773-815 + 902-927).** The whole critical section runs under `self._lock`, so race-free counter allocation is guaranteed without any database-level sequence. The per-type filter (line 800-802) means FEAT-NNN and FIX-NNN advance independently — the obvious right call.
- **`feature_board` correctness for empty/missing state (storage.py:749-769).** The "skip feature_state=None" guard is defensive (see F7 caveat) but does prevent KeyError when bucketing.
- **Zero-items guard in done-detection (feature_sync.py:144-151).** Explicit early-return prevents a feature from auto-transitioning to DONE before any realizing item is linked. Combined with the branch-presence check (feature_sync.py:182-191), the done detection is appropriately conservative.
- **MD fallback ordering in mirror (feature_hooks.py:146-148).** Writing the markdown fallback *before* invoking `gh` (R6) means a `gh` crash never leaves the user with no record.
- **`enqueue_feature_decomposition` graceful degradation (feature_hooks.py:227-237).** When `_worker_pool` is None (test isolation), logs a WARNING instead of raising — keeps unit tests of the API layer simple.
- **`transition_feature` enforces type guard (storage.py:851-855).** Cannot transition a non-feature/non-fix task even by passing the right state value. Defense-in-depth.
- **`validate_realizes` blocks cross-space links (storage.py:222-226).** A task in space A cannot realize a feature in space B.
- **Decomposition outcome branches in `_run_feature_decompose` (worker.py:548-584).** Five distinct outcome paths each with a meaningful `waiting_question` — the user surface (modulo F2 above) is well-considered.

---

## Summary Table

| # | Issue | Severity | File:Line | Recommendation |
|---|-------|----------|-----------|----------------|
| F1 | `set_feature_waiting_question` undefined; `except AttributeError` silently drops `waiting_q` | P1 | `feature_sync.py:100`; missing in `storage.py` | Implement the method; remove the AttributeError swallow |
| F2 | `FeatureRead` does not expose `waiting_question` | P1 | `models.py:199-223` | Add `waiting_question: str \| None = None` |
| F3 | `process_feature` double-fires when state already PROCESSING (no-op transition + mirror + enqueue) | P1 | `api/features.py:354-366` + `storage.py:861-862` | Explicit 409 guard in `process_feature`; also reconsider re-process-from-PLANNED semantics |
| F4 | `validate_realizes` only blocks 1-hop self-cycles; no longer-cycle check | P2 | `storage.py:202-230` | BFS realize-cycle check; consider banning feature→feature realizes |
| F5 | 404 returned for unreachable "space not found" after task lookup succeeds | P2 | `api/features.py:223-225` (and twin sites) | Drop the check or raise 500 |
| F6 | `transition_feature` no-ops silently on same-state | P2 | `storage.py:861-862` | Return sentinel or let callers raise |
| F7 | `feature_board` silently hides features with `feature_state=None` | P2 | `storage.py:762-763` | Log a WARNING |
| F8 | `update` allows type→feature/fix without `feature_key`/`feature_state` init | P2 | `storage.py:934-976` | Reject or initialize symmetrically with `create` |
| F9 | Mirror broad-except uses `log.warning` without `exc_info` | P2 | `feature_hooks.py:195-201` | Use `log.exception` or `exc_info=True` |
| F10 | `_fire_mirror` carries a bare `# type: ignore[arg-type]` | P2 | `api/features.py:86` | Resolve the type mismatch |
| F11 | DELETE returns 501 stub | P3 | `api/features.py:371-374` | Wire `store.delete` or remove the route until a design exists |
| F12 | `proposed_issue_path` persisted but UI fallback unclear | P3 | `feature_hooks.py:174-179` | Verify in frontend audit |
| F13 | `_DATE_PREFIX_RE` duplicates task-id structural knowledge | P3 | `feature_sync.py:22` | Centralize a `slug_from_task_id` helper |
| F14 | `_find_root` 50-hop cap silently no-ops on overflow | P3 | `feature_sync.py:240-250` | Typed error or metric |
| F15 | `_NOT_IMPLEMENTED` singleton response shared across calls | P3 | `api/features.py:103-106` | Build per-request |

---

## Audit checklist (A–J → resolution)

| Brief ref | Question | Outcome |
|-----------|----------|---------|
| A | Does `set_feature_waiting_question` exist on `TaskStore`? | **No** — see F1. Not P0 (AttributeError caught), but P1 (silent data loss). |
| B | Does DELETE return 501? Plan? | **Yes 501** — see F11. No visible plan; deferred. |
| C | Does `process_feature` guard against double-processing? | **No** — see F3. P1 bug with multi-spawn risk. |
| D | Does `validate_realizes` prevent circular references / self-realize? | **Self-realize: yes** (1-hop). **Multi-hop cycles: no.** **Task realizes task: rejected** by target-type check. See F4. |
| E | Is GitHub mirror purely fire-and-forget? Behavior on missing remote? | **Yes** (`_fire_mirror` + `asyncio.create_task`); `gh_issue_upsert` returns `(None, None)` when no remote and MD fallback is persisted. Logs at WARNING. Works well; see F9 for log-detail nit. |
| F | Does `propagate_to_feature` handle done-detection edge cases (empty realizing_items, non-PLANNED feature)? | **Yes** — explicit zero-items guard (line 144-151) and PLANNED-only guard (line 140-142). Feature stays PLANNED rather than incorrectly transitioning to DONE. |
| G | Are FEAT-NNN / FIX-NNN counters space-isolated and race-safe? | **Yes** — per-(space, type) filter + `self._lock` covering both `_next_feature_key` and the write. See "What Works Well". |
| H | Are there stuck-states in `FEATURE_USER_TRANSITIONS` / `FEATURE_WORKER_TRANSITIONS`? | **No reachability gaps found.** PROCESSING resolves to BACKLOG (user) / PLANNED or WAITING (worker). WAITING resolves to PLANNED or PROCESSING. DONE re-opens via DONE→BACKLOG. Note: DONE→PROCESSING requires DONE→BACKLOG→PROCESSING (UX nit, not a stuck state). |
| I | 404 / 422 / 409 returned consistently? | **Mostly yes.** 404 for unknown features (consistent). 409 for invalid feature-state transitions. 400 for `validate_realizes` failures and for git_repo_url=None on POST. 422 from Pydantic and explicit on missing `space_id` query param. See F5 for one over-eager 404. |
| J | Does `FeatureRead` include all fields a detail panel needs? | **realizing_items / feature_key / issue_number / issue_url / proposed_issue_path: yes. waiting_question: NO** — see F2. |
