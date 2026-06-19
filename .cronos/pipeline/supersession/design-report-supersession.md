---
cc_version: "1.0"
agent: pipeline-architect
slug: supersession
phase: design
status: done
confidence: 0.85
inputs_used:
  - memory:project-memory-system
  - memory:project-memory-lifecycle
  - memory:project-architecture
  - .cronos/pipeline/trust-loop-supersession/analysis-report-trust-loop-supersession.md
  - .cronos/pipeline/trust-loop-supersession/scout-report-trust-loop-supersession.md
  - backend/app/models.py
  - backend/app/memory_store.py
  - backend/app/memory_retrieval.py
outputs_produced:
  - .cronos/pipeline/supersession/design-report-supersession.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
    - backend/app/models.py
    - backend/app/memory_store.py
    - backend/app/memory_retrieval.py
  excluded:
    - "frontend/: backend-only feature, has_ui=false in analysis"
    - "deploy/: no deployment surface for memory supersession"
  strategies:
    - memory_retrieval
    - read_targeted
    - grep_symbol
iterations:
  - id: I1
    type: data
    scope_files:
      - backend/app/models.py
    validation_command: 'cd backend && pytest tests/test_memory_supersession.py::test_links_defaults_to_dict -v --override-ini="addopts="'
    max_diff_lines: 30
    depends_on: []
  - id: I2
    type: backend
    scope_files:
      - backend/app/memory_store.py
    validation_command: 'cd backend && pytest tests/test_memory_supersession.py::test_detect_contradiction tests/test_memory_supersession.py::test_detect_no_contradiction tests/test_memory_supersession.py::test_create_supersedes_archives_old_item tests/test_memory_supersession.py::test_create_supersedes_sets_links tests/test_memory_supersession.py::test_create_non_contradiction_unchanged -v --override-ini="addopts="'
    max_diff_lines: 260
    depends_on:
      - I1
  - id: I3
    type: backend
    scope_files:
      - backend/tests/test_memory_supersession.py
    validation_command: 'cd backend && pytest tests/test_memory_supersession.py -v --override-ini="addopts="'
    max_diff_lines: 400
    depends_on:
      - I1
      - I2
risks:
  - description: "Legacy memory item files on disk serialize links as a YAML list (`links: []`). After R1 changes the field type to dict, _load_item() will construct MemoryItem(links=[]) and Pydantic will reject the empty list against a dict-typed field, making every previously-written memory item unreadable (the whole store fails to load)."
    severity: high
    mitigation: "I2's _load_item() must coerce a non-dict links value to an empty dict before building the model: `links = meta.get('links'); links = links if isinstance(links, dict) else {}`. The I3 test test_load_legacy_list_links_coerced writes a fixture file with `links: []` frontmatter directly and asserts it loads with links == {}. This makes the migration backward-compatible without a data migration script."
  - description: "Frontmatter/YAML round-trip of a populated dict with a nested list value (`{'supersedes': ['mem-x']}`) could lose ordering or coerce types differently from the list case the store has always used, silently corrupting the supersedes chain."
    severity: medium
    mitigation: "I2 changes _dump_item() line 99 to emit `dict(item.links)` (mapping) instead of `list(item.links)`. The I3 test test_links_roundtrip creates an item, sets links to {'superseded_by': 'mem-a'} and {'supersedes': ['mem-a','mem-b']}, dumps then loads it, and asserts dict equality both ways before any supersession logic is exercised."
  - description: "The update-link-then-archive sequence in create() is two filesystem operations (write superseded_by into the old item file, then os.replace it into archive/). If they run outside the existing lock or in the wrong order, a concurrent retrieve() could observe the old item already mutated but not yet archived, or detect_contradictions() could re-match an item mid-archive."
    severity: medium
    mitigation: "I2 performs the entire supersession sequence inside the existing `async with self._lock` block in create(), BEFORE persisting the new item, and in this exact order per contradicted item: (1) _atomic_write the old file with links['superseded_by']=new_id while it is still in items/, (2) os.replace it into archive/ (mkdir parents first, mirroring prune_stale lines 366-367). The I3 test test_create_supersedes_archives_old_item asserts the old file is absent from items/ and present in archive/ with the link set."
  - description: "Case-insensitive title matching in detect_contradictions() could over-match (treat two genuinely distinct memories with coincidentally equal normalized titles as contradictions) and silently archive a still-valid memory."
    severity: low
    mitigation: "detect_contradictions() compares `new.title.strip().lower() == existing.title.strip().lower()` AND `existing.body != new.body` — body equality is the second gate, so same-title/same-body re-writes are never archived. The I3 tests test_detect_no_contradiction (different title) and test_create_non_contradiction_unchanged (same title + same body) pin both negative paths."
  - description: "detect_contradictions() called on a brand-new or empty scope whose items/ directory does not yet exist would raise on glob, aborting the very first create() in that scope."
    severity: low
    mitigation: "detect_contradictions() guards `items_dir = self._items_dir(scope); if not items_dir.is_dir(): return []` exactly as _list_scope_locked() already does (memory_store.py:185-187), so the first write into any scope detects zero contradictions and proceeds. The I3 test test_detect_empty_scope covers this."
