---
cc_version: "1.0"
agent: pipeline-reviewer
slug: supersession--attempt1
phase: review
status: blocked
confidence: 0.88
inputs_used:
  - .cronos/pipeline/supersession/design-report-supersession.md
  - .cronos/pipeline/supersession/impl-report-supersession--i1.md
  - backend/app/models.py
  - backend/app/memory_store.py
  - backend/tests/test_memory_supersession.py
  - backend/app/api/memory.py
outputs_produced:
  - .cronos/pipeline/supersession/review-report-supersession--attempt1.md
blockers:
  - description: "I1 changed MemoryItem.links from list[str] to dict[str, Any] but left backend/app/api/memory.py request schemas (CreateMemoryBody.links, UpdateMemoryBody.links) typed as list[str]. POSTing/PUTting a memory with a non-empty links list now raises ValueError (HTTP 500) in MemoryStore.create() at `dict(links or {})`, and test_api_memory.py::test_roundtrip_full_item fails. The scoped change has an unscoped blast radius."
    severity: high
    suggested_resolution: "Scope-extend a fix iteration: change CreateMemoryBody.links to `dict[str, Any] = Field(default_factory=dict)` and UpdateMemoryBody.links to `dict[str, Any] | None = None` in backend/app/api/memory.py, and update test_api_memory.py::test_roundtrip_full_item to pass a dict (e.g. {'supersedes': ['mem-other']}). Re-run the review as attempt2."
next_consumer: implementation
metrics:
  tool_calls: 14
  files_read: 7
  memory_hits: 0
  diff_lines_reviewed: 287
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: high
    file: backend/app/api/memory.py:37
    evidence: "MemoryItem.links is now dict[str, Any] (models.py:377), but CreateMemoryBody.links / UpdateMemoryBody.links are still `list[str]`. memory.py:78 and :117 pass body.links straight into store.create()/update(), which run `dict(links or {})` (memory_store.py:257). A non-empty list triggers `ValueError: dictionary update sequence element #0 has length 9; 2 is required`. Confirmed: `pytest tests/test_api_memory.py::test_roundtrip_full_item` FAILS with that exact ValueError."
    blocking: true
    suggested_action: "Extend scope to backend/app/api/memory.py: retype both request-body `links` fields to dict[str, Any] (Create: default {}, Update: | None = None) and update test_api_memory.py::test_roundtrip_full_item to send a dict. Then re-review as attempt2. The design's I1 should have flagged api/memory.py as a downstream consumer of the field-type change."
  - id: F2
    severity: low
    file: .cronos/pipeline/supersession/impl-report-supersession--i1.md:8
    evidence: "impl-report inputs_used lists `.cronos/pipeline/trust-loop-supersession/architect-report-supersession.md` — that file/dir is the unrelated trust-loop feature's directory and the architect artifact is actually `design-report-supersession.md` in the `supersession/` dir. Provenance is mislabeled; the implementor consumed the correct design report (the implementation matches it exactly), only the citation path is wrong."
    blocking: false
    suggested_action: "Non-blocking. On the attempt2 impl pass, cite `.cronos/pipeline/supersession/design-report-supersession.md`. No code impact."
  - id: F3
    severity: low
    file: backend/app/memory_store.py:392
    evidence: "The working tree also carries the unrelated trust-loop changes (nudge_confidence() here, plus uncommitted trace_parser.py / worker.py / test_memory_trust_loop.py edits) interleaved with the supersession diff. These are out of this goal's scope_files and not claimed by the supersession impl-report; reviewed only for non-interference (none found). They are a commit-hygiene hazard for goal-task-commit, which must stage ONLY models.py + memory_store.py supersession hunks + test_memory_supersession.py."
    blocking: false
    suggested_action: "Non-blocking for correctness. At commit time, stage only the three supersession files/hunks so the trust-loop changes don't ride along on this goal's branch."
---

## Summary

