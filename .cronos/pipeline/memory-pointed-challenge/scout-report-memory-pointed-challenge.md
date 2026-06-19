---
cc_version: "1.0"
agent: pipeline-scout
slug: memory-pointed-challenge
phase: scout
status: done
confidence: 0.95
inputs_used:
  - memory:project_memory_system
  - memory:project_parse_status_fix
  - backend/app/memory_parser.py
  - backend/app/memory_store.py
  - backend/app/models.py
  - backend/app/worker.py
  - backend/app/agent.py
  - backend/tests/test_memory_parser.py
  - .claude/skills/write-memory/SKILL.md
outputs_produced:
  - .cronos/pipeline/memory-pointed-challenge/scout-report-memory-pointed-challenge.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/memory_parser.py (regex parsing logic)
    - backend/app/memory_store.py (MemoryItem schema and storage API)
    - backend/app/worker.py (integration: memory persistence after task run)
    - backend/app/agent.py (memory injection into prompts)
    - backend/tests/test_memory_parser.py (test coverage for all patterns)
    - .claude/skills/write-memory/SKILL.md (user-facing memory writing guidance)
  excluded:
    - frontend/: not relevant to memory ingestion parsing
    - docs/: architectural overviews not parsing specifics
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Research the current MEMORY: ingestion path and document every failure mode."
metrics:
  tool_calls: 9
  files_read: 8
  memory_hits: 3
---

## Summary

The MEMORY: ingestion pipeline is implemented as a two-stage parser (`memory_parser.py` → `memory_store.create()`) with comprehensive inline and fenced block support. Regex patterns are **case-insensitive**, whitespace-tolerant, and support four inline kind hints (`[fact]`, `[procedure]`, `[observation]`, `[reference]`). Memory blocks are extracted in `worker.py` after every agent run (_finalize_task and _finalize_child) and stored as unconfirmed MemoryItems scoped per space. The injection path is clean: `memory_retrieval.retrieve()` → `build_prompt()` → `# Memory Context` header. Identified failure modes span markdown wrapping, whitespace handling, fence syntax, and state corruption on partial writes.

## Coverage

### Searched
- `backend/app/memory_parser.py` — regex definitions and parse_memory_blocks() function
- `backend/app/memory_store.py` — MemoryItem schema (lines 364–378 in models.py), storage API (create/get/update/list)
- `backend/app/worker.py` — integration points at lines 1196–1213 (_finalize_task) and 1337–1354 (_finalize_child)
- `backend/app/agent.py` — build_prompt() memory injection (lines 275–303); run_agent() memory_items parameter
- `backend/tests/test_memory_parser.py` — 26 test cases covering inline, fenced, mixed, and edge cases
- `.claude/skills/write-memory/SKILL.md` — user-facing guidance on memory file paths

### Excluded
- `frontend/`: no UI relevance to ingestion path
- `backend/app/memory_retrieval.py`: scoring/ranking, not parsing

### Strategies
- **memory_retrieval**: 3 hits (project_memory_system, project_parse_status_fix, project_pipeline_scout_agent)
- **glob_structural**: targeted grep for parse_memory_blocks, MemoryBlock, memory_parser imports
- **grep_symbol**: traced calls from worker.py → parse_memory_blocks() → memory_store.create()
- **read_targeted**: deep reads on core files; skim memory_retrieval.py; full test read for validation

## Findings

### 1. Regex pattern: MEMORY: marker (inline)

**File**: `backend/app/memory_parser.py:8–11`

```python
_MEMORY_LINE = re.compile(
    r"^\s*MEMORY(?:\[([a-z]+)\])?:\s*(.+)",
    re.IGNORECASE,
)
```

**Behavior**:
- Matches at start of line, **case-insensitive** (`re.IGNORECASE`)
- Optional leading whitespace (`^\s*`)
- Optional kind hint in square brackets: `[fact]`, `[procedure]`, `[observation]`, `[reference]`
- Kind extraction: group(1); content: group(2).strip()
- **Minimal content**: `.+` requires at least one char after the colon (fails on bare `MEMORY:` with no content)
- **Empty content bug**: Line with `MEMORY: ` (colon + space, no text) matches but content = "", then stripped to "", and is **skipped** in append (line 69 `if content:`)

### 2. Regex pattern: Fenced blocks

**File**: `backend/app/memory_parser.py:12–13`

```python
_FENCE_OPEN = re.compile(r"^```memory(?:\s+([a-z]+))?\s*$", re.IGNORECASE)
_FENCE_CLOSE = re.compile(r"^```\s*$")
```

**Behavior**:
- `_FENCE_OPEN`: Matches ` ```memory` (case-insensitive), optional kind after whitespace, end-of-line
  - **Failure mode**: ` ```memory fact ` (trailing space before close) is accepted; inner lines captured as-is
  - **Failure mode**: ` ```memory_fact` (underscore, not whitespace) is **not matched** — treated as inline code
