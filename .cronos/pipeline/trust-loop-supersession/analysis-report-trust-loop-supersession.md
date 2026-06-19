---
cc_version: "1.0"
agent: pipeline-analyst
slug: trust-loop-supersession
phase: analysis
status: done
confidence: 0.9
inputs_used:
  - memory:project-memory-system
  - memory:project-memory-lifecycle
  - .cronos/pipeline/trust-loop-supersession/scout-report-trust-loop-supersession.md
  - backend/app/memory_store.py
  - backend/app/models.py
outputs_produced:
  - .cronos/pipeline/trust-loop-supersession/analysis-report-trust-loop-supersession.md
blockers: []
next_consumer: design
request: "Wire the unused links field for memory supersession. On memory write, scan
  existing memories in the same scope for contradictions (same key/name/slug with
  different content). When a contradiction is detected, archive the old memory and
  set bidirectional links: old memory gets links.superseded_by = new_id, new memory
  gets links.supersedes = [old_id]."
has_ui: false
coverage_summary:
  searched:
    - backend/app/memory_store.py
    - backend/app/models.py
  excluded:
    - frontend/: backend-only feature — no UI surface for supersession
    - deploy/: no deployment changes needed
  strategies:
    - memory_retrieval
    - read_targeted
    - grep_symbol
traceability:
  - requirement_id: R1
    statement: "MemoryItem.links field type is changed from list[str] to dict supporting
      optional keys superseded_by (str, set on archived items) and supersedes
      (list[str], set on new items that replace archived ones)."
    acceptance_criteria:
      - "Given a newly created MemoryItem, links defaults to {} (empty dict, not empty list)."
      - "Given a superseded item, item.links['superseded_by'] equals the new item's ID."
      - "Given a superseding item, item.links['supersedes'] is a list containing all archived item IDs."
      - "MemoryStore serialization round-trips links as a dict through frontmatter I/O."
    verifying_phase: test
    confidence: 0.9
  - requirement_id: R2
    statement: "MemoryStore exposes detect_contradictions(new_item) that returns existing
      non-archived items in the same scope whose title matches the new item's title
      (case-insensitive, stripped) but whose body differs."
    acceptance_criteria:
      - "Given item A in scope S with title 'Foo' and body 'X', when detect_contradictions
        is called with title='foo' and body='Y', then A is returned."
      - "Given item B with the same title AND the same body as new_item, B is NOT returned
        (same-content items are not contradictions)."
      - "Given item C in a different scope than new_item, C is NOT returned."
      - "Given item D with a different title than new_item, D is NOT returned."
      - "Items already in the archive/ subdir are NOT returned."
    verifying_phase: test
    confidence: 0.9
  - requirement_id: R3
    statement: "MemoryStore.create() calls detect_contradictions() before persisting
      the new item; when contradictions are found, each contradicted item is archived
      (moved to archive/) and its links['superseded_by'] is set to the new item's ID."
    acceptance_criteria:
      - "Given an existing item A with title 'T' and body 'X', when create() is called
        with title='T' and body='Y', then A's file is moved to archive/."
      - "The archived item A has links['superseded_by'] equal to the new item's ID."
      - "The archiving is atomic: A is updated with the superseded_by link before being
        moved to archive/."
    verifying_phase: test
    confidence: 0.9
  - requirement_id: R4
    statement: "The new item returned from create() has links['supersedes'] containing
      the IDs of all items that were archived due to contradiction."
    acceptance_criteria:
      - "Given create() supersedes N>=1 existing items, new_item.links['supersedes']
        is a list of N IDs."
      - "Given create() supersedes 0 items (no contradiction), new_item.links is {} or
        missing the 'supersedes' key."
    verifying_phase: test
    confidence: 0.9
  - requirement_id: R5
    statement: "Non-contradicting writes proceed unchanged: create() does not archive
      or mutate any existing items when there is no title match, or when title matches
      but body is identical."
    acceptance_criteria:
      - "Given no existing item with the new item's title in scope, create() stores
        the new item without archiving anything."
      - "Given an existing item with the same title AND same body as new_item, create()
        stores the new item but does NOT archive the existing one (idempotent re-write)."
    verifying_phase: test
    confidence: 0.95
  - requirement_id: R6
    statement: "Archived (superseded) memory items are excluded from retrieval results:
      memory_retrieval.retrieve() and MemoryStore.list() do not surface items stored
      under archive/."
    acceptance_criteria:
      - "Given item A has been superseded and moved to archive/, when retrieve() is
        called with a query matching A's title, A is not in the returned list."
      - "Given MemoryStore.list(scope) is called, items in archive/ are not included."
    verifying_phase: test
    confidence: 0.9
  - requirement_id: R7
    statement: "A new test file backend/tests/test_memory_supersession.py covers all
      acceptance criteria: contradiction detection, archiving, bidirectional links,
      retrieval exclusion, and non-contradicting passthrough."
    acceptance_criteria:
      - "File exists at backend/tests/test_memory_supersession.py."
      - "test_detect_no_contradiction: different title or same body → empty result."
      - "test_detect_contradiction: same title, different body → returns existing item."
      - "test_create_supersedes_archives_old_item: old item moved to archive/."
      - "test_create_supersedes_sets_links: archived item has superseded_by, new item has supersedes."
      - "test_create_non_contradiction_unchanged: no archiving on clean write."
      - "test_retrieval_excludes_archived: archived items absent from retrieve() results."
    verifying_phase: test
    confidence: 0.9
metrics:
  tool_calls: 10
  files_read: 5
  memory_hits: 2
---

## Summary

