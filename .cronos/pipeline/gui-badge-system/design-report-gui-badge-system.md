---
cc_version: '1.0'
agent: pipeline-architect
slug: gui-badge-system
phase: design
status: done
confidence: 0.84
inputs_used:
- memory:GUI Refactor Board Setup
- memory:gui-tokens-brand RESOLVED
- memory:gui-layout-primitives review RESOLVED
- memory:observation_impl_reverts_sibling_phase
- memory:Worktree main vs workspace
- memory:Pipeline narrow -k coverage floor
- .cronos/pipeline/gui-badge-system/analysis-report-gui-badge-system.md
- .cronos/pipeline/gui-badge-system/scout-report-gui-badge-system.md
- frontend/src/index.css
- frontend/tailwind.config.js
- frontend/src/components/Card.tsx
- frontend/src/components/ui/
outputs_produced:
- .cronos/pipeline/gui-badge-system/design-report-gui-badge-system.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - .cronos/pipeline/gui-badge-system/
  - frontend/src/index.css
  - frontend/tailwind.config.js
  - frontend/src/components/Card.tsx
  - frontend/src/components/ui/
  excluded:
  - backend/: frontend-only feature
  - frontend/src/components/ToolBlock.tsx: not in analyst scope
  - frontend/src/components/AdoptedToolTelemetry.tsx: not in analyst scope
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: infra
  scope_files:
  - frontend/src/index.css
  - frontend/tailwind.config.js
  - frontend/tests/index.css.test.ts
  validation_command: cd frontend && npm test -- tests/index.css.test.ts
  max_diff_lines: 250
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/components/ui/Badge.tsx
  - frontend/src/utils/badgeTone.ts
  - frontend/src/components/ui/__tests__/Badge.test.tsx
  - frontend/src/utils/__tests__/badgeTone.test.ts
  validation_command: cd frontend && npm test -- src/components/ui/__tests__/Badge.test.tsx
    src/utils/__tests__/badgeTone.test.ts
  max_diff_lines: 400
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/components/Card.tsx
  - frontend/src/components/Detail.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Card.test.tsx
    src/components/__tests__/Detail.test.tsx
  max_diff_lines: 350
  depends_on:
  - I2
- id: I4
  type: frontend
  scope_files:
  - frontend/src/components/TaskForm.tsx
  - frontend/src/components/FeatureForm.tsx
  - frontend/src/pages/FeatureDetail.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/TaskForm.test.tsx
    src/components/__tests__/FeatureForm.test.tsx src/pages/__tests__/FeatureDetail.test.tsx
  max_diff_lines: 300
  depends_on:
  - I2
- id: I5
  type: frontend
  scope_files:
  - frontend/src/components/ConversationEntry.tsx
  - frontend/src/pages/HarnessRunsPage.tsx
  - frontend/src/components/harness/RunOverlay.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/ConversationEntry.test.tsx
    src/pages/__tests__/HarnessRunsPage.test.tsx src/components/harness/__tests__/RunOverlay.test.tsx
  max_diff_lines: 300
  depends_on:
  - I2
- id: I6
  type: frontend
  scope_files:
  - frontend/tests/no-raw-palette-classes.test.ts
  validation_command: cd frontend && npm run build && npm test -- tests/no-raw-palette-classes.test.ts
  max_diff_lines: 200
  depends_on:
  - I3
  - I4
  - I5
risks:
- description: Phase 0 sibling-phase revert pattern (memory:observation_impl_reverts_sibling_phase).
    The feature/gui-refactor HEAD (01d5710) again removed Phase 0 status/categorical/brand
    tokens that were restored by 4c9e272. If the implementor of I1 grabs a stale local
    checkout, they may either redundantly re-restore tokens or miss the revert entirely
    — leaving I2 with no working Tailwind colors.
  severity: high
  mitigation: I1 implementor MUST verify `git log --oneline -5 feature/gui-refactor`
    shows 01d5710 as HEAD, then diff index.css and tailwind.config.js against 4c9e272
    to confirm the gap before writing. Restoration source is exactly the additions
    shown in commit 4c9e272 for the two files. I1 validation runs frontend/tests/index.css.test.ts
    which already encodes the Phase 0 expectations (created in commit 4c9e272).
- description: Worktree-vs-main confusion (memory:Worktree main vs workspace). Sub-agents
    historically edit the main worktree but the goal commits from the workspace worktree.
    Files written by implementor to /data/spaces/cronos-development/frontend/... may
    not appear in the workspace tree where goal-task-commit runs.
  severity: medium
  mitigation: Each implementor MUST verify cwd via `git rev-parse --show-toplevel`
    and `git rev-parse --abbrev-ref HEAD` before writing. The workspace path is /data/spaces/cronos-development/.cronos/workspaces/2026-06-22-1335-design-gui-badge-system;
    the implementor should resolve scope_files relative to whichever worktree is on
    feature/gui-refactor. If editing in main worktree, copy files into workspace before
    commit.
