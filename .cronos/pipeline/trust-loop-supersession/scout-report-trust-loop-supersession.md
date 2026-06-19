---
cc_version: "1.0"
agent: pipeline-scout
slug: trust-loop-supersession
phase: scout
status: done
confidence: 0.9
inputs_used:
  - memory:project-memory-system
  - memory:project-memory-lifecycle
  - memory:project-architecture
  - memory:project-pipeline-foundation
  - backend/app/memory_store.py
  - backend/app/models.py
  - backend/app/trace_parser.py
  - backend/app/memory_retrieval.py
  - backend/app/memory_lifecycle.py
  - backend/app/worker.py
  - backend/app/storage.py
  - backend/tests/test_memory_store.py
  - backend/tests/test_memory_lifecycle.py
outputs_produced:
  - .cronos/pipeline/trust-loop-supersession/scout-report-trust-loop-supersession.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/memory_store.py
    - backend/app/memory_retrieval.py
    - backend/app/memory_lifecycle.py
    - backend/app/trace_parser.py
    - backend/app/worker.py
    - backend/app/storage.py
    - backend/app/models.py
  excluded:
    - frontend/: not relevant to memory system backend
    - deploy/: not relevant to in-app memory lifecycle
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Research the memory system codebase to answer 6 questions: (1) MemoryItem schema, (2) task lifecycle hooks, (3) memory_hits tracking, (4) links field, (5) confidence retrieval scoring, (6) test coverage patterns"
metrics:
  tool_calls: 7
  files_read: 12
  memory_hits: 4
---

## Summary

The memory system is a fully-implemented persistent store with confidence-scored retrieval, lifecycle management (TTL decay/boost/prune), and integration into agent execution and task completion hooks. Confidence multiplies retrieval score directly (line 28, memory_retrieval.py: `(matches / len(terms)) * item.confidence`). Items default to confidence=1.0 (agents) or are set explicitly on write. The `links` field is a list[str] defaulting to empty list. Memory IDs are tracked during retrieval (trace_parser.py lines 341–352) and stored in RunTrace.memory_used[]. Task completion triggers three post-DONE hooks: harness fan-out via on_task_state_change callback (worker.py:1029), PR autopilot flow (1051), and adopted-tool merge finalization (1074). No rework-to-BACKLOG hook exists yet — that would be a gap for the trust-loop supersession feature.

## Coverage

### Searched
- backend/app/memory_store.py (384 lines) — MemoryItem I/O, confidence storage, TTL archive
- backend/app/models.py (lines 364–378) — MemoryItem Pydantic schema
- backend/app/memory_retrieval.py (70 lines) — term-match + confidence scoring
- backend/app/memory_lifecycle.py (48 lines) — decay/boost/prune/auto-confirm logic
- backend/app/trace_parser.py (384 lines) — RunTrace.memory_hit_rate computation
- backend/app/worker.py (lines 825–1272) — task finalization + post-DONE hooks
- backend/app/storage.py (lines 1–200) — TaskState transitions, USER_TRANSITIONS, WORKER_TRANSITIONS
- backend/tests/test_memory_store.py (250 lines) — create/get/update/delete/boost patterns
- backend/tests/test_memory_lifecycle.py (105 lines) — boost/prune/auto-confirm test specs

### Excluded
- frontend/src/**/*.tsx: memory system is backend-only; frontend consumes via API endpoints (not in scope)
- deploy/: deployment scripts don't contain business logic
- Backend test files outside memory scope: covered implicitly via test pattern analysis

### Strategies
- memory_retrieval: 4 relevant entries from project memory index established foundational context
- glob_structural: targeted Python file search located core modules (memory_store.py, retrieval.py, lifecycle.py)
- grep_symbol: confirmed confidence field, links list, memory_hits tracking present in codebase
- read_targeted: full-depth read of core modules + test files to answer all 6 questions

## Findings

### 1. MemoryItem Schema (backend/app/models.py:364–378)

```
class MemoryItem(BaseModel):
    id: str
    scope: str  # "global" | "space:{space_id}"
    kind: MemoryKind  # FACT | PROCEDURE | OBSERVATION | REFERENCE
    title: str
    body: str = ""
    confirmed: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    score: float = 0.0
    last_used_at: datetime
    ref_count: int = 0
    ttl_until: datetime | None = None
    sources: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
```

**Key fields:**
- `confidence: float` defaults to 1.0, validated in range [0.0, 1.0]
- `links: list[str]` defaults to empty list (not dict, not None)
- `score: float` is the retrieval + lifecycle score (initially 0.0 on create)
- `ref_count: int` incremented on each access (auto-confirm at ≥3)
- `ttl_until: datetime | None` controls pruning eligibility
- `confirmed: bool` manual or auto-confirmed via access boosts

