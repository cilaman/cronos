---
cc_version: '1.0'
agent: pipeline-analyst
slug: g12-lightweight-docs
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project-g04-fail-closed-auth-impl
- memory:project-g11-least-priv-git-impl
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- README.md
outputs_produced:
- .cronos/pipeline/g12-lightweight-docs/analysis-report-g12-lightweight-docs.md
blockers: []
next_consumer: design
request: 'Adds a minimal security-posture note and optional architecture decision
  records (ADRs) so the system''s deliberate choices are discoverable to future-you.
  After: A security-posture section exists in README (or SECURITY.md) describing the
  intended controls — non-root agents (G03), fail-closed auth (G04), human-approved
  plugin install (G06), least-privilege PAT (G11) — and that there is no formal support/disclosure
  process (personal project). Optionally: 2–3 ADRs for markdown-as-truth + SQLite-as-index,
  SQLite-native durability (G08), Mermaid-over-Excalidraw. This is a minimal scope
  (D2 resolved: personal project, not adoptable OSS).'
has_ui: false
coverage_summary:
  searched:
  - README.md (full, 117 lines)
  - docs/ (listing — only HARNESSES.md present)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md §G12
  excluded:
  - backend/: no source changes; documentation-only goal
  - frontend/: no source changes; documentation-only goal
  - .github/: no workflow changes in scope
  strategies:
  - memory_retrieval
  - read_targeted
  - glob_structural
traceability:
- requirement_id: R1
  statement: README.md gains a 'Security posture' section that consolidates all four
    intended controls and states there is no formal support/disclosure process.
  acceptance_criteria:
  - Given README.md is read, when a reader looks for security information, then a
    clearly titled 'Security posture' (or equivalent) section is present.
  - 'The section covers: non-root agent execution (G03), fail-closed app-layer auth
    (G04), human-approved + Bash-guarded plugin install (G06), and least-privilege
    git PAT (G11).'
  - The section explicitly states Cronos is a personal project with no formal vulnerability
    disclosure or support process.
  - Each control cross-references either the implementation detail in README (existing
    Auth / Git credential model sections) or the relevant goal identifier.
  verifying_phase: review
  confidence: 0.95
- requirement_id: R2
  statement: A docs/adr/001-markdown-as-truth.md ADR documents the markdown-as-truth
    + SQLite-as-disposable-index architecture invariant.
  acceptance_criteria:
  - The file exists at docs/adr/001-markdown-as-truth.md (or equivalent structured
    path).
  - 'The ADR records the decision: markdown files are the authoritative source of
    truth; SQLite (cronos-index.db) is a disposable index rebuilt from disk on startup.'
  - 'The rationale explains the self-healing property: torn dual-writes resolve on
    next restart without manual intervention.'
  - The ADR notes the consequence for future coordination state (e.g., task leases
    per G08 must live index-side and not displace markdown-as-truth).
  verifying_phase: review
  confidence: 0.9
- requirement_id: R3
  statement: A docs/adr/002-sqlite-durability.md ADR captures the SQLite-native durability
    decision (G08/D3).
  acceptance_criteria:
  - The file exists at docs/adr/002-sqlite-durability.md (or equivalent structured
    path).
  - 'The ADR records the decision: SQLite lease/heartbeat tables for the durable queue
    over Postgres, Redis, or LangGraph-style checkpointing.'
  - 'The rationale includes: preserves the one-VPS-SQLite identity; LangGraph/Temporal
    checkpoints state between nodes, not inside long agent runs, so they don''t address
    the actual gap (crash mid-run).'
  - 'The ADR states when to revisit: if durability needs outgrow single-VPS SQLite.'
  verifying_phase: review
  confidence: 0.88
metrics:
  tool_calls: 6
  files_read: 3
  memory_hits: 2
---

## Summary

G12 adds a minimal security-posture note to README.md and 2–3 lightweight ADRs under `docs/adr/`. Decision D2 (personal system) is resolved: the full external adopter on-ramp (CONTRIBUTING, issue templates, formal disclosure policy) is explicitly deferred. The README currently has separate "Authentication" and "Git credential model" sections covering G04 and G11, but has no consolidated security-posture section and no mention of G03 (non-root) or G06 (plugin guard). The `docs/` directory exists with only `HARNESSES.md`; no ADR subdirectory or files exist yet. All three requirements produce markdown prose, making them review-verified rather than unit-test-verified.

## Scope

### In scope
- A "Security posture" section added to README.md describing all four intended controls (G03, G04, G06, G11) and the personal-project trust model
- docs/adr/001-markdown-as-truth.md — the load-bearing architecture invariant (markdown-as-truth + SQLite-as-disposable-index)
- docs/adr/002-sqlite-durability.md — SQLite-native durability rationale (G08/D3)
- Creation of the docs/adr/ directory

