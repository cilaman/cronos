---
cc_version: '1.0'
agent: pipeline-architect
slug: g12-lightweight-docs
phase: design
status: done
confidence: 0.9
inputs_used:
- memory:project-g04-fail-closed-auth-impl
- memory:project-g11-least-priv-git-impl
- memory:project-remediation-board-setup
- memory:observation-worktree-main-vs-workspace
- .cronos/pipeline/g12-lightweight-docs/analysis-report-g12-lightweight-docs.md
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- README.md
- backend/app/pipeline/schemas/design.schema.yaml
- backend/app/pipeline/CONTRACT.md
outputs_produced:
- .cronos/pipeline/g12-lightweight-docs/design-report-g12-lightweight-docs.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - README.md
  - docs/
  - .cronos/pipeline/g12-lightweight-docs/
  - backend/app/pipeline/schemas/design.schema.yaml
  excluded:
  - 'backend/: documentation-only goal; no source changes'
  - 'frontend/: documentation-only goal; no source changes'
  - 'tests/: no unit tests to add for prose deliverables'
  strategies:
  - memory_retrieval
  - read_targeted
  - glob_structural
iterations:
- id: I1
  type: infra
  scope_files:
  - README.md
  validation_command: test -f README.md && grep -q '^## Security posture' README.md
    && grep -q 'G03' README.md && grep -q 'G04' README.md && grep -q 'G06' README.md
    && grep -q 'G11' README.md && grep -qi 'personal project' README.md && grep -qi
    'no formal' README.md
  max_diff_lines: 120
  depends_on: []
- id: I2
  type: infra
  scope_files:
  - docs/adr/001-markdown-as-truth.md
  validation_command: mkdir -p docs/adr && test -f docs/adr/001-markdown-as-truth.md
    && grep -q '^# ADR 001' docs/adr/001-markdown-as-truth.md && grep -q '^## Status'
    docs/adr/001-markdown-as-truth.md && grep -q '^## Context' docs/adr/001-markdown-as-truth.md
    && grep -q '^## Decision' docs/adr/001-markdown-as-truth.md && grep -q '^## Consequences'
    docs/adr/001-markdown-as-truth.md && grep -qi 'markdown' docs/adr/001-markdown-as-truth.md
    && grep -qi 'cronos-index.db' docs/adr/001-markdown-as-truth.md && grep -qi 'self-healing'
    docs/adr/001-markdown-as-truth.md && grep -qi 'G08' docs/adr/001-markdown-as-truth.md
  max_diff_lines: 200
  depends_on: []
- id: I3
  type: infra
  scope_files:
  - docs/adr/002-sqlite-durability.md
  validation_command: mkdir -p docs/adr && test -f docs/adr/002-sqlite-durability.md
    && grep -q '^# ADR 002' docs/adr/002-sqlite-durability.md && grep -q '^## Status'
    docs/adr/002-sqlite-durability.md && grep -q '^## Context' docs/adr/002-sqlite-durability.md
    && grep -q '^## Decision' docs/adr/002-sqlite-durability.md && grep -q '^## Consequences'
    docs/adr/002-sqlite-durability.md && grep -qi 'lease' docs/adr/002-sqlite-durability.md
    && grep -qi 'heartbeat' docs/adr/002-sqlite-durability.md && grep -qi 'LangGraph'
    docs/adr/002-sqlite-durability.md && grep -qi 'G08' docs/adr/002-sqlite-durability.md
    && grep -qi 'revisit' docs/adr/002-sqlite-durability.md
  max_diff_lines: 200
  depends_on: []
risks:
- description: README divergence between worktrees — the per-task workspace worktree
    at `.cronos/workspaces/2026-06-20-1437-architect-g12-lightweight-docs/README.md`
    is a 62-line stale pre-remediation copy with no Authentication or Git credential
    model sections, while the canonical 116-line README on `feature/cronos-remediation-plan`
    is at the space root. Editing the stale copy would silently drop G04+G11 documentation
    and produce a malformed Security posture section.
  severity: critical
  mitigation: Implementor MUST be cut from `feature/cronos-remediation-plan` (the
    goal branch) so its workspace worktree contains the 116-line README. Implementor
    MUST verify before editing by running `wc -l README.md` (expect ~116) and `grep
    -c '^## Authentication\|^## Git credential model' README.md` (expect 2). The Security
    posture section is to be inserted as a new H2 AFTER the existing `## Git credential
    model` section (around line 104 in the canonical README) and BEFORE `## Layout`.
    If verification fails, abort the iteration and escalate.
- description: G03 (non-root agents) and G06 (plugin install guard) may not be merged
    when I1 runs — the memory index shows G04 and G11 merged but no merge marker for
    G03/G06. A present-tense claim like 'agents run as non-root' would be a false
    documentation statement.
  severity: high
  mitigation: I1 MUST write G03/G06 with explicit status qualifiers — phrasings like
    'designed to run as non-root (G03, planned)' or 'human approval gate on plugin
    install (G06, designed)'. G04 and G11 may be written present-tense ('the app layer
    is fail-closed', 'least-privilege fine-grained PAT'). The validation grep checks
    merely require the goal IDs G03/G04/G06/G11 appear; the qualifier discipline is
    enforced at the review phase via the existing acceptance criteria for R1.