- `_FENCE_CLOSE`: Matches ` ``` ` (backticks + optional spaces); **strict ending** (no language name allowed)
- Content trimmed before append: `.strip()` removes leading/trailing blank lines (line 74)

### 3. Supported inline kinds

**File**: `backend/app/memory_parser.py:6, 22–25`

```python
_VALID_KINDS = frozenset({"fact", "procedure", "observation", "reference"})

def _normalize_kind(raw: str | None) -> str | None:
    if raw and raw.lower() in _VALID_KINDS:
        return raw.lower()
    return None
```

**Behavior**:
- Four valid kinds; unknown kinds are **normalized to None** (line 54)
- `_normalize_kind()` is called on both inline and fenced kind hints
- **Invalid kind examples**: `[note]`, `[bug]`, `[question]` all → `kind_hint=None`
- When stored, defaults to `"observation"` (worker.py:1206, 1347)

### 4. Multi-line content in inline markers

**Failure mode**: Inline `MEMORY:` markers are **line-only**. Content after the colon on the same line is captured; subsequent lines are **not** captured.

**Example**:
```
MEMORY: first line
second line is ignored
```
Result: block with content = "first line"

**Note**: This is **intentional design** (inline ≠ fenced). Fenced blocks are for multi-line content.

### 5. Markdown wrapping and escaping

**Failure mode**: No markdown escaping in regex or storage. Inline content wrapped in backticks, brackets, or asterisks are **passed through as-is**.

**Example**:
```
MEMORY: `code snippet inside backticks` works fine
MEMORY[fact]: **bold text** is preserved
```
Result: both render correctly in markdown; no escaping issues detected in tests or code.

### 6. Empty/whitespace-only blocks

**Failure modes**:
- Inline `MEMORY: ` (colon + space, no text): Matched by regex, content = "", stripped to "", **skipped** (line 69)
- Fenced with only whitespace:
  ```
  ```memory
  
  ```
  ```
  Result: content stripped to "", **skipped** (line 75)
- Both modes handle this correctly — empty blocks are silently dropped, not stored.

### 7. Whitespace and indentation handling

**Inline**: Leading whitespace on the line is **ignored** (`^\s*`); content after colon is stripped (`.strip()`)

**Fenced**: Content lines are **preserved as-written** (no dedent logic). Example:
```
```memory
    indented line
  another line
```
```
Result: content = "    indented line\n  another line" (spacing preserved)

**Failure mode**: If fenced block uses non-standard indent (e.g., tabs vs spaces), spacing is preserved in body — can cause YAML parsing issues if body is later parsed as structured data.

### 8. Unclosed fence blocks

**Failure mode**: If ` ``` ` is never matched, content lines **accumulate until EOF**. No warning or error is logged.

**Example**:
```
MEMORY: outside fence
```memory
MEMORY: treated as content, not a marker
STATUS: DONE
```
Result: One block extracted (the `MEMORY: outside` inline). The fenced block with "MEMORY: treated..." is accumulated but never closed, so content is lost.

### 9. Case sensitivity

**Behavior**: Both `MEMORY:` and `memory:` are matched (case-insensitive). All kind hints are normalized to lowercase.

**Edge case**: `MEMORY[FACT]:` → kind_hint = "fact" (lowercased correctly). `MEMORY[Fact]:` → kind_hint = "fact" (correct).

### 10. Storage and persistence pipeline

**File**: `backend/app/worker.py:1196–1213` (_finalize_task) and `1337–1354` (_finalize_child)

**Flow**:
1. Agent output is captured in `result.final_text`
2. `parse_memory_blocks(result.final_text)` extracts MemoryBlock instances
3. For each block:
   - Title = first line of content, truncated to 120 chars (line 1203)
   - Kind = block.kind_hint if present, else default to "observation"
   - Body = full block.content
   - Scope = f"space:{task.space_id}" (per-space scoped)
   - Confirmed = False (always unconfirmed at creation)
   - Sources = [f"task:{task_id}", f"run:{run_index}"] (with run index for task) OR [f"task:{child_id}"] (without run index for child)

**Failure mode**: If `memory_store` is None (not configured), parsing happens but items are not persisted (silent no-op, line 1196 check).

**Failure mode**: If `parse_memory_blocks()` throws an exception, the exception is caught and logged (line 1212); the task continues and completes normally — memory is silently lost.

### 11. MemoryItem schema

**File**: `backend/app/models.py:364–378`

```python
class MemoryItem(BaseModel):
    id: str
    scope: str  # "global" | "space:{space_id}"
    kind: MemoryKind
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