- description: Narrow pytest/vitest -k or single-file validation against a coverage
    floor will fail (memory:Pipeline narrow -k coverage floor). Frontend uses vitest;
    its config may or may not enforce a coverage floor on `npm test`. If running a
    narrow test file fails coverage, the implementor will misread it as a real failure.
  severity: medium
  mitigation: Validation commands target specific test files via `npm test --`. The
    frontend vitest config does NOT enforce --cov-fail-under (verified — that floor
    is backend-only in pyproject.toml). If vitest coverage flags appear later, implementor
    uses `npx vitest run <file>` without coverage to validate, then reports validation_command_passed=true
    with a note.
- description: Badge tone helper return types may drift from existing enum types.
    TaskState, FeatureState, AgentMode, TaskType are defined in frontend/src/types.ts
    as union string literals; getTone* helpers must accept those exact unions or TypeScript
    will complain at call sites in I3-I5.
  severity: medium
  mitigation: 'I2 explicitly imports the union types from src/types.ts and types each
    helper with them: `getToneTaskState(state: TaskState): Tone`. Where the analyst
    spec uses a generic `string`, the helper signature uses the typed union and returns
    the `Tone` literal-union string. badgeTone.test.ts must include a TypeScript compilation
    check (vitest does this automatically when test files import the helpers).'
- description: WCAG AA contrast (R12) is verifying_phase=manual, but implementor token
    values copied from commit 4c9e272 may not actually achieve 4.5:1 on each theme's
    surface. Visual review may fail post-merge.
  severity: low
  mitigation: I1 takes token RGBs verbatim from commit 4c9e272 (the previously-shipped
    Phase 0 baseline) — the same values that already passed the gui-tokens-brand pipeline.
    R12 is deferred to manual review per the analyst; design does not attempt automated
    contrast validation. If manual review fails, a follow-up token-tuning task is
    created outside this phase.
- description: ConversationEntry.tsx MODEL_COLOR/AGENT_TYPE_COLOR use text-only color
    (no bg/ring). Replacing them with the full `<Badge>` recipe changes visual density.
    Analyst R8 says replace; user request says replace; but the change may look heavier
    than current inline colored text.
  severity: low
  mitigation: I5 follows the explicit user request and analyst R8 literally — convert
    to `<Badge tone={...}>` even if visually denser. If post-merge visual review rejects
    the density change, follow-up phase introduces a `<Badge variant='inline'>` text-only
    variant. Document this decision in impl-report-gui-badge-system--i5.md.
metrics:
  tool_calls: 11
  files_read: 7
  memory_hits: 6
  iterations_planned: 6
---

## Summary

This design ships a single `<Badge tone=...>` component plus a `badgeTone.ts` helper module, then migrates 10 frontend scope files to delete duplicated `*_BADGE_STYLES` / `*_COLOR` objects (63 raw Tailwind palette classes total). The DAG is a tight 6-iteration plan: I1 restores Phase 0 status/categorical/brand tokens that were re-reverted by commit 01d5710 (the same sibling-phase revert pattern documented in memory) and wires them into `tailwind.config.js`; I2 ships `Badge.tsx` + `badgeTone.ts` with unit tests; I3-I4-I5 run in parallel after I2 to migrate the badge sites in three thematic groups (Card+Detail, Forms+FeatureDetail, Conversation+HarnessRuns+RunOverlay); I6 is the final grep audit + build gate. The single critical tradeoff: I5's MODEL_COLOR/AGENT_TYPE_COLOR migration converts inline colored text into full badge pills — done deliberately per analyst R8, with a low-severity rollback risk recorded.

## Components

### Data
- No data-layer changes. This is a frontend-only token + component + migration phase.

### Backend
- No backend changes.

