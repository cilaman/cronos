---
class: doc
agent: doc-sync
goal_slug: delivery-v2-security
feature: "F1 — security-review node (delivery/v2 §2)"
phase: doc
status: done
docs_updated: ["packages/delivery-workflow/agents/README.md"]
intentionally_not_updated:
  - "CLAUDE.md: root project documentation focuses on Cronos-coupled components; delivery/v2 is documented in the portable delivery-workflow package and delivery-v2-spec.md"
  - "docs/delivery-pipeline/delivery-v2/delivery-v2-spec.md: already comprehensive; no implementation details added to the spec itself"
  - "packages/delivery-workflow/README.md: package documentation at appropriate level; agents/skills documented in their individual files and the agents/README.md roster"
---

# Documentation — F1 security-review node (delivery/v2)

## Summary

F1 introduced two new agents in the delivery/v1 package: `security-reviewer` (LLM judgment + OWASP/CWE triage) and `g-security` gate (real-subprocess scanner re-execution). Both are well-documented in their own implementation files (`agents/security-reviewer.md` and `skills/security-review/SKILL.md`). The only user-facing documentation needing update was the agent roster table in `packages/delivery-workflow/agents/README.md`, which is the primary registry where users learn what agents are available and their I/O contract.

## Files changed

- `packages/delivery-workflow/agents/README.md` — Updated the "Agent roster & I/O contract" table (line 10–20) and "Tool allowlists" table (line 74–84) to add `security-reviewer` as a row, positioned after `reviewer` (its upstream node in the workflow). Added description of role, tools, and guardrails to keep the documentation current with the implementation.

## Scope analysis

### Considered but intentionally not updated

1. **`CLAUDE.md`** — Root project documentation listing Cronos modules. The delivery pipeline (`packages/delivery-workflow/`) is a **portable package** designed to be adopted by multiple runtimes, not a Cronos-specific component. Including it in CLAUDE.md would blur the boundary between Cronos-coupled and portable infrastructure. The delivery/v2 features are properly documented at the package level (agents/README.md, individual agent/skill files) and in the spec (docs/delivery-pipeline/delivery-v2/). No update needed.

2. **`docs/delivery-pipeline/delivery-v2/delivery-v2-spec.md`** — Already comprehensive; documents the F1 design decisions (DD-001 through DD-010), placement, routing taxonomy, and acceptance criteria. No implementation details belong in the spec itself; the implementation lives in code.

3. **`packages/delivery-workflow/README.md`** — Package-level documentation. It already names agents as a category ("9 agents spanning research → design → build → verify → docs") and describes the roster structure. Specific agent names and roles are documented in `agents/README.md` and individual agent files, not duplicated at the package level.

4. **`backend/app/pipeline/gate.py`** — Source code documentation. The `_check_security` function is well-commented; docstrings explain the fail-closed behavior, scanner fallback handling, and artifact reconciliation. No separate documentation artifact needed.

5. **`packages/delivery-workflow/schemas/delivery.workflow.schema.yaml`** — Spec-driven; the schema is the documentation. JSON-Schema field descriptions are present in the YAML itself (`description` keys on the `security` check type).

## Artifacts from implementation

The agent (`security-reviewer.md`) and skill (`security-review/SKILL.md`) are self-documenting at ~80 and ~145 lines respectively. They follow the established delivery/v1 harvest-and-author pattern and include:

- **Agent** — Role definition, inputs, outputs, hard rules, return structure
- **Skill** — 10-section method (memory preflight, trust model, scan sweeps, OWASP/CWE mapping, severity ladder, code-vs-dependency-vs-design routing, false-positive triage, carry-forward discipline, artifact reconciliation, scope enforcement)
- **Schema** — JSON-Schema description fields for the `security` check type and its four sub-fields
- **Tests** — 9 real-subprocess gate tests, 3 schema tests, 16 spec wiring tests; all validation commands green

No separate documentation was required for these — the agent and skill files are the reference documentation.

## Status

**Complete.** The agent roster is now current, and all user-facing documentation is consistent with the implementation. The implementation-phase finding (F1 and F2 gate defects) does not affect documentation; it affects the next implementation pass to harden the security gate's parse failure handling.
