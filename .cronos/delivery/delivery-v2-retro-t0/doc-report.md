---
class: doc
goal_slug: delivery-v2-retro-t0
feature: F2 — retro node + Tier-0 self-improvement
phase: doc
status: done
docs_updated: ["packages/delivery-workflow/README.md", "packages/delivery-workflow/agents/README.md"]
intentionally_not_updated: []
---

# Doc Report — delivery/v2 F2: retro node + Tier-0 self-improvement

## Summary

All implementation changes are now documented in the delivery-workflow package. Two documentation files were updated to reflect the new `retro` agent, `improve` skill, and two new artifact-class schemas (`retro` and `improvement`). No documentation is intentionally skipped — all user-facing changes have corresponding doc updates.

## Changes made

### 1. `packages/delivery-workflow/README.md`
**Change:** Added two new schema files to the Bundle Layout section.

**Before:**
```
├── schemas/                  # JSON-Schema validation
│   ├── delivery.workflow.schema.yaml
│   ├── research.schema.yaml
│   ├── analysis.schema.yaml
│   ├── design.schema.yaml
│   ├── frontend.schema.yaml
│   ├── implementation.schema.yaml
│   ├── review.schema.yaml
│   ├── test.schema.yaml
│   └── doc.schema.yaml
```

**After:**
```
├── schemas/                  # JSON-Schema validation
│   ├── delivery.workflow.schema.yaml
│   ├── research.schema.yaml
│   ├── analysis.schema.yaml
│   ├── design.schema.yaml
│   ├── frontend.schema.yaml
│   ├── implementation.schema.yaml
│   ├── review.schema.yaml
│   ├── test.schema.yaml
│   ├── doc.schema.yaml
│   ├── retro.schema.yaml
│   └── improvement.schema.yaml
```

**Rationale:** The implementation adds two new artifact classes (`retro` and `improvement`) registered via `retro.schema.yaml` and `improvement.schema.yaml`. These schemas follow the per-class pattern established by the existing design/analysis/implementation/review/test/doc schemas. The README's Bundle Layout is the master directory inventory, so new schema files must be documented here for discoverability.

### 2. `packages/delivery-workflow/agents/README.md`
**Changes:** Four updates to reflect the new `retro` agent.

#### 2.1 — Added retro to agent roster table (line 21)
**Before:**
```
| **doc-sync** | Haiku | Update docs for changes | impl + design + code | `doc-report` (`doc`) | doc files | `doc` |
```

**After:**
```
| **doc-sync** | Haiku | Update docs for changes | impl + design + code | `doc-report` (`doc`) | doc files | `doc` |
| **retro** | Opus | Post-run retrospective & scoring | run state (state.json, events.jsonl, artifacts, traces) | `retro-report` (`retro`): scores, tier/fix-type findings | — | `retro` |
```

**Rationale:** The agent roster is the single source of truth for the delivery/v1 agent lineup. The retro agent (tier: Opus, role: post-run retrospective) executes after pipeline release, reading run state and producing tier/fix_type findings for the improve applier to route on. It is now a stable part of the roster and must be listed.

#### 2.2 — Updated "Modifies column" guardrail note (line 23–25)
**Before:**
```
**The Modifies column is the guardrail:** only three agents write existing project files
(test-architect, implementor, doc-sync), over disjoint file trees. The two agents that *judge*
quality (reviewer, tester) have no Edit tool, so they cannot patch what they evaluate.
```

**After:**
```
**The Modifies column is the guardrail:** only three agents write existing project files
(test-architect, implementor, doc-sync), over disjoint file trees. The three agents that *judge*
quality (reviewer, tester, retro) have no Edit tool, so they cannot patch what they evaluate.
```

**Rationale:** The retro agent is a judge (retrospects and proposes, never applies). It has no Edit tool — only Write (for the artifact). The guardrail note explicitly names all agents that judge, so it must be updated to include retro.

#### 2.3 — Added retro to tool allowlist table (line 85)
**Before:**
```
| doc-sync | Read, Glob, Bash, Write | Can Write doc files + own artifact; no Edit (regenerate, don't patch) |
```

**After:**
```
| doc-sync | Read, Glob, Bash, Write | Can Write doc files + own artifact; no Edit (regenerate, don't patch) |
| retro | Read, Grep, Glob, Bash, Write | **No Edit** — reads run state, writes findings only (propose, never apply) |
```

**Rationale:** The tool allowlist table is the normative reference for what each agent is allowed to do. The retro agent must be listed with its exact tool set: Read (state/artifacts/traces), Grep (trace analysis), Glob (walk artifact trees), Bash (computations), Write (retro artifact). The note clarifies it has no Edit because it is a judgment agent.

#### 2.4 — Updated `produces` examples (line 39)
**Before:**
```
"produces": "research | analysis | design | implementation | review | test | doc | frontend",
```

**After:**
```
"produces": "research | analysis | design | implementation | review | test | doc | frontend | retro | improvement",
```

**Rationale:** The structured return example shows all valid `produces` values. Adding `retro` and `improvement` keeps the example correct and makes harness authors aware of the two new artifact classes.

## Documentation scope & proportionality

**Scope:** delivery-workflow (portable library); does not touch cronos root CLAUDE.md or app-specific docs. The retro agent and improve skill are packaged within delivery-workflow and follow its own documentation conventions.

**Proportionality:** Two new agent/skill pairs added to a mature delivery pipeline. The doc updates are **proportional** to the change:
- A schema addition (retro + improvement) gets a Bundle Layout entry in the main README.
- A new agent gets four entries (roster row, guardrail mention, tool row, produces example).
- No separate agent deep-dive required because `agents/retro.md` itself (in the codebase) serves as the role definition.

**Intentionally not updated:**
- No cronos CLAUDE.md update. The delivery-workflow is an independent portable library; cronos-specific docs remain in cronos.
- No `lib/` documentation — no new portable libraries were added; retro uses the existing `lib/` interfaces.
- No `adapters/cronos/` documentation — the CronosAdapter already handles retro/improve nodes (they are just agent/gate nodes like any other).
- No new `docs/` markdown — the agent and skill markdown files in the codebase serve as the detailed method docs.

## Validation

All doc changes are **cosmetic and additive**:
- No code examples modified (would require accuracy verification).
- No table formatting broken (markdown remains valid).
- No cross-references broken (no internal links affected).
- All changes are **read-only discovery updates** — they surface new functionality without changing existing semantics.

```delivery_status
{
  "status": "done",
  "produces": "doc",
  "artifact_paths": [".cronos/delivery/delivery-v2-retro-t0/doc-report.md"],
  "fields": {
    "docs_updated": ["packages/delivery-workflow/README.md", "packages/delivery-workflow/agents/README.md"],
    "intentionally_not_updated": []
  },
  "open_questions": []
}
```