- description: Validation commands are content greps, not unit tests. A typo in a
    heading or a missing required keyword would slip past loose greps, and the review
    phase becomes the real gate. Drift between the validation strings and the prose
    the author writes can also produce false validation failures.
  severity: medium
  mitigation: Each validation_command pins (a) file existence, (b) the exact ADR or
    section H2 markers, and (c) at least one substantive keyword per acceptance criterion.
    The implementor MUST mirror the validation strings verbatim in the prose — the
    heading text and key terms (cronos-index.db, self-healing, LangGraph, lease, heartbeat,
    revisit, personal project) are not optional. The keyword set was chosen to be
    tight enough to detect missing acceptance criteria but loose enough not to over-constrain
    prose phrasing.
- description: docs/adr/ directory does not yet exist. Either ADR iteration running
    first must create it; if both run in parallel and both attempt `mkdir`, only an
    idempotent variant is safe.
  severity: low
  mitigation: Both I2 and I3 prepend `mkdir -p docs/adr` to their validation_command
    and the implementor MUST also include `mkdir -p docs/adr` as the first action
    of the iteration. `mkdir -p` is idempotent and safe under parallel execution;
    no I-level dependency is required.
- description: An ADR template that diverges from existing repo conventions (docs/HARNESSES.md
    uses free-form prose, not an ADR-style header) could feel inconsistent.
  severity: low
  mitigation: 'Adopt a minimal, lightweight ADR header — `# ADR <num>: <title>` followed
    by `## Status`, `## Date`, `## Context`, `## Decision`, `## Consequences`. This
    is the standard Nygard-style template. The two ADRs are the first ADRs in the
    repo, so they set the convention rather than fight one. HARNESSES.md remains as-is
    (it is a system reference, not a decision record).'
metrics:
  tool_calls: 9
  files_read: 6
  memory_hits: 4
  iterations_planned: 3
---

## Summary

G12 produces three lightweight markdown deliverables: a consolidated `## Security posture` section appended to the space-root `README.md` (covering G03/G04/G06/G11 with personal-project disclaimer) and two ADRs under a newly-created `docs/adr/` — `001-markdown-as-truth.md` (markdown=truth, SQLite=disposable index, G08 implication) and `002-sqlite-durability.md` (SQLite leases over Postgres/Redis/LangGraph, one-VPS identity, revisit condition). All three iterations are independent (DAG layer 0); the two ADRs each idempotently create `docs/adr/`, so no synchronization edge is needed. Validation commands are deterministic `test -f` + `grep -q` content checks pinned to required ADR section headings and acceptance-criteria keywords. The critical risk to thread through to the implementor is README-divergence between the space-root worktree (116 lines, on `feature/cronos-remediation-plan`) and the stale per-task workspace worktree (62 lines).

## Components

### Data
- None — documentation-only goal, no schema, models, or storage changes.

### Backend
- None — no FastAPI routes, services, workers, or tests are created or modified.