metrics:
  tool_calls: 12
  files_read: 5
  memory_hits: 3
  iterations_planned: 3
---

## Summary

This design wires the previously-unused `MemoryItem.links` field for memory supersession: when a memory is written whose title matches an existing same-scope item but whose body differs, the old item is archived and bidirectional links are set (`superseded_by` on the archived item, `supersedes` on the new one). The plan splits along the two changed source files plus a test file: I1 changes only the `links` field type in `models.py` (`list[str]` → `dict`), I2 carries all of `memory_store.py` (dict serialization round-trip, `detect_contradictions()`, and the archive-and-link supersession block inside `create()`), and I3 assembles `test_memory_supersession.py` covering every requirement. The DAG is a deliberate serial chain (I1 → I2 → I3) because dict serialization in I2 cannot be valid until the field is a dict in I1, and the tests assert behaviour from both. The load-bearing, non-obvious invariant is backward compatibility: existing on-disk items carry `links: []`, so I2's `_load_item()` must coerce any non-dict value to `{}` — captured as the highest-severity risk, since without it the entire store fails to load.

## Components

### Data
- `MemoryItem.links` (`backend/app/models.py:377`): field type changes from `list[str] = Field(default_factory=list)` to `dict[str, Any] = Field(default_factory=dict)`; defaults to `{}`, supports optional keys `superseded_by` (str) and `supersedes` (list[str]). No other model field changes.

### Backend
- `MemoryStore._dump_item()` / `_load_item()` (`memory_store.py:82-122`): serialize `links` as a YAML mapping (`dict(item.links)`) and coerce any non-dict loaded value to `{}` for backward compatibility with legacy `links: []` files.
- `MemoryStore.create()` / `update()` signatures (`memory_store.py:212,287`): `links` parameter type becomes `dict | None`; `create()` stores `links=links or {}`.
- `MemoryStore.detect_contradictions(new_scope, new_title, new_body)` — new method: returns existing non-archived items in the same scope whose normalized title equals the new title but whose body differs. Guards a missing `items/` dir by returning `[]`. Reuses `_list_scope_locked()` semantics (globs `items/*.md`, so `archive/` is excluded automatically).
- `MemoryStore.create()` supersession block — new logic inside the existing `async with self._lock`, executed before the new item is persisted: for each contradicted item, write `links["superseded_by"] = new_id` into its file (still in `items/`) then `os.replace()` it into `archive/` (mirroring `prune_stale()` lines 366-367); accumulate archived ids into the new item's `links["supersedes"]`.
- Retrieval/list exclusion (`memory_retrieval.py`, `_list_scope_locked`): **no code change** — archived items leave `items/`, so they drop out of the rebuilt index and out of `list_scope()`. Verified by I3 tests rather than modified.

## Implementation plan

