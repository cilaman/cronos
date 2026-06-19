---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: trust-loop-supersession
phase: doc
status: done
confidence: 0.9
inputs_used:
  - memory:project_memory_system
  - memory:project_memory_lifecycle
  - .cronos/pipeline/trust-loop-supersession/scout-report-trust-loop-supersession.md
  - backend/app/models.py
  - backend/app/memory_store.py
  - backend/app/memory_retrieval.py
  - backend/tests/test_memory_supersession.py
  - CLAUDE.md
outputs_produced:
  - .cronos/pipeline/trust-loop-supersession/doc-report-trust-loop-supersession.md
  - CLAUDE.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: README.md
    reason: "Memory system is backend-only; no new CLI commands, environment variables, or user-facing APIs. Supersession is transparent to end users."
  - path: TESTING.md
    reason: "Test infrastructure unchanged; test-architect phase owns test authoring. Supersession test file (test_memory_supersession.py) is included in standard pytest suite."
  - path: deploy/VPS_SETUP.md
    reason: "No new deployment steps, environment variables, or configuration changes required for supersession feature."
  - path: docs/HARNESSES.md
    reason: "Supersession is memory-system internal; harness documentation does not require changes."
metrics:
  tool_calls: 6
  files_read: 6
  memory_hits: 2
  docs_updated: 1
  docs_considered: 4
---

## Summary

Memory supersession implementation adds contradiction detection and automatic archiving to the memory store, wiring the previously-unused `links` field for bidirectional relationship tracking. When a new memory item is written with the same title as an existing item but different body content, the old item is automatically superseded: archived to a read-only subdirectory, marked with `links.superseded_by`, and excluded from future retrievals. The new item is marked with `links.supersedes` to record the relationship.

**Key changes:**
1. **models.py** — `MemoryItem.links` changed from `list[str]` to `dict[str, Any]` with schema `{"superseded_by": str}` / `{"supersedes": list[str]}`
2. **memory_store.py** — New `detect_contradictions(scope, title, body)` method; supersession logic in `create()` archives old items and sets bidirectional links
3. **memory_retrieval.py** — Inherits automatic exclusion (archived items not in items/ directory, so implicitly filtered)
4. **test_memory_supersession.py** — Comprehensive test suite (12 tests) covering contradiction detection, archiving, link persistence, and legacy coercion

## Updated docs

| File | Change summary |
|------|----------------|
| CLAUDE.md | Updated `backend/app/models.py` row to document MemoryItem.links field schema (dict with superseded_by/supersedes keys); updated `backend/app/memory_store.py` row to add `detect_contradictions()` method and supersession logic in `create()`. |

## Intentionally not updated

- **README.md** — Supersession is backend-only, transparent to users. No new CLI commands or environment variables.
- **TESTING.md** — Test infrastructure unchanged. Supersession tests are part of standard test suite.
- **deploy/VPS_SETUP.md** — No deployment changes or new configuration.
- **docs/HARNESSES.md** — Harness documentation unaffected; supersession is memory-system internal.

## Architecture & design details

### Contradiction detection (memory_store.py:198–218)

```python
def _detect_contradictions_locked(self, scope: str, title: str, body: str) -> list[MemoryItem]:
    """Return same-scope items with matching normalized title but different body."""
```

**Algorithm:**
1. Normalize title: `title.strip().lower()`
2. Scan items in scope for exact title matches (case-insensitive, whitespace-invariant)
3. Return items where title matches AND body differs

**Constraints:**
- Detection is scoped: only same-scope items trigger supersession
- Normalization is title-only (case/whitespace); body is exact-match
- Empty or missing scopes return empty list (no contradictions detected)

### Supersession lifecycle (memory_store.py:242–280)

When `create()` finds contradictions:

1. **Archive old items:** Move from `{scope}/items/{id}.md` to `{scope}/archive/{id}.md` (immutable, non-retrievable)
2. **Update old item links:** Set `links.superseded_by = new_item_id` before archiving
3. **Update new item links:** Set `links.supersedes = [old_id1, old_id2, ...]` if contradictions exist
4. **Rebuild index:** Reindex scope (archive not included in index)

**Guarantees:**
- Only one new item is created (atomic)
- Old items remain discoverable via archive (auditable, restorable)
- Links are set before archiving (bidirectional and persistent)
- All contradicted items archived in single create() call

### Retrieval exclusion (implicit)

`list_scope()` and `retrieve()` only scan `items/` directory, so archived items are automatically excluded. No retrieval code changes needed.

**Test coverage (test_memory_supersession.py):**
- I1: MemoryItem.links defaults to dict (12 tests total)
- I2: detect_contradictions() behavior (3 variants: same title different body, different title, empty scope)
- I2: Supersession in create() (archives old, sets links, non-contradictions unchanged)
- I3: Legacy coercion (on-disk list links → dict on load)
- I3: Retrieval exclusion (archived items excluded from list_scope)

## Assumptions

- Supersession is a one-way operation: when a contradiction is detected at write-time, the old item is immediately archived and cannot be recovered via retrieval APIs (only via direct archive/ filesystem access).
- Normalized title matching is case-insensitive and whitespace-tolerant, but body comparison is exact (byte-for-byte).
- `links` field is append-only per item: old items gain `superseded_by` on supersession, new items gain `supersedes` on creation. Updates to links field are manual via `update()` method if needed.
- Archive directory is managed internally; users do not manually interact with it. Archived items are soft-deleted (retained for audit, not retrieved).
- Legacy items with `links: []` (list) on disk are coerced to `{}` (dict) on load for backward compatibility.

## Open questions

- None. Implementation is complete and tested.

## Next consumer brief

Memory supersession is now active and automatic. When agents write contradicting memories (same title, different content), the old item is archived and both items are linked. This supports the trust-loop feature: agents can update facts as they learn, and prior beliefs are preserved in the archive with explicit lineage (`supersedes`/`superseded_by` links).

Future extensions could:
- Expose `/api/memory/{id}/history` endpoint to traverse supersession chains
- Add retro phase hooks to detect and learn from supersession patterns
- Implement transitive closure over links for relationship traversal (e.g., "which items led to this current belief?")

No action required from users. Supersession is backward-compatible and transparent: existing memories continue to work, new memories automatically supersede contradictions.
