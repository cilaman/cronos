---
cc_version: "1.0"
agent: pipeline-scout
slug: pipeline-agents
phase: scout
status: done
confidence: 0.85
inputs_used:
  - memory:pipeline-foundation
  - memory:pipeline-cronos-mapping
  - backend/app/pipeline/contract.py
  - backend/app/pipeline/CONTRACT.md
  - backend/app/pipeline/verify.py
  - backend/app/pipeline/schemas/research.schema.yaml
outputs_produced:
  - .cronos/pipeline/pipeline-agents/scout-report-pipeline-agents.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/pipeline/
    - .claude/agents/
    - backend/app/models.py
    - backend/app/agent.py
  excluded:
    - frontend/: not relevant to pipeline agent authoring brief
    - backend/tests/: test fixtures read selectively only
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Understand the CC-v1 contract and infrastructure needed to author pipeline phase agents for Cronos."
metrics:
  tool_calls: 14
  files_read: 4
  memory_hits: 2
---

## Summary

The Cronos pipeline uses CC-v1 Agent Contract (`backend/app/pipeline/CONTRACT.md`) which adapts the Delivery Notes Agent Contract v1.0. Key differences: `memory_hits` replaces `kb_hits` (Cronos uses `memory_store.py`, not `.kb/`), agents never write `duration_s`/`token_spend` (trace-owned), and artifacts live at `.cronos/pipeline/{goal_slug}/{phase}-report-{goal_slug}.md`. The contract schema (`contract.py`) defines `HEADER_FIELDS`, `REQUIRED_SECTIONS`, `R_RULES`, and `AGENT_REPORTED_METRICS`. The verifier (`verify.py`) accepts `--agent research` for scout-class artifacts and exits 0/1/2/3 for proceed/fail/escalate/retry.

## Coverage

### Searched
- `backend/app/pipeline/` — contract.py, CONTRACT.md, verify.py, schemas/research.schema.yaml
- `.claude/agents/` — existing agent files for format reference
- `backend/app/models.py` and `backend/app/agent.py` — agent spawning and memory injection patterns

### Excluded
- `frontend/`: not relevant to pipeline agent authoring
- `backend/tests/fixtures/`: selectively referenced only for schema validation patterns

### Strategies
- memory_retrieval: 2 relevant entries (pipeline-foundation, pipeline-cronos-mapping)
- glob_structural: located all pipeline schema files and existing agent definitions
- grep_symbol: traced CC_VERSION, HEADER_FIELDS, REQUIRED_SECTIONS, CLASS_CONFIG constants
- read_targeted: read contract.py, CONTRACT.md, verify.py, research.schema.yaml in full

## Findings

**CC-v1 contract constants** (`backend/app/pipeline/contract.py:39-51`):
- `HEADER_FIELDS` = cc_version, agent, slug, phase, status, confidence, inputs_used, outputs_produced, blockers, next_consumer, metrics
- `REQUIRED_SECTIONS` = Summary, Coverage, Findings, Assumptions, Open questions, Next consumer brief
- `AGENT_REPORTED_METRICS` = tool_calls, files_read, memory_hits
- `TRACE_OWNED_METRICS` = duration_s, token_spend (agents MUST NOT write these)

**Research-class specifics** (`backend/app/pipeline/schemas/research.schema.yaml`):
- Additional required field: `coverage_summary` (searched, excluded, strategies list)
- Allowed strategy strings: memory_retrieval, glob_structural, grep_symbol, grep_keyword, read_targeted, repo_map, web_search, fetch_url
- Optional fields: `brief` (verbatim brief for eval replay), `top_relevance[]` (ranked findings)

**Verifier** (`backend/app/pipeline/verify.py:74-110`):
- `CLASS_CONFIG["research"]` maps to `phase_const="scout"` and `filename_prefix="scout-report"`
- R4 cross-field rule enforced: `files_read + memory_hits >= len(inputs_used)`
- Trace-owned fields in agent-written artifacts → hard fail

**Existing agent format** (`.claude/agents/test-architect.md`):
- Cronos agents use YAML frontmatter with `name`, `description`, `model`, `tools`
- No `input_contract`/`output_contract` frontmatter (unlike Delivery Notes format)
- Model IDs use full names (e.g. `claude-opus-4-8`) not short aliases

## Assumptions
- The pipeline-agents goal slug is verbatim as passed — no derivation.
- Memory context entries are counted as memory_hits when the agent relied on them, not merely when they appeared in the prompt.
- The `tools` frontmatter field accepts a comma-separated list; `allowed_tools` is the Delivery Notes field name but Cronos uses `tools`.

## Open questions
- None.

## Next consumer brief

Read `coverage_summary.strategies` and `## Findings` first. The critical facts for authoring pipeline phase agents:

1. `phase` field MUST equal the class's `phase_const` from `CLASS_CONFIG` (e.g. `"scout"` for research class).
2. Agent NEVER writes `duration_s` or `token_spend` — verifier hard-fails on these.
3. `coverage_summary` is required for research class; strategies must be from the allowed enum.
4. R4 (`files_read + memory_hits >= len(inputs_used)`) is the most common failure point.
5. Artifact path is workspace-relative: `.cronos/pipeline/{goal_slug}/scout-report-{goal_slug}.md`.