| ID  | Type    | Depends on | Scope files (abridged)                    | Validation                                                                                     |
|-----|---------|------------|-------------------------------------------|------------------------------------------------------------------------------------------------|
| I1  | data    | -          | backend/app/models.py                     | pytest tests/test_memory_supersession.py::test_links_defaults_to_dict -v                        |
| I2  | backend | I1         | backend/app/memory_store.py               | pytest tests/test_memory_supersession.py::test_detect_* test_create_* -v                        |
| I3  | backend | I1, I2     | backend/tests/test_memory_supersession.py | pytest tests/test_memory_supersession.py -v                                                     |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Legacy on-disk `links: []` (list) fails to load against new dict-typed field → whole store unreadable | high | I2 `_load_item()` coerces non-dict links to `{}`; I3 test_load_legacy_list_links_coerced pins it |
| Dict round-trip through frontmatter could corrupt nested `supersedes` list | medium | I2 emits `dict(item.links)`; I3 test_links_roundtrip asserts dict equality both directions |
| update-link-then-archive race / wrong order leaves item half-superseded | medium | Whole sequence inside existing lock, write superseded_by then os.replace into archive/; I3 test asserts old file moved |
| Case-insensitive title match over-archives a still-valid memory | low | Match requires same normalized title AND differing body; I3 negative tests pin same-body and different-title |
| detect_contradictions on a scope with no `items/` dir raises on glob | low | Guard `if not items_dir.is_dir(): return []` mirroring `_list_scope_locked`; I3 test_detect_empty_scope |

## Assumptions

- The DAG is intentionally serial (I1 → I2 → I3) rather than wide: I2's dict serialization is invalid until I1 makes `links` a dict, and I3's tests exercise both. There is no independent layer-0 work to parallelize for a three-file, schema→logic→tests feature.
- Contradiction matching is exact normalized-title equality (`strip().lower()`) plus body inequality — consistent with the analyst's framing of "same key/name/slug with different content"; semantic similarity is explicitly deferred.
- The archive mechanism reuses the existing `archive/` subdir and `os.replace` move pattern from `prune_stale()` (memory_store.py:357-367); no new soft-delete machinery is introduced.
- R6 (retrieval/list exclusion) needs no production-code change: `_list_scope_locked()` globs `items/*.md` and `retrieve()` reads the rebuilt index, so archived items are excluded the moment they leave `items/`. I2's archive move is the cause; I3 only adds the asserting test.
- `links: dict[str, Any]` uses `Any` value typing so the field can hold both a `str` (`superseded_by`) and a `list[str]` (`supersedes`) without a discriminated union; validation of key shapes is left to the store logic and tests, not the Pydantic model.

## Open questions

- None. All seven requirements (R1–R7) map to iteration scope files; the only structural-only requirement (R6) is covered by I2's archive move plus an I3 test.

## Next consumer brief

For implementation: read `iterations[]` and `iterations[].scope_files` from the YAML header — they are hard diff boundaries (I1 = models.py only, I2 = memory_store.py only, I3 = the new test file only). Cross-iteration invariants the YAML cannot encode:

1. **I1 ↔ I2 type contract**: I1 sets `links: dict[str, Any] = Field(default_factory=dict)`. I2 MUST then change `_dump_item` line 99 from `list(item.links)` to `dict(item.links)`, change `_load_item` to coerce non-dict to `{}`, and change the `create()`/`update()` `links` params to `dict | None` with `links or {}`. If I2 lands before this coercion, every existing item file (`links: []`) becomes unloadable — the highest-severity risk.
2. **Atomic order in I2**: per contradicted item — (a) `_atomic_write` the old file with `links["superseded_by"]=new_id` while still in `items/`, (b) `os.replace` into `archive/`. Then persist the new item with `links["supersedes"]=[old_ids...]`. All inside the one `async with self._lock` in `create()`.
3. **No memory_retrieval.py edit**: R6 is satisfied structurally; do not add redundant archive filtering. I3 asserts exclusion against the unchanged retrieval path.
4. **Test names are the binding spec** for the forward-referenced validation commands in I1/I2: `test_links_defaults_to_dict`, `test_detect_contradiction`, `test_detect_no_contradiction`, `test_create_supersedes_archives_old_item`, `test_create_supersedes_sets_links`, `test_create_non_contradiction_unchanged`, plus `test_load_legacy_list_links_coerced`, `test_links_roundtrip`, `test_detect_empty_scope`, `test_retrieval_excludes_archived`. Use `--override-ini="addopts="` to bypass the 60% coverage floor on narrow selections.