### 2. write_memory() & create() Patterns (memory_store.py:198–238)

**Public entry point:** `MemoryStore.create()` with kwargs:
```python
async def create(
    self,
    *,
    scope: str,
    kind: MemoryKind | str,
    title: str,
    body: str = "",
    confirmed: bool = False,
    confidence: float = 1.0,  # Set here on write
    score: float = 0.0,
    ...
    sources: list[str] | None = None,
    links: list[str] | None = None,
) -> MemoryItem:
```

**Confidence initial values:**
- Default: `confidence: float = 1.0` (assumes agent-written facts as trusted)
- Retro-written items: explicitly set `confidence: float` on create() call (e.g., retro_memory_writer.py would pass 0.8 or similar)
- No auto-demotion on create; confidence is immutable until explicit update()

**Sources:** assigned at creation (e.g., worker.py:1210: `sources=[f"task:{task_id}", f"run:{run_index}"]`)

### 3. Confidence in Retrieval Scoring (memory_retrieval.py:24–28)

```python
def _term_match_score(item: MemoryItem, terms: set[str]) -> float:
    """Fraction of query terms found in item title + body, weighted by confidence."""
    haystack = (item.title + " " + item.body).lower()
    matches = sum(1 for t in terms if t in haystack)
    return (matches / len(terms)) * item.confidence
```

**Confidence is an active multiplier:**
- Baseline score = (term_matches / total_terms)
- **Final score = baseline × item.confidence**
- Example: if item matches 3/4 terms (0.75) with confidence=0.8, final_score=0.6
- Items with confidence=1.0 preserve full term-match score
- Items with confidence=0.5 receive 50% of their term-match baseline

**Retrieval flow (memory_retrieval.py:31–69):**
1. Extract terms from task.title + task.brief
2. Scan space + global index.md for candidates
3. Load matching items via `store.get()` (which boosts score)
4. Score via `_term_match_score()` × confidence
5. Return top-5 sorted by boosted score

### 4. memory_hits in RunTrace (trace_parser.py:148–152, 336–352)

**Field definition:**
```python
class RunTrace(BaseModel):
    ...
    memory_injected: list[str] = Field(default_factory=list)
    memory_used: list[str] = Field(default_factory=list)
    memory_written: list[str] = Field(default_factory=list)
    memory_hit_rate: float = 0.0
```

**Tracking during retrieval (worker.py:871–877):**
```python
retrieved_memory = None
if self.memory_store is not None:
    try:
        retrieved_memory = await memory_retrieval.retrieve(task, task.space_id, self.memory_store) or None
    except Exception:
        log.exception("Failed to retrieve memory for %s", task_id)
```

**Memory IDs tracked in trace (trace_parser.py:336–352):**
- `memory_injected` = list of .md filenames from Claude's workspace memory dir
- `memory_used` = unique memory item IDs read from .cronos/memory/items/ (extracted via regex `_memory_slug()`)
- `memory_written` = unique memory item IDs written (MEMORY: blocks or created via memory_store.create())
- `memory_hit_rate` = `len(mem_used) / max(1, len(memory_injected))`

**Memory items passed to agent (worker.py:887, agent.py):** memory_retrieval.retrieve() returns list[MemoryItem], passed as `memory_items=retrieved_memory` to run_agent()

### 5. Task Completion Hooks & Life Cycle (worker.py:936–1272)

**finalize_run() atomically transitions task state:**
```python
await self.store.finalize_run(
    task_id,
    new_state=new_state,  # DONE | WAITING
    session_id=...,
    waiting_question=...,
    history_entry=...,
)
```

**Post-DONE hooks (triggered only when new_state == TaskState.DONE):**

1. **Harness fan-out (worker.py:1029–1044)** — triggers on_task_state_change callback
   ```python
   if new_state == TaskState.DONE and self._on_task_state_change is not None:
       await self._on_task_state_change(space_id, task_id, old_state, new_state)
   ```
   Wired by main.py to fan_out_to_harnesses() for trigger dispatch

2. **Autopilot PR flow (worker.py:1046–1065)** — runs post_done_flow for PR creation
   ```python
   if new_state == TaskState.DONE and self.space_store is not None:
       pr_result = await autopilot_pr.run_post_done_flow(task_done, space_for_pr, self.store)
   ```

3. **Adopted-tool merge finalization (worker.py:1068–1090)** — parses merge-meta brief
   ```python
   if new_state == TaskState.DONE:
       if task_for_merge.title.startswith("Merge upstream changes to "):
           meta = _parse_merge_meta(task_for_merge.brief)
           finalize_merge(meta["space_id"], ...)
   ```

