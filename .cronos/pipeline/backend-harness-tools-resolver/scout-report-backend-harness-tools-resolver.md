---
cc_version: "1.0"
agent: pipeline-scout
slug: backend-harness-tools-resolver
phase: scout
status: done
confidence: 0.9
inputs_used:
  - backend/app/worker.py
  - backend/app/tools/scanner.py
  - backend/app/api/tools.py
  - backend/app/harnesses/brief_composer.py
  - backend/app/harnesses/executor.py
  - backend/app/models.py
  - backend/app/space_storage.py
outputs_produced:
  - .cronos/pipeline/backend-harness-tools-resolver/scout-report-backend-harness-tools-resolver.md
blockers: []
next_consumer: pipeline-analyst
metrics:
  tool_calls: 8
  files_read: 7
  memory_hits: 0
coverage_summary:
  searched:
    - backend/app/worker.py stub resolver location
    - backend/app/tools/scanner.py _scan_category and _scan_skills functions
    - backend/app/api/tools.py _scan_context function
    - backend/app/harnesses/brief_composer.py _is_skill and compose_brief functions
    - backend/app/harnesses/executor.py resolver injection and invocation
    - backend/app/models.py AiToolEntry structure
    - backend/app/space_storage.py SpaceStore paths
  excluded: []
  strategies:
    - read_targeted
    - grep_symbol
---

# Scout: Backend Harness Tools Resolver

## Summary

The harness executor needs a tools resolver function to match `agent_ref` strings (agent, skill, command, or context names) against real `AiToolEntry` objects. The resolver is stubbed at `backend/app/worker.py:642-643` and already integrated into the `HarnessExecutor` at `backend/app/harnesses/executor.py:753`. Existing scanners in `scanner.py` and `api/tools.py` can be reused to collect candidates; the implementation must match by name, search both space and global scopes, and return the correct entry so that `compose_brief()` can detect skills and apply the `/<skill-name>` prefix.

## Coverage

- **Searched**: Stub location, HarnessExecutor integration, existing scanners, brief composer skill detection, scope resolution strategy, space directory resolution, tool categories
- **Excluded**: No exclusions; all relevant source paths examined
- **Strategies**: Targeted reads of 7 source files, grep for resolver-related symbols, schema analysis

## Findings

### 1. Stub Location and Integration

The stub resolver is at `backend/app/worker.py:642-643`:
```python
def _tools_resolver(space_id: str, agent_ref: str):
    return None
```

It's already wired into `HarnessExecutor`:
- Injected during construction (line 649): `executor = HarnessExecutor(..., _tools_resolver, ...)`
- Called at line 753 of `backend/app/harnesses/executor.py`: `agent_entry = self.tools_resolver(space.id, agent_ref)`
- Result flows directly to `compose_brief(node, interpolated_prompt, agent_entry)` at line 758

### 2. AiToolEntry Structure

All four tool categories (agents, skills, commands, context) share the same `AiToolEntry` model from `backend/app/models.py:289-294`:
```python
class AiToolEntry(BaseModel):
    name: str                  # The tool name (stem or directory name)
    path: str                  # Relative path from space root, e.g. ".claude/skills/foo/SKILL.md"
    description: str | None = None
    scope: str                 # "space" or "global"
    modified_at: str           # ISO-8601 timestamp
```

The `name` field is what's matched against `agent_ref`; the `path` field is used to detect skill vs. agent via `_is_skill()`.

### 3. Existing Scanners (Reusable)

Three scanner functions in the codebase:

#### `_scan_category(claude_dir: Path, subfolder: str, scope: str, recursive: bool = False)`
- **Location**: `backend/app/tools/scanner.py:70-94`
- **Purpose**: Scans `.claude/<subfolder>/` for markdown files
- **Returns**: List of `AiToolEntry` with name=stem, scope=(passed-in), path=(relative to space root)
- **Usage**: Agents, commands (with `recursive=True` for nested structure)

#### `_scan_skills(claude_dir: Path, scope: str)`
- **Location**: `backend/app/tools/scanner.py:97-136`
- **Purpose**: Scans `.claude/skills/` for two patterns:
  - Flat `.md` files: `skills/my-skill.md` → name="my-skill"
  - Directory-based: `skills/my-skill/SKILL.md` → name="my-skill"
- **Returns**: List of `AiToolEntry` with name=(stem or dir name), path=(to the .md file), scope=(passed-in)
- **Key**: Path always points to the .md file; `_is_skill()` detects skills by checking if "skills/" is in the path

#### `_scan_context(claude_dir: Path, scope: str)`
- **Location**: `backend/app/api/tools.py:57-83`
- **Purpose**: Scans `.claude/CONTEXT.md` and `.claude/context/` directory
- **Returns**: List of `AiToolEntry` for both locations

