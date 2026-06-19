---
agent_mode: auto
agent_model: opus
claude_session_id: 83a7fd92-97da-4c7f-84ef-3aef95c92010
created_at: '2026-06-19T06:41:51Z'
depends_on:
- 2026-06-19-0641-test-supersession
feature_key: null
feature_state: null
id: 2026-06-19-0641-review-supersession
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-19-0641-supersession-contradiction-detection-arc
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: review – supersession
type: task
updated_at: '2026-06-19T08:37:00Z'
waiting_question: null
---

# Brief

CC-v1 review phase for: supersession – contradiction detection + archiving.

Scout report: `.cronos/pipeline/trust-loop-supersession/scout-report-trust-loop-supersession.md`
Agent contract: `.claude/agents/pipeline-reviewer.md`
Artifact output: `.cronos/pipeline/trust-loop-supersession/review-report-supersession--attempt1.md`

Feature scope:
- `backend/app/memory_store.py` — `detect_contradictions()` + supersession logic in `write_memory()`
- `backend/app/models.py` — `links` field schema (`superseded_by` / `supersedes`)
- `backend/tests/test_memory_supersession.py` — new tests covering contradiction detection, archiving, and retrieval exclusion


Then run: /pipeline-gate

# History

```
2026-06-19T08:03:19Z [agent]
I'll start by gathering the context I need to perform this review. Let me read the relevant files in parallel.

The existing artifacts describe the **trust-loop nudge** feature, not the **supersession** feature my brief asks me to review. Let me check whether the supersession implementation actually exists in the code.

The supersession feature appears unimplemented in this worktree. Given implementor agents often edit the **main worktree**, let me check there and review the full state.

The implementation is in the **main worktree** and there's a separate `supersession` pipeline dir. Let me read the design/impl reports and the actual code.

Now let me read the impl report and the actual implementation diff.

The implementor self-flagged a **HIGH severity** regression: the API layer (`api/memory.py`) still types `links` as `list[str]`, which now breaks. Let me examine the actual diff and verify the test impact.

Let me run the supersession tests and the at-risk API test to get ground truth on the regression.

Regression confirmed (`dict(["mem-other"])` → ValueError). Let me verify two more correctness points: whether `create()` rebuilds the index after archiving (so retrieval exclusion actually holds), and confirm the supersession tests genuinely cover exclusion.

`create()` does rebuild the index after archiving, so retrieval exclusion (R6) genuinely holds, and all 10 tests cover the acceptance paths. The feature itself is correct and well-tested. The one real defect is the API-layer regression.

Let me confirm the pipeline state/dir the gate tracks, so I write the artifact where the gate will look.

goal_slug is `supersession` and the dir is `.cronos/pipeline/supersession/` — the gate resolves there (the brief's `trust-loop-supersession` path is stale). Before I finalize the verdict, let me confirm how the verifier/gate treats a non-pass review verdict so my report drives the correct gate outcome.

Let me read the full review check logic and schema to set `status`/`verdict` coherently so the gate escalates (BLOCKED) rather than proceeding to doc.

I now have full ground truth. Let me write the review report to the canonical path the gate resolves (`.cronos/pipeline/supersession/`, goal_slug `supersession` — the brief's `trust-loop-supersession` path is stale).

**Verdict reasoning:** The supersession feature itself is correctly implemented, scope-clean (3 files == design `scope_files`), and all 10 in-scope tests pass. But the I1 type change (`MemoryItem.links: list[str] → dict`) has an unscoped blast radius: `api/memory.py` still types request `links` as `list[str]`, so `create()`'s `dict(links or {})` raises `ValueError` (HTTP 500) on any non-empty links write — a reproducible production regression that breaks `test_api_memory.py::test_roundtrip_full_item`. That's a blocking finding → `needs_fix`, `status: blocked` so the gate escalates instead of advancing to doc.

Now let me verify the report passes the CC-v1 verifier before invoking the gate.

Verifier passes with `outcome: escalate, exit_code: 2` — exactly the intended signal: the report is valid, and `status: blocked` escalates the gate to BLOCKED so the DAG halts for the F1 fix iteration before doc. Now running the gate.

Now I'll execute the gate steps. Step 2 — normalize + verify:

VERIFY_EXIT=2 (escalate), artifact valid, no errors. Step 3 — record state via state_writer:

Gate recorded: **ESCALATE / BLOCKED** for the review phase. Phase is not `retro`, so Steps 3b/3c are skipped. Verify exit was 2 (escalate), PY exit 0 → BLOCK path.

## Review complete — verdict: `needs_fix` (gate BLOCKED)

**What I reviewed.** The `supersession` feature (contradiction detection + archiving) implemented in the main worktree. Note: the task brief pointed at `.cronos/pipeline/trust-loop-supersession/`, but the live goal slug is `supersession` and its artifacts/state live in `.cronos/pipeline/supersession/` (the `trust-loop-supersession` dir belongs to the already-merged trust-loop feature). I reviewed against the correct goal dir.

**What's correct (no rework needed):**
- Scope-clean: implementor's `files_changed` == design `scope_files` (`models.py`, `memory_store.py`, `tests/test_memory_supersession.py`).
- `detect_contradictions()` matches on normalized-title equality **AND** body inequality (identical re-writes never archived); guards missing `items/` dir.
- Supersession runs entirely under `self._lock`, sets bidirectional `superseded_by`/`supersedes`, `os.replace`s the old item into `archive/`, and `create()`'s closing `rebuild_index` drops it from retrieval (R6 holds with no retrieval-code change).
- Legacy `links: []` coercion and dict round-trip both present. All 10 supersession tests pass.

**Blocking finding F1 (high).** I1 changed `MemoryItem.links` from `list[str]` → `dict[str, Any]`, but `backend/app/api/memory.py` still types the request bodies' `links` as `list[str]`. A non-empty links write through the API now raises `ValueError` (HTTP 500) in `create()` at `dict(links or {})`. I reproduced it live: `test_api_memory.py::test_roundtrip_full_item` fails (33 passed / 1 failed). The implementor honestly self-flagged this as out-of-scope, but it's a real production regression, so it gates doc.

**Fix for attempt2 (mechanical):** retype `CreateMemoryBody.links` → `dict[str, Any]` and `UpdateMemoryBody.links` → `dict[str, Any] | None` in `api/memory.py`, update that one test to send a dict, then re-review. Two low non-blocking notes (F2: impl-report mis-cites the design path; F3: stage only the 3 supersession files at commit time so unrelated trust-loop working-tree changes don't ride along) are in the report.

The verifier validated the report (no schema/R-rule errors); `status: blocked` correctly escalates the gate so the DAG halts before doc.

Artifact: `.cronos/pipeline/supersession/review-report-supersession--attempt1.md`

gate BLOCKED — review / supersession (verify exit 2, escalate; verdict=needs_fix, blocking finding F1)

STATUS: BLOCKED
```