### Frontend
- `frontend/src/index.css` — restore 13 CSS variables (6 status + 6 categorical + 1 brand) for `:root`, `.dark`, `.neon` per commit 4c9e272.
- `frontend/tailwind.config.js` — extend `theme.extend.colors` with `running`, `success`, `info`, `neutral`, `brand`, `goal`, `feature`, `fix`, `issue`, `plan`, `ask` mappings using `rgb(var(--color-*) / <alpha-value>)` for status and `rgb(var(--cat-*) / <alpha-value>)` for categorical tones.
- `frontend/src/components/ui/Badge.tsx` — new component. Props: `tone: Tone` (required), `children?: ReactNode`. Renders the §2.1 recipe: `inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ring-1 ring-inset bg-{tone}/12 text-{tone} ring-{tone}/30`. Class assembly uses a frozen tone→classes map so Tailwind's class scanner detects all 12 variants statically.
- `frontend/src/utils/badgeTone.ts` — exports `Tone` union type plus 6 helpers: `getTonePriority(p: 1|2|3|4|5)`, `getToneTaskState(s: TaskState)`, `getToneType(t: TaskType)`, `getToneMode(m: AgentMode)`, `getToneRunStatus(s: string)`, `getToneFeatureState(s: FeatureState)`. Each returns a `Tone` literal.
- `frontend/src/components/Card.tsx` — delete PRIORITY_STYLES/MODE_STYLES/TYPE_BADGE_STYLES/STATE_BADGE_STYLES; render badges via `<Badge tone={...}>`.
- `frontend/src/components/Detail.tsx` — delete PRIORITY_BADGE_STYLES/TYPE_BADGE_STYLES; use `<Badge>`.
- `frontend/src/components/TaskForm.tsx` — remove `cls` field from PRIORITY_OPTIONS; render via `<Badge tone={getTonePriority(p)}>`.
- `frontend/src/components/FeatureForm.tsx` — same pattern as TaskForm.
- `frontend/src/pages/FeatureDetail.tsx` — delete FEATURE_STATE_BADGE; inline type map at lines 145-149 → `<Badge>`.
- `frontend/src/components/ConversationEntry.tsx` — delete MODEL_COLOR and AGENT_TYPE_COLOR; convert labels to `<Badge>` (analyst-confirmed deliberate visual change).
- `frontend/src/pages/HarnessRunsPage.tsx` — delete RUN_BADGE_STYLE; use `<Badge tone={getToneRunStatus(status)}>`.
- `frontend/src/components/harness/RunOverlay.tsx` — replace hex `#22c55e` with `rgb(var(--color-running))`.
- `frontend/tests/no-raw-palette-classes.test.ts` — new repo-wide audit test that greps the 10 scope files for `(bg|text|ring|border)-(red|orange|amber|teal|sky|emerald|violet|rose|indigo|purple)-\d+` and asserts zero matches in badge-adjacent JSX.

## Implementation plan

| ID  | Type     | Depends on | Scope files (abridged)                                                | Validation                                                                  |
|-----|----------|------------|-----------------------------------------------------------------------|-----------------------------------------------------------------------------|
| I1  | infra    | -          | frontend/src/index.css, frontend/tailwind.config.js, tests/index.css.test.ts | cd frontend && npm test -- tests/index.css.test.ts                          |
| I2  | frontend | I1         | components/ui/Badge.tsx, utils/badgeTone.ts, + 2 test files          | cd frontend && npm test -- Badge.test.tsx badgeTone.test.ts                  |
| I3  | frontend | I2         | components/Card.tsx, components/Detail.tsx                            | cd frontend && npm test -- Card.test.tsx Detail.test.tsx                     |
| I4  | frontend | I2         | components/TaskForm.tsx, components/FeatureForm.tsx, pages/FeatureDetail.tsx | cd frontend && npm test -- TaskForm.test.tsx FeatureForm.test.tsx FeatureDetail.test.tsx |
| I5  | frontend | I2         | components/ConversationEntry.tsx, pages/HarnessRunsPage.tsx, harness/RunOverlay.tsx | cd frontend && npm test -- ConversationEntry.test.tsx HarnessRunsPage.test.tsx RunOverlay.test.tsx |
| I6  | frontend | I3, I4, I5 | frontend/tests/no-raw-palette-classes.test.ts                         | cd frontend && npm run build && npm test -- tests/no-raw-palette-classes.test.ts |

DAG layers (Kahn topological sort):
- Layer 0: I1
- Layer 1: I2
- Layer 2: I3, I4, I5 (parallel)
- Layer 3: I6

Cross-iteration invariants (the implementor MUST honour):