### 4. How Brief Composer Detects Skills

The `compose_brief()` function in `backend/app/harnesses/brief_composer.py:35-41` uses `_is_skill()`:
```python
def _is_skill(agent_entry: AiToolEntry) -> bool:
    """Return True when the resolved tool entry is a skill (not a plain agent)."""
    return "skills/" in agent_entry.path or "/skills/" in agent_entry.path
```

This checks the path string for the substring "skills/" (handles both Unix and Windows style). If true, the brief gets the header `/<skill_name>`; otherwise `Agent: <name>`.

### 5. Scope Resolution Strategy

Both space-scoped and global-scoped tools must be searchable:
- **Space-scoped**: `.claude/` inside the space directory
- **Global-scoped**: `~/.claude/` (home directory)

The `api/tools.py:129-174` endpoint shows the pattern:
1. Scan space `.claude/` directory for all four categories
2. Scan global `~/.claude/` directory for all four categories
3. Return space entries first in the lists, so they shadow globals with the same name

For the resolver, we should:
1. Scan space-scoped tools first
2. Return the first match by name
3. If no space match, scan globals and return the first global match
4. Return `None` if no match in either scope

### 6. Space Directory Resolution

The space directory is obtained from `SpaceStore.space_dir(space_id)`:
- **Path**: `{spaces_dir}/{space_id}`
- **Inside task execution**: The space object is already available; use `space.id` parameter passed to resolver
- **DATA_DIR**: Import from `backend/app/main.py` or use `Path.home().parent.parent / "data" / "spaces"`

### 7. Scanned Categories Summary

Based on `api/tools.py:129-174`, the full tool enumeration:

| Category | Scanner | Path Pattern | Name Match |
|----------|---------|--------------|------------|
| Agent | `_scan_category(..., "agents", ...)` | `.claude/agents/<name>.md` | File stem |
| Skill (flat) | `_scan_skills(...)` | `.claude/skills/<name>.md` | File stem |
| Skill (dir) | `_scan_skills(...)` | `.claude/skills/<name>/SKILL.md` | Dir name |
| Command | `_scan_category(..., "commands", ..., recursive=True)` | `.claude/commands/**/*.md` | File stem or path-based |
| Context (file) | `_scan_context(...)` | `.claude/CONTEXT.md` | "CONTEXT" |
| Context (dir) | `_scan_context(...)` | `.claude/context/<name>.*` | File stem |

The `agent_ref` string is matched against the `name` field of all entries.

## Design Observations

1. **Single-name matching**: The resolver matches by name only (no category prefix in `agent_ref`). This means if both an agent and a skill share the same name, the space-scoped one wins, then the global agent, then the global skill. The actual execution behavior depends on the harness design — the brief will have the correct header based on which tool is matched.

2. **Reusing scanners**: All three scanners handle path extraction and description parsing; the resolver only needs to call them and filter by name.

3. **Atomic resolution**: The resolver function receives `(space_id, agent_ref)` and returns `AiToolEntry | None`. No state or caching is required; it's called once per agent node during harness execution.

4. **Brief composition is automatic**: Once the resolver returns an entry, `compose_brief()` handles the skill-prefix detection and header generation. No additional logic needed in the resolver.

## Assumptions

1. The `DATA_DIR` variable is accessible from `backend/app/main.py` or derivable as `Path.home().parent.parent / "data" / "spaces"`.
2. Both space-scoped and global-scoped tools are available during harness execution.
3. The resolver function is called exactly once per agent node, so performance is not a concern.
4. No filtering by tool category is needed; matching by name across all four categories (agents, skills, commands, context) is intentional.
5. The `brief_composer._is_skill()` function will correctly detect skills via the "skills/" path substring.

## Open questions

1. Should the resolver handle case-insensitive matching? (Current scanners are case-sensitive; this matches the existing scanner behavior.)
2. When both a space and global tool share the same name, should space always win? (Yes, per the pattern in `api/tools.py:129-174`.)
3. Are there any performance constraints on scanning the `.claude/` directories during harness execution? (Harness execution is already interactive; small upfront cost is acceptable.)

## Next consumer brief

The analyst phase should:
1. Extract the resolver implementation into testable requirements (matching logic, scanner invocation order, scope precedence, error handling)
2. Identify how to access the space directory and DATA_DIR from the worker context
3. Specify test cases covering all four tool categories, space vs. global scoping, and the "miss → None" case
4. Clarify whether the resolver should log missing tools or fail silently (currently: return None)
5. Design the resolver to be a pure function with no side effects (atomic, idempotent)
