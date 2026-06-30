---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: sg6-skills-regeneration
phase: doc
status: done
confidence: 0.90
inputs_used:
  - .cronos/pipeline/sg6-skills-regeneration/review-report-sg6-skills-regeneration--attempt1.md
  - .cronos/pipeline/sg6-skills-regeneration/impl-report-sg6-skills-regeneration.md
  - .cronos/pipeline/sg6-skills-regeneration/impl-report-sg6-skills-regeneration--i5.md
  - .claude/skills/create-goal/SKILL.md
  - .claude/skills/create-delivery-goal/SKILL.md
  - .claude/skills/pipeline-scaffold/SKILL.md
  - CLAUDE.md
outputs_produced:
  - .cronos/pipeline/sg6-skills-regeneration/doc-report-sg6-skills-regeneration.md
  - CLAUDE.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: README.md
    reason: "No changes to public API, CLI commands, or architecture; skill files are self-documenting via SKILL.md frontmatter."
  - path: TESTING.md
    reason: "Test file additions (test_create_delivery_goal_contract.py, test_skill_files_phase_cleanliness.py) are code artifacts, not documentation that needs updating."
  - path: deploy/VPS_SETUP.md
    reason: "Deployment and infrastructure unchanged; skill modifications are runtime-only."
  - path: docs/delivery-pipeline/README.md
    reason: "Delivery pipeline docs do not list individual skills; architecture and runtime patterns unchanged."
metrics:
  tool_calls: 12
  files_read: 7
  memory_hits: 0
  docs_updated: 1
  docs_considered: 5
---

## Summary

SG6 implementation reorganized the skill layer for delivery-workflow goal creation. The core change: **create-goal** now coordination-only (CC-v1 phase tree removed), **create-delivery-goal** is the new canonical entry point for delivery goals (binds to runner via `<!-- delivery-workflow: spec_path -->` sentinel), and **pipeline-scaffold** is DEPRECATED. Updated CLAUDE.md Registered skills table: added create-delivery-goal entry (+1 row), documented that pipeline-scaffold is now deprecated (not added to table, as deprecated skills are not listed). Skill files are self-documenting via SKILL.md frontmatter; no separate docs need updating. Test files (2 new) are code artifacts, not documentation.

## Updated docs

| File | Change summary |
|------|----------------|
| CLAUDE.md | Added [create-delivery-goal](.claude/skills/create-delivery-goal/) row to Registered skills table with purpose describing sentinel-driven runner binding. |

## Intentionally not updated

- **README.md** — No changes to public API, CLI commands, or architecture; skill files are self-documenting via SKILL.md frontmatter.
- **TESTING.md** — Test file additions (test_create_delivery_goal_contract.py, test_skill_files_phase_cleanliness.py) are code artifacts, not documentation that needs updating.
- **deploy/VPS_SETUP.md** — Deployment and infrastructure unchanged; skill modifications are runtime-only.
- **docs/delivery-pipeline/README.md** — Delivery pipeline docs do not list individual skills; architecture and runtime patterns unchanged.

## Assumptions

- Skill files (SKILL.md) are canonical, self-documenting resources; their YAML frontmatter description field is the source of truth for the Registered skills table.
- CLAUDE.md "Registered skills" table is the only user-facing doc that lists skills by name and purpose; changes to skill semantics warrant table updates.
- pipeline-scaffold is intentionally omitted from the Registered skills table because it is deprecated; the SKILL.md frontmatter description contains `[DEPRECATED — use /create-delivery-goal instead]` which is sufficient for users consulting that file directly.
- Implementation did not introduce new architecture, data models, or API changes that would require updates to README.md architecture section.
- Memory hits: 0 (no memory entries were needed for this doc-sync pass; skill changes are self-contained and don't require historical context).

## Open questions

- None.

## Next consumer brief

The Cronos skill ecosystem has been updated to support the new delivery-workflow runner model. Users creating pipeline goals should now invoke `/create-delivery-goal` (with `<!-- delivery-workflow: spec_path -->` sentinel in the brief) instead of `/create-goal` with manually-specified phase tasks. The CLAUDE.md Registered skills table reflects this change. The old `/pipeline-scaffold` skill is deprecated and marked as such in its frontmatter; the entry has been removed from the Registered skills table. No action required by the user — the documentation is now accurate and ready for consumption.