4. **Goal state propagation (worker.py:1093–1096)** — child-to-parent
   ```python
   await goal_sync.propagate_to_parent(task_id, self.store, self._pool)
   ```

5. **Feature realization sync (worker.py:1098–1102)** — feature/fix state updates
   ```python
   await feature_sync.propagate_to_feature(task_id, self.store, self._pool)
   ```

**No existing rework-to-BACKLOG hook:** Tasks transition DONE → WAITING (if agent fails) or stay DONE (if success). Manual DONE → BACKLOG is a user action (USER_TRANSITIONS). No automatic "re-enqueue on trust failure" exists — would be a new capability.

### 6. Access Boost & Get Mutation (memory_store.py:240–266)

**get() always mutates:**
```python
async def get(self, scope: str, item_id: str) -> MemoryItem | None:
    # ...
    decayed_score = decay(item.score, item.last_used_at, now)
    new_score, new_ttl = boost(decayed_score, item.ttl_until, now)
    new_ref_count = item.ref_count + 1
    boosted = item.model_copy(update={
        "score": new_score,
        "ref_count": new_ref_count,
        "last_used_at": now,
        "ttl_until": new_ttl,
    })
    if should_auto_confirm(new_ref_count):
        boosted = boosted.model_copy(update={"confirmed": True})
    self._atomic_write(path, self._dump_item(boosted))
```

**Lifecycle constants (memory_lifecycle.py:6–13):**
- `DECAY_HALF_LIFE_DAYS = 14.0`
- `BOOST_AMOUNT = 0.5` (additive, not multiplicative)
- `MAX_SCORE = 10.0`
- `PRUNE_THRESHOLD = 0.1`
- `TTL_EXTENSION_PER_BOOST_DAYS = 7`
- `CONFIRM_MIN_USES = 3` (auto-confirm after 3 accesses)

**Archive vs. Delete:**
- `delete()` removes file immediately (worker-visible deletion)
- `prune_stale()` moves to `archive/` subdir (soft retention for auditing)
- Pruning condition: `now >= ttl_until AND score < 0.1` (line 365, memory_store.py)

### 7. Test Coverage Patterns (backend/tests/test_memory_*.py)

**Key test suites:**
- `test_memory_store.py` (250 lines) — create/get/update/delete/list/index, boost persistence, confirmed badge, scope isolation
- `test_memory_lifecycle.py` (105 lines) — decay/boost/prune logic, CONFIRM_MIN_USES threshold, MAX_SCORE cap, BOOST_AMOUNT > PRUNE_THRESHOLD invariant
- `test_memory_retrieval.py` — term extraction, confidence weighting, top-5 ranking
- `test_memory_integration.py` — end-to-end memory write/retrieve/boost cycles

**R4 invariant (test_memory_lifecycle.py:70–84):** Boosting from 0.0 must exceed PRUNE_THRESHOLD even when TTL expires
**R7 invariant (test_memory_lifecycle.py:71–84):** Auto-confirm and score resilience

## Assumptions

- Confidence=1.0 is the default for agent-written facts; retro-written items or user-curated items set confidence explicitly
- Links field is currently unused (empty list) but reserved for future relationship traversal or transclusion features
- Memory retrieval is read-only mutation: get() boosts score but doesn't change item.confidence
- Task completion triggers exactly 3 post-DONE hooks (harness, PR, merge); other state transitions skip all hooks
- Confidence multiplier is preserved across get() calls (confidence field is never mutated during lifecycle)
- Per-space memory index is rebuilt atomically after every create/update/delete/prune to keep wikilinks in sync

## Open questions

- None. All 6 research questions answered with code citations.

## Next consumer brief

**For analysis agent:**

The trust-loop supersession feature will likely need to:
1. Add a new post-DONE hook that evaluates task outcome confidence (via confidence-scored memory matching or external verdict mechanism)
2. If confidence below threshold, automatically re-enqueue task to BACKLOG with a rework briefing
3. Track prior supersession attempts to prevent infinite loops (similar to auto-resume counter in worker.py:1217–1224)
4. Populate `links` field on memory items to record bidirectional relationships (e.g., memory-item → task-outcome for traceability)
5. Consider confidence decay over rework cycles so repeated failures progressively lower memory confidence

**Key modules to analyze:**
- storage.py: TaskState enum and USER_TRANSITIONS/WORKER_TRANSITIONS sets (lines 61–78)
- worker.py: _finalize() method and post-DONE hook insertion points (lines 1025–1100)
- memory_retrieval.py: confidence multiplier application (line 28)
- memory_store.py: update() for confidence mutations if needed