### Out of scope
- CONTRIBUTING.md, issue/PR templates, CHANGELOG — deferred (D2: personal system)
- Formal vulnerability disclosure policy — deferred (D2)
- SECURITY.md as a standalone file — inline README section is sufficient for personal scope
- A third ADR (Mermaid-over-Excalidraw) — optional per remediation plan; deferring as lower priority than the two architectural ADRs
- Any changes to backend or frontend source files

### Deferred
- Full adopter on-ramp (CONTRIBUTING, ARCHITECTURE, issue templates, governance, formal disclosure policy) — revisit only if D2 changes to "adoptable OSS"
- Mermaid-over-Excalidraw ADR — can be added in a follow-on pass if desired
- A third ADR for any additional architectural decisions surfaced post-G12

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | README.md gains a consolidated "Security posture" section covering G03/G04/G06/G11 and personal-project trust model |
| R2 | docs/adr/001-markdown-as-truth.md captures the markdown-as-truth + SQLite-as-disposable-index invariant |
| R3 | docs/adr/002-sqlite-durability.md captures the SQLite-native durable queue rationale (G08/D3) |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array. Compact summary:

- R1 — README.md "Security posture" section present; covers non-root (G03), fail-closed auth (G04), plugin guard (G06), least-priv PAT (G11); states no formal support/disclosure; each control cross-references implementation detail.
- R2 — docs/adr/001-markdown-as-truth.md exists; states decision (markdown=truth, SQLite=index), rationale (self-healing), and implication for G08 coordination state.
- R3 — docs/adr/002-sqlite-durability.md exists; states decision (SQLite leases over Postgres/Redis/LangGraph), rationale (one-VPS identity + crash-inside-run gap), and revisit condition.

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | review | README.md gains a "Security posture" section that consolidates all four intended controls and states there is no formal support/disclosure process. |
| R2 | review | docs/adr/001-markdown-as-truth.md ADR documents the markdown-as-truth + SQLite-as-disposable-index architecture invariant. |
| R3 | review | docs/adr/002-sqlite-durability.md ADR captures the SQLite-native durability decision (G08/D3). |

## Assumptions

- has_ui=false rationale: all outputs are markdown documentation files; no React component, API endpoint, or UI interaction is introduced.
- G04 (fail-closed auth) and G11 (least-priv git) are already implemented and merged to `feature/cronos-remediation-plan` (confirmed via memory entries). The security-posture note can describe G04/G11 as implemented; G03/G06 should be described as "intended" or "planned" controls — the note documents the design target, not a false present-tense claim.
- README.md has separate "Authentication" and "Git credential model" sections (lines 62–104); the new "Security posture" section should complement these rather than duplicate them — cross-reference or consolidate at design time.
- docs/ directory exists (`docs/HARNESSES.md` confirmed by scout); docs/adr/ subdirectory does not exist and must be created.
- The optional Mermaid-over-Excalidraw ADR is deferred as the lowest-priority of the three suggested ADRs; two ADRs satisfy the remediation plan's acceptance criteria.
- Scout status=done (confidence 0.92); this analysis inherits that confidence level.

## Open questions

- None. D2 (personal system) is resolved; scope is unambiguous. The design agent should decide the exact section title in README (e.g., "Security posture", "Security controls", or an expansion of the existing "Authentication" section) and whether to use a lightweight ADR template vs. free-form markdown.

## Next consumer brief

**Design agent read order:** `traceability[]` → `## Scope` → `## Assumptions`.

**Key decision points for design:**
1. **README section placement:** "Authentication" and "Git credential model" sections already exist (lines 62–104). Decide whether to add "Security posture" as a new H2 after "Git credential model" or to fold G03/G06 mentions into the existing auth section. A separate section is cleaner for discoverability.
2. **G03/G06 wording:** At writing time, G03 and G06 may not yet be merged. The section must describe them as *intended* controls ("agents are designed to run as non-root") rather than present-fact, or include a status qualifier. This is a prose-level design decision.
3. **ADR template:** docs/HARNESSES.md uses prose markdown, not a rigid ADR template. The design agent should decide if a minimal ADR header (Title / Status / Context / Decision / Consequences) suffices or if free-form prose is fine. Lightweight header is recommended for scannability.
4. **File paths:** docs/adr/ as the ADR home is the conventional choice and matches the existing docs/ directory; confirm or adjust at design time.
5. No backend, frontend, or test changes needed — implementation is pure markdown authoring.