- The 12-tone `Tone` union exported from `utils/badgeTone.ts` is the single source of truth for tone strings. Badge.tsx imports `Tone` from `badgeTone.ts`, not the reverse.
- The class assembly inside `Badge.tsx` MUST use a frozen object literal mapping `tone → 'bg-running/12 text-running ring-running/30'` (one entry per tone, 12 entries total). Do NOT use string interpolation like `` `bg-${tone}/12` `` — Tailwind's JIT scanner can't see those classes, so the colors won't compile.
- All migration iterations (I3, I4, I5) MUST import `Badge` from `'./ui/Badge'` (or the page-relative equivalent) and tone helpers from `'../utils/badgeTone'`. No alternative ad-hoc tone strings.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Phase 0 sibling-phase revert pattern: HEAD (01d5710) re-removed status/categorical/brand tokens that 4c9e272 restored. | high | I1 implementor verifies HEAD via `git log --oneline -5`, diffs against 4c9e272, restores exact token values. I1 validation runs the Phase 0 regression test that already exists at frontend/tests/index.css.test.ts (carried over by 4c9e272 — if missing, I1 restores it too). |
| Worktree-vs-main confusion — implementors historically edit main worktree but goal-task-commit runs from workspace. | medium | Implementors verify cwd is on feature/gui-refactor via `git rev-parse --show-toplevel` and `git rev-parse --abbrev-ref HEAD` before writing; copy across worktrees if needed before commit. |
| Narrow vitest validation against a coverage floor would fail spuriously. | medium | Frontend vitest config does NOT enforce coverage floor; validation_commands use `npm test -- <file>` without --coverage. If a regression introduces one, implementor falls back to `npx vitest run <file>`. |
| getTone* helper signatures may drift from `types.ts` union types. | medium | I2 imports TaskState/FeatureState/AgentMode/TaskType from `src/types.ts` and types helpers with them; test file imports same unions and validates compile + runtime mapping. |
| WCAG AA contrast (R12, manual) may fail post-merge on token RGBs copied from 4c9e272. | low | Use commit 4c9e272 RGBs verbatim — they already passed Phase 0 review. Manual review is deferred per analyst; follow-up tuning task created only if review rejects. |
| ConversationEntry MODEL_COLOR/AGENT_TYPE_COLOR conversion changes visual density (inline colored text → badge pills). | low | I5 follows analyst R8 literally; impl-report records the deliberate density change; rollback by adding a `<Badge variant='inline'>` text-only variant in a follow-up phase if needed. |

## Assumptions

- The feature/gui-refactor branch is the working branch. Implementor checks out (or verifies) this branch in the workspace worktree before any iteration.
- `--color-warning` and `--color-danger` already exist in all three themes at the values shown on current HEAD; I1 keeps these values intact and ONLY adds the missing status/categorical/brand tokens.
- Token RGB values come verbatim from commit 4c9e272 (see `git show 4c9e272 -- frontend/src/index.css`). Values were validated by the Phase 0 review at the time and need no re-derivation.
- The 12 tones (running/success/info/warning/danger/neutral + goal/feature/fix/issue/plan/ask) are exhaustive for every badge use case across the 10 scope files — confirmed by scout's color-palette audit table.
- All migration iterations preserve the existing badge text labels (e.g. "P1", "Active", "Goal") and only swap the visual classes — no copy changes.
- The `frontend/tests/index.css.test.ts` Phase 0 regression test exists or will be restored by I1. (Per commit 4c9e272 diff, it was added there. Per commit 01d5710 diff, it may have been removed again — I1 confirms and restores if needed; that work falls inside I1's scope_files via the test file entry.)
- vitest is run via `npm test --`; no coverage floor is enforced on frontend; build is `npm run build`. Both are gated in I6.
- Test files at the paths listed in validation_commands MUST be created by the same iteration that creates/modifies the production code they cover. Where no test file is named in scope_files, the iteration creates a colocated test (e.g. `Card.test.tsx`).

## Open questions

- None. Analyst's open questions are explicitly "None"; scout's open questions are "None". The Phase 0 revert is a known constraint, not an ambiguity.

## Next consumer brief

Implementor: read `iterations[]` and follow layer order. Each iteration is independently mergeable; do NOT batch across iterations.

Key fields per iteration:
- `scope_files[]` — hard boundary. Do not modify any other file (memory:Worktree main vs workspace caveat applies — verify worktree first).
- `validation_command` — run verbatim; report `validation_command_passed: true/false` in impl-report.
- `max_diff_lines` — exceed only by escalating in impl-report `blockers[]`.

Cross-iteration invariants (NOT derivable from YAML — see body §Implementation plan):
1. Badge.tsx class assembly MUST be a frozen object literal keyed by `Tone`, never string interpolation (Tailwind JIT requirement).
2. `Tone` union lives in `utils/badgeTone.ts` and is imported by `Badge.tsx` (one-way dependency).
3. I1 implementor verifies HEAD is 01d5710 and restores tokens to the exact values from `git show 4c9e272 -- frontend/src/index.css frontend/tailwind.config.js`. If HEAD has moved, abort and escalate.

Unresolved issue for implementor to confirm during I1:
- Whether `frontend/tests/index.css.test.ts` is present on HEAD. If absent, I1 also creates it (scope_files already lists it). The test must encode the 13 token presence checks per analysis R1 acceptance criteria.

After I6 passes: phase-gate proceeds to review → doc-sync → commit (no goal-finalize — this is a non-terminal subgoal per the GUI Refactor Board Setup memory).
