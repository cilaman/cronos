---
cc_version: "1.0"
agent: pipeline-implementor
slug: supersession--i1
phase: impl
status: done
confidence: 0.88
inputs_used:
  - .cronos/pipeline/trust-loop-supersession/architect-report-supersession.md
  - .cronos/pipeline/trust-loop-supersession/scout-report-trust-loop-supersession.md
  - backend/app/models.py
  - backend/app/memory_store.py
  - backend/tests/test_memory_store.py
iteration_id: I1
files_changed:
  - backend/app/models.py
  - backend/app/memory_store.py
  - backend/tests/test_memory_supersession.py
validation_command: cd backend && pytest tests/test_memory_supersession.py -v --override-ini="addopts="
validation_command_passed: true
out_of_scope_findings:
  - description: "backend/app/api/memory.py defines CreateMemoryBody.links and UpdateMemoryBody.links as list[str]. After MemoryItem.links changed to dict[str, Any], passing a list via the API causes ValueError in memory_store.create() at dict(links or {}) because dict(['string']) is not valid. The test test_api_memory.py::test_roundtrip_full_item passes links=[\"mem-other\"] and will fail with ValueError. This needs a follow-up scope extension to update the API schemas and test."
    location: "backend/app/api/memory.py:37,51"
    severity: high
outputs_produced:
  - .cronos/pipeline/supersession/impl-report-supersession--i1.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 22
  files_read: 7
  memory_hits: 0
  diff_lines_added: 286
  diff_lines_removed: 7
---

## Summary

Implemented memory supersession (contradiction detection + archiving) across all three design iterations (I1–I3) in a single pass. I1 changed `MemoryItem.links` from `list[str]` to `dict[str, Any]` in `models.py`. I2 updated `memory_store.py`: backward-compatible `_load_item()` coercion (legacy `links: []` loads as `{}`), `dict(item.links)` serialization in `_dump_item()`, new `detect_contradictions()` + `_detect_contradictions_locked()` methods, and supersession logic in `create()` (archive contradicted items under the lock, set bidirectional `superseded_by`/`supersedes` links). I3 created `tests/test_memory_supersession.py` with 10 tests covering all acceptance paths. All 10 tests pass. One known regression in `backend/tests/test_api_memory.py::test_roundtrip_full_item` due to the API layer using `links: list[str]` (out-of-scope, documented in `out_of_scope_findings`).

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/models.py | modified | +2 / -1 | Add `Any` import; change `links: list[str]` to `dict[str, Any]` |
| backend/app/memory_store.py | modified | +61 / -6 | Dict serialization, legacy coercion, `detect_contradictions()`, supersession in `create()` |
| backend/tests/test_memory_supersession.py | created | +221 / 0 | 10 tests covering I1–I3 acceptance criteria |

## Out-of-scope findings

- `backend/app/api/memory.py:37,51` (high): `CreateMemoryBody.links: list[str]` and `UpdateMemoryBody.links: list[str] | None` still use the old list type. Passing a list to the updated `create()` causes `ValueError: dictionary update sequence element #0 has length 9; 2 is required` because `dict(["mem-other"])` is not valid. Also in `out_of_scope_findings[]` YAML. Follow-up: change these fields to `dict[str, Any]` and update `test_api_memory.py::test_roundtrip_full_item` accordingly.

## Assumptions

- All three design iterations (I1, I2, I3) were executed in a single pass; `iteration_id: I1` is the root iteration per the compound slug `supersession--i1`.
- The `detect_contradictions()` method is split into a public async wrapper (acquires lock) and a private sync helper (`_detect_contradictions_locked`) called inside `create()`'s existing lock to avoid deadlock.
- Contradiction matching uses normalized title equality (`strip().lower()`) plus body inequality — same title + same body is not a contradiction (per design, a re-write of identical content should not archive the original).
- The `archive/` directory is created with `mkdir(parents=True, exist_ok=True)` exactly as `prune_stale()` does, so no new directory semantics are introduced.
- The supersession block in `create()` runs before the new item is persisted, ensuring the archive move completes atomically within the existing lock.
- Scope files read before editing: all listed individually in `inputs_used[]`.

## Open questions

- None.

## Next consumer brief

Validation command: `cd backend && pytest tests/test_memory_supersession.py -v --override-ini="addopts="`

All 10 tests pass. Key edge cases exercised: legacy on-disk `links: []` coercion, dict round-trip with nested list, case-insensitive title matching, same-body non-contradiction, archived item excluded from `list_scope`.

**Priority finding for reviewer**: `backend/app/api/memory.py` uses `links: list[str]` in its request schemas — this causes `ValueError` in `create()` when the API passes a list. `test_api_memory.py::test_roundtrip_full_item` will fail in the full suite. A follow-up scope extension is needed to update the API schemas and test (files NOT in the current scope).
