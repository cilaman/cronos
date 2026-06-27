# delivery-v2 — spec + agent/skill drafts

Specification and runtime artifacts for delivery pipeline **v2**, extending delivery/v1 with a
security-review stage and a self-improvement (retro → improve) loop. Tool evolution is
out of scope and stays in Cronos (see spec §4).

Grounded in `cronos@def4354e` (read 2026-06-26).

## Contents

```
delivery-v2/
├── delivery-v2-spec.md            # the canonical spec — read this first
├── agents/
│   ├── security-reviewer.md       # F1 agent — DRAFT, ready to drop in
│   └── retro.md                   # F2 agent — DRAFT, ready to drop in
└── skills/
    ├── security-review/SKILL.md   # F1 method — DRAFT (paired with security-reviewer.md)
    └── retro/SKILL.md             # F2 method — DRAFT (paired with retro.md)
```

## What is ready vs. what is spec-only

| Piece | State | Notes |
|---|---|---|
| `delivery-v2-spec.md` | **canonical** | scope, designs, graph deltas, schema/interface changes, 4-phase build plan with acceptance checkboxes, risks, open decisions |
| `agents/security-reviewer.md` + `skills/security-review/SKILL.md` | **drafted** | the agentic layer of F1 — these ARE the implementation (the harness loads them as prompts), not docs about it |
| `agents/retro.md` + `skills/retro/SKILL.md` | **drafted** | the agentic layer of F2 |
| `_check_security` gate handler, `improve` applier, workflow-YAML edits, schema enum change | **spec-only** | build in-repo against the real `gate.py` / `auto_improver.py` / package types — see the acceptance-criteria checkboxes in the spec |

The drafts are intentionally shaped to the v1 `reviewer` / `code-review` exemplar: a thin agent
(role + inputs + hard rules + the `delivery_status` fence) paired with a skill that carries the
method. Paths are taken from the runtime — nothing hardcodes `/data/spaces/...`.

## Two decisions still open (spec §8)
1. **Security placement** — sequential after `g-review` (recommended) vs. parallel join.
2. **Contract-versioning for delivery/v1** — define one, or scope version-bumping out of Tier 0.

## Where each draft was harvested from
- `security-reviewer.md` / `security-review` ← `.claude/agents/security-officer.md` (OWASP sweeps,
  dep-audit) reshaped to the delivery/v1 agent contract.
- `retro.md` / `retro` ← `.claude/agents/pipeline-retro.md` (scoring + finding discipline) and the
  `.claude/skills/evaluate-run` rubric, re-targeted from CC-v1 state to delivery/v1
  `state.json` + `events.jsonl` + `RunTrace`, with the fix_type enum adapted to delivery/v1
  surfaces and the tier mapping preserved.
