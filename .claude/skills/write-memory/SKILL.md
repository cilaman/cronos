---
name: write-memory
description: Write a memory file to the correct workspace-scoped path. Use whenever you want to save a feedback, project, user, or reference memory. Avoids the root cause where memory written to the wrong path is never injected into future runs.
---

# Write Memory

Writes a memory file to the workspace-specific memory directory derived from `$PWD`. This is the only path the harness injects into future runs of the same task workspace.

## Critical rule

**Never delegate memory writes to a subagent (Agent tool).** The subagent cannot know the spawning agent's `$PWD`, so it will write to the wrong path — typically the space-root memory, which is never injected into workspace runs.

Write memory directly using the `Write` and `Edit` tools.

## Step 1 — compute the memory path

```bash
MEMORY_DIR="/root/.claude/projects/$(pwd | sed 's|[^a-zA-Z0-9-]|-|g')/memory"
echo "$MEMORY_DIR"
mkdir -p "$MEMORY_DIR"
```

The formula: take `$PWD`, replace every character that is not alphanumeric or `-` with `-`, prepend `/root/.claude/projects/`, append `/memory`.

Example: `$PWD = /data/spaces/cronos-development/.cronos/workspaces/2026-05-29-1234-my-task`  
→ `MEMORY_DIR = /root/.claude/projects/-data-spaces-cronos-development--cronos-workspaces-2026-05-29-1234-my-task/memory`

## Step 2 — write the memory file

Use the `Write` tool with the full absolute path from Step 1:

```
Write(
  file_path = "<MEMORY_DIR>/feedback_my_topic.md",
  content   = """---
name: feedback-my-topic
description: One-line summary used to decide relevance — be specific
metadata:
  type: feedback   # or: user | project | reference
---

Rule or fact.

**Why:** The reason this matters (incident, constraint, preference).
**How to apply:** When and where this guidance kicks in.
"""
)
```

Memory types:
- **feedback** — guidance on how to approach work (corrections and validated successes)
- **project** — ongoing work, goals, decisions, deadlines
- **user** — user role, preferences, expertise level
- **reference** — pointers to external systems (Linear projects, dashboards, APIs)

## Step 3 — update MEMORY.md

Read the existing `MEMORY.md` (or create it if absent), then add one index line:

```markdown
- [Title](filename.md) — one-line hook under ~150 chars
```

Keep MEMORY.md under 200 lines — it is always loaded into context.

## Step 4 — verify

```bash
ls "$MEMORY_DIR"
```

Confirm the file exists at the workspace-specific path.

## Anti-patterns

| Wrong | Why |
|-------|-----|
| `Agent("save this to memory")` | Subagent writes to its own (unknown) path, not yours |
| Hardcoding `/root/.claude/projects/-data-spaces-cronos-development/memory/` | That is the space-root path — invisible to workspace runs |
| Writing to `$PWD/memory/` | Wrong location entirely — not under `/root/.claude/projects/` |