```
2026-06-19T08:32:15Z [user]
Implement fixes
```

```
2026-06-19T08:35:09Z [agent] run=1 model=claude-opus-4-8 mode=auto
I'll implement the F1 fix in the main worktree where the supersession diff lives. Let me read the relevant files first.

`Any` is already imported. Let me fix both schemas.

Now the test. Let me find the `links` usage in `test_roundtrip_full_item`.

Now let me verify the fix and check for any other consumers of `links`-as-list.

All 34 pass (was 33/1). No other `links`-as-list consumers remain. Let me run the broader memory-related suite to confirm no regressions from the type change.

All 441 memory/trace/worker tests pass. The schema change touches shared API/model surface, so let me run the full backend suite to be certain nothing else regressed.

Done. The blocking finding F1 is fixed and verified.

## Fixes implemented

**F1 (blocking) — API-layer `links` type mismatch.** In `backend/app/api/memory.py`:
- `CreateMemoryBody.links`: `list[str]` → `dict[str, Any] = Field(default_factory=dict)`
- `UpdateMemoryBody.links`: `list[str] | None` → `dict[str, Any] | None = None`

And updated `backend/tests/test_api_memory.py::test_roundtrip_full_item` to round-trip a dict (`{"supersedes": ["mem-other"]}`) instead of a bare list.

## Verification

- `test_api_memory.py` + `test_memory_supersession.py`: **34 passed** (was 33/1 — the previously-failing `test_roundtrip_full_item` now passes; the `ValueError`/500 regression is gone).
- Memory/trace/worker subset: **441 passed**.
- Full backend suite: **2595 passed, 1 failed** — the single failure is `test_features_routes_registered`, the pre-existing, unrelated failure already documented on `main` (no connection to `links`; my change only touched the memory API/test). No new regressions.

F2 (impl-report mis-citation) and F3 (commit hygiene — stage only the supersession files) were non-blocking process notes, not code defects, so there's nothing to change in source for those; F3 remains a reminder for whoever runs `goal-task-commit` so the unrelated trust-loop working-tree changes don't ride along.

The supersession feature is now complete with no known regressions. If you'd like, I can re-run the review gate as attempt2 to formally clear it for the doc phase.
```