### Infra / Docs
- `README.md` — gains a new H2 `## Security posture` section (inserted after `## Git credential model`, before `## Layout`) consolidating G03, G04, G06, G11 with status qualifiers for G03/G06; states Cronos is a personal project with no formal vulnerability disclosure or support process; cross-references the existing `## Authentication` and `## Git credential model` sections.
- `docs/adr/` directory — created on first use; convention home for future ADRs.
- `docs/adr/001-markdown-as-truth.md` — new ADR (Nygard-style: Title / Status / Date / Context / Decision / Consequences); records the markdown-as-truth + SQLite-as-disposable-index invariant; rationale is the self-healing property under torn dual-writes; consequence is that G08 task leases must live in the SQLite index and must not displace markdown as the source of truth.
- `docs/adr/002-sqlite-durability.md` — new ADR (same template); records SQLite lease/heartbeat tables as the chosen durable-queue substrate over Postgres, Redis, or LangGraph/Temporal-style checkpointing; rationale preserves single-VPS SQLite identity and notes LangGraph/Temporal checkpoint *between* nodes not *inside* long agent runs (so they don't close the crash-mid-run gap); revisit condition: durability needs outgrow single-VPS SQLite.

## Implementation plan

| ID  | Type  | Depends on | Scope files                          | Validation (abridged) |
|-----|-------|------------|--------------------------------------|-----------------------|
| I1  | infra | -          | README.md                            | `test -f README.md && grep -q '^## Security posture' && grep -q G03/G04/G06/G11 && grep -qi 'personal project'` |
| I2  | infra | -          | docs/adr/001-markdown-as-truth.md    | `mkdir -p docs/adr && test -f && grep -q ADR/Status/Context/Decision/Consequences && grep -qi cronos-index.db/self-healing/G08` |
| I3  | infra | -          | docs/adr/002-sqlite-durability.md    | `mkdir -p docs/adr && test -f && grep -q ADR/Status/Context/Decision/Consequences && grep -qi lease/heartbeat/LangGraph/G08/revisit` |

All three iterations are in topological layer 0 — no dependencies between them; they can be dispatched in parallel by the orchestrator. The machine-readable plan in the YAML `iterations[]` array is authoritative; this table is a human reading aid.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| README divergence between space-root worktree (116 lines, has Auth + Git sections) and stale per-task workspace worktree (62 lines, missing both) | critical | Cut implementor workspace from `feature/cronos-remediation-plan`; pre-edit verify with `wc -l README.md` (~116) and grep for both existing H2 sections; insert Security posture between `## Git credential model` and `## Layout`. |
| G03 + G06 may not be merged when I1 runs — present-tense claims would be false | high | Use explicit status qualifiers ('designed', 'planned', 'intended') for G03 and G06; G04 and G11 may be written present-tense (already merged). Review phase enforces the qualifier discipline against R1 acceptance criteria. |
| Validation commands are content greps, not unit tests | medium | Pin file existence, exact H2 headings, and at least one substantive keyword per acceptance criterion. Implementor mirrors the heading text and key terms verbatim in prose. Review phase is the real correctness gate. |
| `docs/adr/` directory does not yet exist | low | Both ADR iterations prepend `mkdir -p docs/adr` to their validation_command and execute the same `mkdir -p` at the start of the iteration. `mkdir -p` is idempotent and safe under parallelism. |
| ADR template divergence from existing `docs/HARNESSES.md` (free-form prose) | low | Adopt Nygard-style minimal ADR header (Title / Status / Date / Context / Decision / Consequences). These are the first ADRs in the repo, so they set the convention; HARNESSES.md remains a system reference, not a decision record. |

## Assumptions

- The implementor task will be created from `feature/cronos-remediation-plan` (the goal branch) — confirmed via memory `project-remediation-board-setup`. Any other base branch would surface the stale 62-line README and produce a malformed edit.
- G04 (fail-closed auth) and G11 (least-priv git) are already merged to `feature/cronos-remediation-plan` per memories `project-g04-fail-closed-auth-impl` and `project-g11-least-priv-git-impl`; the README at the space root already has matching sections (`## Authentication` line 60, `## Git credential model` line 91).
- G03 and G06 status at I1 execution time is unknown to this design; I1 prose MUST hedge with status qualifiers ('designed', 'planned') rather than make present-tense claims.
- `docs/HARNESSES.md` is a system-reference document, not a decision record — it does not constrain the ADR template choice.
- The optional third ADR (Mermaid-over-Excalidraw) is deferred per the analysis report's hard exclusion.
- Validation commands use POSIX `test`, `grep`, and `mkdir` — all available in the agent execution environment (confirmed by existing pipeline validation commands across the codebase).

## Open questions

- None. The analysis report's open-questions section is empty and its decision points (README section placement, G03/G06 wording, ADR template, docs/adr/ as ADR home) are all resolved in this design's Components and Risks sections.

## Next consumer brief

The downstream implementor reads `iterations[]` for the three units of work (I1, I2, I3 — all in DAG layer 0, parallel-eligible). For each iteration: `scope_files` is the hard diff boundary; `validation_command` is the exact shell command the tester will run verbatim.

Cross-iteration invariants not derivable from the YAML alone:

1. **README-divergence guard (CRITICAL):** before editing `README.md` in I1, verify the workspace was cut from `feature/cronos-remediation-plan` by running `wc -l README.md` (expect ~116 lines) and `grep -c '^## Authentication\|^## Git credential model' README.md` (expect 2). If the README is ~62 lines without those H2s, abort and escalate — the implementor is on the wrong branch and would silently drop G04/G11 documentation.
2. **Section placement (I1):** insert the new `## Security posture` H2 AFTER the existing `## Git credential model` section and BEFORE `## Layout`.
3. **G03/G06 hedging (I1):** use status qualifiers ('designed', 'planned', 'intended') for G03 and G06; G04 and G11 may be written present-tense.
4. **Idempotent dir creation (I2, I3):** start each ADR iteration with `mkdir -p docs/adr` so parallel execution is safe.
5. **ADR template (I2, I3):** Nygard-style headings — `# ADR <num>: <title>` then `## Status`, `## Date`, `## Context`, `## Decision`, `## Consequences`. The validation greps require exactly those H2 names.
6. **Required keywords (I2):** `cronos-index.db`, `self-healing`, `G08` MUST appear in the prose.
7. **Required keywords (I3):** `lease`, `heartbeat`, `LangGraph`, `G08`, `revisit` MUST appear in the prose.

No open questions block implementation. The review phase (R1/R2/R3 acceptance criteria) is the substantive correctness gate; validation commands are necessary-but-not-sufficient existence + keyword checks.