This feature wires the currently unused `links` field on `MemoryItem` for bidirectional supersession tracking. When a memory item is written whose `title` matches an existing item in the same scope but whose `body` differs, the existing item is archived and bidirectional links are set: the archived item gets `links["superseded_by"] = new_id` and the new item gets `links["supersedes"] = [old_id]`. This enables the memory store to self-curate over time — contradictory facts are retired without deletion, preserving audit history in `archive/`. Non-contradicting writes and same-content re-writes proceed unchanged. The feature is entirely backend-only, requiring changes to `models.py` (schema), `memory_store.py` (logic), and a new test file.

## Scope

### In scope
- `MemoryItem.links` field type change from `list[str]` to `dict` with optional `superseded_by` / `supersedes` keys
- `MemoryStore.detect_contradictions(new_item)` method (same-scope, same-title, different-body detection)
- `MemoryStore.create()` supersession logic: archive old items and set bidirectional links
- Archival mechanism reusing the existing `archive/` subdir from `prune_stale()`
- `backend/tests/test_memory_supersession.py` test file

### Out of scope
- New API endpoints for querying supersession history
- UI surface for viewing supersession chains
- Confidence nudging on supersession (separate trust-loop feature)
- Cross-scope supersession (contradictions only detected within the same scope)

### Deferred
- Transitive supersession resolution (following the `supersedes` chain across multiple generations)
- Configurable contradiction matching strategy (e.g., semantic similarity vs. title equality)
- Surfacing supersession provenance in retrieval results (e.g., "this item supersedes X")

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | `MemoryItem.links` field type changes from `list[str]` to `dict` with `superseded_by`/`supersedes` keys |
| R2 | `detect_contradictions(new_item)` returns same-scope, same-title, different-body existing items |
| R3 | `create()` archives contradicting items and sets `links["superseded_by"]` on each |
| R4 | New item from `create()` has `links["supersedes"]` listing archived item IDs |
| R5 | Non-contradicting writes proceed without archiving or mutation |
| R6 | Archived items excluded from retrieval and list results |
| R7 | New `test_memory_supersession.py` covers all AC paths |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 — links defaults to `{}`, supports `superseded_by: str` and `supersedes: list[str]`; round-trips through frontmatter I/O
- R2 — match = same scope + title (case-insensitive) + different body; archived/out-of-scope/same-body items excluded
- R3 — contradicting items moved to `archive/` with `links["superseded_by"] = new_id` before move
- R4 — new item has `links["supersedes"]` = list of archived IDs; empty dict when no supersession occurred
- R5 — no existing item with matching title, or same title + same body → no archiving
- R6 — `archive/` items absent from `list()` and `retrieve()` results
- R7 — test file with ≥7 named test cases covering all six requirements

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | `MemoryItem.links` changes from `list[str]` to `dict` with superseded_by/supersedes |
| R2 | test | `detect_contradictions` finds same-scope, same-title, different-body items |
| R3 | test | `create()` archives contradicting items and sets `links["superseded_by"]` |
| R4 | test | New item gets `links["supersedes"]` with archived item IDs |
| R5 | test | Non-contradicting writes are unchanged (no archive, no mutation) |
| R6 | test | `archive/` items absent from `list()` and `retrieve()` |
| R7 | test | `test_memory_supersession.py` with ≥7 named test cases |

## Assumptions

- `has_ui: false` rationale: all changes are in `memory_store.py` and `models.py` (backend); the feature has no UI surface in the request text or scout findings.
- The `links` field is currently unused (always `[]`), so changing its type from `list[str]` to `dict` is a non-breaking change for all existing consumers (none set or read `links` today).
- Contradiction detection uses exact title matching (case-insensitive, stripped) rather than semantic similarity — consistent with how the scout framed "same key/name/slug".
- Same-title + same-body is an idempotent re-write, not a contradiction; the existing item is preserved and no links are set on the new item.
- The archive mechanism reuses the existing `archive/` subdir from `prune_stale()` (already a soft-delete pattern).
- `detect_contradictions()` must not raise if `items_dir` does not exist (new/empty scope) — return empty list.
- The design agent must ensure the update-links-then-archive sequence is atomic within the existing `async with self._lock` block.

## Open questions

- None. Requirements map cleanly to the three scope files (models.py, memory_store.py, test file).

## Next consumer brief

**For the design agent** (`design-report-trust-loop-supersession.md`):

Read in order: `traceability[]` (R1–R7), `## Scope`, `## Assumptions` (schema change safety, atomicity requirement).

**Decision points:**
1. **Schema migration for `links`**: `list[str]` → `dict` is safe since `links` is currently always `[]`. The design must confirm no existing test fixtures write non-empty `links` lists that would fail deserialization.
2. **Atomic update-then-archive**: the design must ensure `links["superseded_by"]` is written to the item file BEFORE `os.replace()` moves it to `archive/`. If the process crashes between write and move, the item stays in `items/` with the link set — acceptable transient state.
3. **Iteration ordering**: R1 (schema change in models.py) must precede R2/R3/R4 (memory_store.py logic) and R5/R6 (passthrough + retrieval) in the implementation DAG. Tests (R7) depend on all prior changes.
4. **`list()` exclusion**: confirm that the current `_list_scope_locked()` implementation already excludes `archive/` (it globs `items/*.md`, so archive is naturally excluded). The design should verify this rather than adding redundant filtering.
5. **Risk area**: frontmatter serialization of `links: dict` vs `links: list` — the `_dump_item()` / `_load_item()` methods use `python-frontmatter`; dicts serialize as YAML mappings, lists as YAML sequences. Verify round-trip correctness for both empty (`{}`) and populated (`{"superseded_by": "abc"}`) dict values.