The supersession feature is implemented correctly and meets every goal acceptance criterion at the memory-store layer, with disciplined scope: the implementor's `files_changed` (`models.py`, `memory_store.py`, `tests/test_memory_supersession.py`) is exactly the union of the design `iterations[].scope_files` — no scope escape. `detect_contradictions()`/`_detect_contradictions_locked()` correctly match on normalized-title equality AND body inequality (so identical re-writes are never archived), guard a missing `items/` dir, and glob `items/*.md` so `archive/` is excluded. The supersession block in `create()` runs entirely inside the existing `self._lock`, writes `links["superseded_by"]=new_id` into the old file while it is still in `items/`, then `os.replace()`s it into `archive/` (mirroring `prune_stale()`), accumulates `links["supersedes"]`, and — critically — `create()` ends with `rebuild_index(scope, _list_scope_locked(scope))`, so the archived item drops out of the retrieval index (R6 holds with no retrieval-code change, exactly as the design argued). Backward-compat coercion (`_load_item()` non-dict → `{}`) and dict round-trip (`_dump_item()` → `dict(item.links)`) are both present, addressing the design's two highest risks. All 10 tests in `test_memory_supersession.py` pass (the design's I1/I2/I3 validation commands all green).

The single blocking defect is a regression the design under-scoped: changing `MemoryItem.links` to `dict` (I1) broke the still-`list[str]`-typed request schemas in `backend/app/api/memory.py`. A memory write through the API with non-empty `links` now raises `ValueError` (HTTP 500), and `test_api_memory.py::test_roundtrip_full_item` fails. The implementor honestly surfaced this in `out_of_scope_findings` (high), but it is a real production regression, so it gates doc. Verdict: needs_fix.

## Findings

- **F1 (high, BLOCKING)** — `api/memory.py` request schemas still type `links` as `list[str]` after the model became `dict`; non-empty links → `ValueError`/500 in `create()`; `test_api_memory.py::test_roundtrip_full_item` fails. Reproduced live. Fix = retype both request fields to `dict[str, Any]` + update the test; re-review as attempt2.
- **F2 (low, non-blocking)** — impl-report `inputs_used` mislabels the design artifact path (`trust-loop-supersession/architect-report-...` instead of `supersession/design-report-...`). Citation-only; implementation matches the real design.
- **F3 (low, non-blocking)** — working tree interleaves unrelated trust-loop changes (`nudge_confidence`, `trace_parser.py`, `worker.py`) with the supersession diff; commit-hygiene hazard. Reviewed for non-interference — none found. Stage only the 3 supersession files at commit time.

## Verdict

needs_fix

The supersession logic, archiving, bidirectional links, and retrieval exclusion are all correct and tested. One blocking finding (F1) — a 500-error regression on the memory API introduced by the unscoped field-type change — must be fixed in a follow-up iteration before the pipeline advances to doc.

## Assumptions

- The binding scope contract is the design `iterations[].scope_files[]` union (`models.py`, `memory_store.py`, `tests/test_memory_supersession.py`); the goal slug is `supersession` and the canonical pipeline dir is `.cronos/pipeline/supersession/` per `pipeline-state.json` (the task brief's `trust-loop-supersession/` path is stale — that dir belongs to the already-merged trust-loop feature).
- "Non-contradicting writes proceed unchanged" (goal acceptance) is interpreted to include writes via the public memory API, not only direct `MemoryStore.create()` calls — which is why F1 is treated as blocking rather than a deferrable follow-up.
- `_load_item()` is a pure read; the archived old item leaving `items/` plus the `rebuild_index` call at the end of `create()` is the sole mechanism for retrieval exclusion (no `memory_retrieval.py` change was needed or made), matching the design's R6 argument and `test_retrieval_excludes_archived`.
- `dict([])` evaluates to `{}`, so the API regression manifests only for non-empty `links`; the empty-default path happens to survive, which is why the break is subtle rather than total.

## Open questions

- None. The fix for F1 is mechanical and fully specified; attempt2 should be a narrow scope-extension iteration.

## Next consumer brief

This review is BLOCKING — do not proceed to doc. Route back to the implementor for an attempt2 fix iteration scoped to:

1. `backend/app/api/memory.py` — `CreateMemoryBody.links: dict[str, Any] = Field(default_factory=dict)` and `UpdateMemoryBody.links: dict[str, Any] | None = None` (currently `list[str]` at lines 37 and 51).
2. `backend/tests/test_api_memory.py::test_roundtrip_full_item` — change the `links=["mem-other"]` payload to a dict (e.g. `links={"supersedes": ["mem-other"]}`) and assert the dict round-trips.

Verification for attempt2: `cd backend && pytest tests/test_memory_supersession.py tests/test_api_memory.py -q --override-ini="addopts="` must be fully green (currently 33 passed / 1 failed). Everything else in the supersession diff is correct and needs no rework — keep the `models.py`, `memory_store.py`, and `test_memory_supersession.py` changes as-is. At commit time, stage only the supersession files (F3) so the unrelated trust-loop working-tree changes do not ride along.