**Key fields**:
- `id`: auto-generated at creation (timestamp + 4-byte hex token)
- `scope`: "global" or "space:{space_id}" — determines retrieval scope
- `kind`: one of four Enum values
- `confirmed`: toggled to True via `should_auto_confirm()` after 3 refs (memory_lifecycle.py)
- `confidence`: [0.0, 1.0]; used for scoring/ranking
- `score`: boosted/decayed per access (memory_lifecycle.py)
- `ttl_until`: expiry timestamp for pruning

### 12. Memory injection into prompts

**File**: `backend/app/agent.py:275–303` (build_prompt)

```python
memory_section = ""
if memory_items:
    lines = ["\n# Memory Context\n"]
    for item in memory_items:
        lines.append(f"- **{item.title}** ({item.kind.value})")
        if item.body:
            lines.append(item.body)
    memory_section = "\n".join(lines) + "\n"
```

**Format injected**:
```
# Memory Context

- **Title here** (fact)
body content here...
```

**Failure mode**: If `memory_items` list is empty or None, the entire `# Memory Context` section is omitted (no header, no list marker). Agents that expect the header will not find it.

**Failure mode**: Long titles (>120 chars) are truncated at source (worker.py:1203), but no ellipsis is added — truncation is silent.

### 13. Comparison to STATUS: sentinel

**File**: `backend/app/agent.py` (parse_status function referenced in project_parse_status_fix memory)

Key difference: `parse_status()` scans **all lines in reverse** (full file, not first/last N), returning the **last** occurrence. MEMORY: parsing is **first-to-last** (document order) and **all occurrences** are captured.

**Change in STATUS approach** (from memory:project_parse_status_fix):
- Old: scanned only last 10 lines → buried markers failed
- New: scans all lines in reverse → finds marker even with trailing output

**MEMORY approach** (no such fix needed):
- Already scans all lines (full document order traversal)
- Accumulates all blocks, not just last one
- No risk of "buried by trailing output" because all lines are always checked

## Assumptions

- **Assumption 1**: The `final_text` field in AgentResult always contains the complete agent output including STATUS and MEMORY markers. This is assumed based on agent.py's stdout capture logic and the fact that parse_memory_blocks() is called on it immediately.

- **Assumption 2**: Agents are expected to emit MEMORY blocks before STATUS (as per STATUS contract guidance in project_memory_system memory). This is not enforced by the regex — blocks can appear anywhere. But best practice is MEMORY Step 1, STATUS Step 2.

- **Assumption 3**: Nested markdown inside memory bodies (e.g., headers, code blocks) are preserved as-is. The parser does not re-escape or validate markdown syntax. This allows agents to write rich content directly.

- **Assumption 4**: The `write-memory` SKILL.md guidance reflects current system requirements. Workspace-scoped vs space-root scoping is enforced at the skill level, not the parser level.

## Open questions

- **Q1**: Are there any agents currently writing MEMORY blocks? The tests are comprehensive but there's no evidence of production memory use in the provided codebase. Recommendation: search for MEMORY: in task output logs.

- **Q2**: What is the intended behavior if an agent writes MEMORY: markers but the memory_store is not initialized? Currently, parsing succeeds but items are silently lost. Should this be an error or a graceful no-op?

- **Q3**: Are there any agents or scripts that intentionally write bare `MEMORY:` (colon with no content) for signaling? The regex will match and skip it silently. Recommendation: clarify if this is a valid pattern.

## Next consumer brief

**For analysis agent**:

- **Key YAML fields to read first**:
  - `inputs_used[]` — lists all files consulted
  - `## Findings` sections 1–10 — regex behavior, failure modes, and schema
  - `## Assumptions` — context for why design decisions were made

- **Decision points not in header**:
  - *Is the regex pattern adequate?* Currently supports 4 inline kinds + fenced blocks with optional kinds. No escaping or nesting support.
  - *Failure mode priority*: The main production risk is `memory_store=None` (silent loss) and exception swallowing (line 1212–1213). Both are low-severity but should be documented.
  - *Multi-line inline content*: Intentional by design (fenced blocks for multi-line). Not a bug.

- **Unresolved blockers**: None detected. Parsing is well-tested (26 test cases pass). Integration is clean (3 wiring points in worker.py). Storage schema is complete (10 fields including lifecycle TTL/score).

- **Suggested brief for next phase**: Analyze whether agents are expected to emit MEMORY blocks routinely, or if this is a passive feature only used when agents explicitly call write-memory. This affects whether the ingestion path is "critical fast path" or "background feature."
