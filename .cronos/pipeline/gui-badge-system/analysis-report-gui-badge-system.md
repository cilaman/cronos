---
cc_version: '1.0'
agent: pipeline-analyst
slug: gui-badge-system
phase: analysis
status: done
confidence: 0.88
inputs_used:
- memory:GUI Refactor Board Setup
- memory:gui-tokens-brand RESOLVED
- memory:gui-layout-primitives review RESOLVED
- .cronos/pipeline/gui-badge-system/scout-report-gui-badge-system.md
- docs/ui-ux-review/02-design-system.md
- frontend/src/index.css
- frontend/tailwind.config.js
outputs_produced:
- .cronos/pipeline/gui-badge-system/analysis-report-gui-badge-system.md
blockers: []
next_consumer: design
request: "GUI badge system — tone-driven Badge component (Phase 2)\n\nShips a single\
  \ `<Badge tone=…>` component that replaces 63 raw Tailwind-palette\nclasses duplicated\
  \ across 8+ files. Currently P1=red is defined in 4+ places and none\nof these colors\
  \ adapt to the neon theme. After this phase all badges are theme-aware.\n\n**Concrete\
  \ changes:**\n- `Badge.tsx`: the §2.1 recipe — `inline-flex items-center gap-1 rounded-sm\
  \ px-1.5 py-0.5\n  font-mono text-[10px] uppercase tracking-wide ring-1 ring-inset\n\
  \  bg-{tone}/12 text-{tone} ring-{tone}/30`. Tones: running/success/info/warning/danger/\n\
  \  neutral/goal/feature/fix/issue/plan/ask.\n- `badgeTone.ts`: helpers mapping priority(1–5)/TaskState/type/AgentMode/run-status\n\
  \  to tone strings.\n- Migrate badge sites: Card.tsx (PRIORITY_BADGE_STYLES, TYPE_BADGE_STYLES,\
  \ task state),\n  Detail.tsx:280–352 (duplicate maps), TaskForm.tsx:9–15, FeatureForm.tsx,\n\
  \  FeatureDetail.tsx (FEATURE_STATE_BADGE + type map), ConversationEntry.tsx:35–49\n\
  \  (MODEL_COLOR, AGENT_TYPE_COLOR), HarnessRunsPage.tsx:14.\n- Fix RunOverlay.tsx:119\
  \ raw hex `#22c55e` → `--color-running` CSS variable.\n- Delete all duplicated `*_BADGE_STYLES`\
  \ / `*_COLOR` objects.\n\n**Exit criteria:** zero raw palette classes in badge logic;\
  \ badges adapt correctly in\nneon theme; `npm run build` + `npm test` green.\n\n\
  Scope: frontend/src/components/ui/Badge.tsx, frontend/src/utils/badgeTone.ts, frontend/src/components/Card.tsx,\
  \ frontend/src/pages/Detail.tsx, frontend/src/components/TaskForm.tsx, frontend/src/components/FeatureForm.tsx,\
  \ frontend/src/pages/FeatureDetail.tsx, frontend/src/components/ConversationEntry.tsx,\
  \ frontend/src/pages/HarnessRunsPage.tsx, frontend/src/components/harness/RunOverlay.tsx"
has_ui: true
coverage_summary:
  searched:
  - frontend/src/index.css
  - frontend/tailwind.config.js
  - frontend/src/components/ (via scout)
  - frontend/src/pages/ (via scout)
  - docs/ui-ux-review/ (via scout)
  - .cronos/pipeline/gui-badge-system/
  excluded:
  - backend/: frontend-only feature
  - frontend/src/**/*.test.tsx: implementation concern, not analysis
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: Phase 0 status and categorical token declarations must be present in
    index.css and registered in tailwind.config.js before any badge logic is written.
  acceptance_criteria:
  - Given the feature/gui-refactor branch, when index.css is inspected, then --color-running,
    --color-success, --color-info, --color-warning, --color-danger, --color-neutral,
    --brand, --cat-goal, --cat-feature, --cat-fix, --cat-issue, --cat-plan, --cat-ask
    are defined under :root, .dark, and .neon.
  - tailwind.config.js exposes running, success, info, neutral, goal, feature, fix,
    issue, plan, and ask as Tailwind color utilities using the rgb(var(--color-*)
    / <alpha-value>) pattern.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R2
  statement: A Badge component exists at frontend/src/components/ui/Badge.tsx that
    accepts a required tone prop and an optional children prop and renders using the
    §2.1 recipe.
  acceptance_criteria:
  - Given tone='running', when <Badge tone='running'>active</Badge> is rendered, then
    the element has classes inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5
    font-mono text-[10px] uppercase tracking-wide ring-1 ring-inset bg-running/12
    text-running ring-running/30.
  - 'The tone prop accepts exactly 12 values: running, success, info, warning, danger,
    neutral, goal, feature, fix, issue, plan, ask.'
  - Badge is directly importable from frontend/src/components/ui/Badge.tsx.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R3
  statement: A badgeTone.ts utility module exists at frontend/src/utils/badgeTone.ts
    exporting deterministic tone-mapping helpers for all badge contexts.
  acceptance_criteria:
  - 'getTonePriority(priority: 1|2|3|4|5) returns danger/warning/neutral/info/neutral
    respectively.'
  - 'getToneTaskState(state: TaskState) returns running/warning/success/neutral/neutral
    for active/waiting/done/backlog/archived respectively.'
  - 'getToneType(type: string) returns goal/feature/fix/issue for the four task types.'
  - 'getToneMode(mode: AgentMode) returns plan/ask/neutral for plan/ask/auto modes.'
  - 'getToneRunStatus(status: string) returns running/warning/success/danger/neutral
    for running/waiting/done/failed/other statuses.'
  - 'getToneFeatureState(state: FeatureState) returns neutral/goal/plan/warning/success
    for backlog/planned/processing/waiting/done respectively.'
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: Card.tsx migrates all inline badge style maps (PRIORITY_BADGE_STYLES,
    MODE_STYLES, TYPE_BADGE_STYLES, STATE_BADGE_STYLES) to use <Badge> with badgeTone
    helpers, deleting the map objects.
  acceptance_criteria:
  - PRIORITY_BADGE_STYLES, MODE_STYLES, TYPE_BADGE_STYLES, and STATE_BADGE_STYLES
    constants are removed from Card.tsx.
  - Badge rendering in Card.tsx uses <Badge tone={...}> with tone derived from badgeTone
    helpers.
  - No raw Tailwind palette color classes (e.g. bg-red-500, text-emerald-400) remain
    in badge-related JSX in Card.tsx.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R5
  statement: Detail.tsx migrates its duplicate PRIORITY_BADGE_STYLES and TYPE_BADGE_STYLES
    (lines 280-352) to use <Badge> with badgeTone helpers, deleting the map objects.
  acceptance_criteria:
  - PRIORITY_BADGE_STYLES and TYPE_BADGE_STYLES are removed from Detail.tsx.
  - Badge rendering in Detail.tsx uses <Badge tone={...}> with tone from badgeTone
    helpers.
  - No raw Tailwind palette color classes remain in badge-related JSX in Detail.tsx.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R6
  statement: TaskForm.tsx and FeatureForm.tsx migrate their duplicate PRIORITY_OPTIONS
    badge color fields to use tone references or remove them in favour of a shared
    badgeTone lookup.
  acceptance_criteria:
  - The cls or className field in PRIORITY_OPTIONS within TaskForm.tsx and FeatureForm.tsx
    no longer contains raw Tailwind palette classes.
  - Any badge rendered from PRIORITY_OPTIONS uses <Badge tone={getTonePriority(priority)}>.
  verifying_phase: review
  confidence: 0.85
- requirement_id: R7
  statement: FeatureDetail.tsx migrates FEATURE_STATE_BADGE and the inline type badge
    map to use <Badge> with badgeTone helpers, deleting the map objects.
  acceptance_criteria:
  - FEATURE_STATE_BADGE is removed from FeatureDetail.tsx.
  - Inline type badge logic at lines 145-149 is replaced with <Badge tone={getToneType(type)}>.
  - No raw Tailwind palette color classes remain in badge-related JSX in FeatureDetail.tsx.
  verifying_phase: review
  confidence: 0.88
- requirement_id: R8
  statement: ConversationEntry.tsx migrates MODEL_COLOR and AGENT_TYPE_COLOR to semantic
    tone-based badge rendering using <Badge>.
  acceptance_criteria:
  - MODEL_COLOR and AGENT_TYPE_COLOR constants are removed from ConversationEntry.tsx.
  - Model and agent type labels in ConversationEntry.tsx render via <Badge tone={...}>
    using appropriate badgeTone helpers.
  - No raw Tailwind palette color classes (e.g. text-purple-400, text-emerald-400)
    remain in badge-related JSX in ConversationEntry.tsx.
  verifying_phase: review
  confidence: 0.82
- requirement_id: R9
  statement: HarnessRunsPage.tsx migrates RUN_BADGE_STYLE to use <Badge> with getToneRunStatus,
    deleting the map object.
  acceptance_criteria:
  - RUN_BADGE_STYLE is removed from HarnessRunsPage.tsx.
  - Run status badges in HarnessRunsPage.tsx use <Badge tone={getToneRunStatus(status)}>.
  - No raw Tailwind palette color classes remain in run-status badge JSX.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R10
  statement: 'RunOverlay.tsx replaces the hardcoded hex color #22c55e with the --color-running
    CSS variable reference.'
  acceptance_criteria:
  - The string '#22c55e' does not appear in RunOverlay.tsx.
  - The done edge stroke uses rgb(var(--color-running)) or the Tailwind running color
    utility.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R11
  statement: After migration, zero raw Tailwind palette color classes remain in any
    badge-related JSX across all 10 scope files.
  acceptance_criteria:
  - A grep for bg-{red,orange,amber,teal,sky,emerald,violet,rose,indigo,purple}-{shade}
    in badge JSX contexts across scope files returns zero matches.
  - A grep for text-{red,orange,amber,teal,sky,emerald,violet,rose,indigo,purple}-{shade}
    in badge JSX contexts across scope files returns zero matches.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R12
  statement: Badges render correctly and are visually distinguishable in all three
    themes (light, dark, neon) at WCAG AA 4.5:1 minimum contrast for the tone text
    on the tinted fill.
  acceptance_criteria:
  - In the neon theme, running/success/warning/danger/info tones produce visually
    distinct colors that are not identical to their light or dark theme values.
  - Each tone's text color on bg-{tone}/12 achieves 4.5:1 contrast against the fill
    in each theme (validated by design review or automated contrast check).
  verifying_phase: manual
  confidence: 0.75
- requirement_id: R13
  statement: npm run build and npm test pass with zero new failures after all migrations.
  acceptance_criteria:
  - npm run build exits 0 with no TypeScript or Tailwind errors.
  - npm test exits 0; all pre-existing tests continue to pass; new Badge and badgeTone
    unit tests are green.
  verifying_phase: test
  confidence: 0.92
metrics:
  tool_calls: 14
  files_read: 4
  memory_hits: 3
---

## Summary

This feature consolidates 63 duplicated raw Tailwind palette classes spread across 8+ frontend files into a single tone-driven `<Badge tone=...>` component backed by 13 semantic CSS tokens (6 status + 6 categorical + 1 brand). The core deliverables are: (1) a new `Badge.tsx` UI primitive using the one-recipe approach from design system §2.1, (2) a `badgeTone.ts` utility mapping all domain enumerations (priority, TaskState, type, AgentMode, FeatureState, run-status) to tone strings, and (3) migration of all 8 badge sites to delete duplicated style maps and render via `<Badge>`. A critical prerequisite is that Phase 0 status and categorical tokens exist in `index.css` and `tailwind.config.js` on the `feature/gui-refactor` branch — a direct audit of the branch HEAD confirms that the doc commit for `gui-layout-primitives` (01d5710) again removed these tokens, repeating the sibling-phase revert pattern; the implementor must restore them before writing badge logic.

## Scope

### In scope
- New `frontend/src/components/ui/Badge.tsx` component (12 tones, §2.1 recipe)
- New `frontend/src/utils/badgeTone.ts` tone-mapping helpers (priority, TaskState, type, AgentMode, FeatureState, run-status)
- Restore Phase 0 tokens (`--color-running`, `--color-success`, `--color-info`, `--color-neutral`, `--brand`, `--cat-*`) in `index.css` and `tailwind.config.js` if absent from feature branch HEAD (they were dropped in commit 01d5710)
- Migration of all badge sites: Card.tsx, Detail.tsx, TaskForm.tsx, FeatureForm.tsx, FeatureDetail.tsx, ConversationEntry.tsx, HarnessRunsPage.tsx, RunOverlay.tsx
- Deletion of all duplicated `*_BADGE_STYLES` / `*_COLOR` objects from all scope files
- Unit tests for Badge.tsx and badgeTone.ts
- Fix RunOverlay.tsx hardcoded hex `#22c55e` -> CSS variable

### Out of scope
- Backend changes of any kind
- Non-badge UI styling changes (typography, spacing, radius enforcement — separate subgoals)
- ToolBlock.tsx and AdoptedToolTelemetry.tsx (not in the request's explicit scope list)
- WCAG automated tooling setup (manual review per R12)
- New component primitives other than Badge (Button, Modal, PageHeader — separate subgoals)

### Deferred
- Dynamic dot/icon-only Badge variant (compact mode with `title`/`aria-label`) — referenced in design-system guardrails but not in request exit criteria
- Badge usage in files added after this phase being enforced by a lint rule
- Storybook/visual regression testing for badge themes

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Phase 0 CSS/Tailwind badge tokens present in feature/gui-refactor before badge logic begins |
| R2 | Badge.tsx component with 12-tone prop using the §2.1 class recipe |
| R3 | badgeTone.ts with deterministic helpers for all badge contexts |
| R4 | Card.tsx badge maps removed and replaced with Badge + badgeTone |
| R5 | Detail.tsx duplicate badge maps removed and replaced with Badge + badgeTone |
| R6 | TaskForm.tsx and FeatureForm.tsx PRIORITY_OPTIONS badge classes replaced |
| R7 | FeatureDetail.tsx FEATURE_STATE_BADGE and inline type map removed |
| R8 | ConversationEntry.tsx MODEL_COLOR and AGENT_TYPE_COLOR removed |
| R9 | HarnessRunsPage.tsx RUN_BADGE_STYLE removed |
| R10 | RunOverlay.tsx hardcoded hex #22c55e replaced with CSS variable |
| R11 | Zero raw Tailwind palette color classes remain in badge-related JSX across all scope files |
| R12 | Badges are visually distinguishable and WCAG AA compliant in all three themes |
| R13 | npm run build and npm test green with no regressions |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]`
array (the machine-readable source of truth). The body summary below mirrors them
in compact form for the human reader.

- R1 — All 13 CSS tokens in index.css for :root/.dark/.neon; Tailwind config exposes them as color utilities
- R2 — Badge renders §2.1 classes; accepts exactly 12 tone values; importable from ui/
- R3 — Six helper functions with specified return values for all domain enum inputs
- R4 — PRIORITY_BADGE_STYLES, MODE_STYLES, TYPE_BADGE_STYLES, STATE_BADGE_STYLES deleted; zero raw palette classes in badge JSX
- R5 — PRIORITY_BADGE_STYLES and TYPE_BADGE_STYLES deleted from Detail.tsx; zero raw palette classes
- R6 — No raw Tailwind palette classes in PRIORITY_OPTIONS badge fields; Badge component used
- R7 — FEATURE_STATE_BADGE deleted; inline type badge replaced with Badge; zero raw palette classes
- R8 — MODEL_COLOR and AGENT_TYPE_COLOR deleted; Badge used; zero raw palette classes
- R9 — RUN_BADGE_STYLE deleted; Badge used; zero raw palette classes
- R10 — '#22c55e' absent from RunOverlay.tsx; done edge uses rgb(var(--color-running))
- R11 — Grep audit finds zero raw Tailwind palette color class matches in badge JSX across all 10 scope files
- R12 — Neon-theme badges visually distinct; 4.5:1 contrast confirmed per tone per theme
- R13 — npm run build exit 0; npm test exit 0; no regressions

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML
`traceability[]` array. Downstream agents read the YAML directly; this section
exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Phase 0 CSS/Tailwind badge tokens present in feature/gui-refactor before badge logic |
| R2 | test | Badge.tsx with 12-tone prop using the §2.1 class recipe |
| R3 | test | badgeTone.ts with deterministic helpers for all badge contexts |
| R4 | review | Card.tsx badge maps removed and replaced with Badge + badgeTone |
| R5 | review | Detail.tsx duplicate badge maps removed and replaced with Badge + badgeTone |
| R6 | review | TaskForm.tsx and FeatureForm.tsx PRIORITY_OPTIONS badge classes replaced |
| R7 | review | FeatureDetail.tsx FEATURE_STATE_BADGE and inline type map removed |
| R8 | review | ConversationEntry.tsx MODEL_COLOR and AGENT_TYPE_COLOR removed |
| R9 | review | HarnessRunsPage.tsx RUN_BADGE_STYLE removed |
| R10 | test | RunOverlay.tsx hardcoded hex #22c55e replaced with CSS variable |
| R11 | test | Zero raw palette color classes in badge-related JSX across all scope files |
| R12 | manual | Badges visually distinguishable and WCAG AA compliant in all three themes |
| R13 | test | npm run build and npm test green with no regressions |

## Assumptions

- `has_ui: true` rationale: this is entirely a frontend component and migration task — all 10 scope files are React/TypeScript UI components.
- The `feature/gui-refactor` branch is the working branch for implementation. Direct git inspection of branch HEAD (01d5710) confirms the Phase 0 tokens were removed by the `gui-layout-primitives` doc commit — the same sibling-phase revert pattern as documented in `observation_impl_reverts_sibling_phase`. The implementor must restore from commit 4c9e272 before proceeding.
- The 12 tones are exhaustive for all badge contexts across the 10 scope files. The scout confirmed all existing badge style maps map to these 12 tones.
- ConversationEntry.tsx MODEL_COLOR and AGENT_TYPE_COLOR are to be migrated to full `<Badge>` rendering. The request is explicit and includes ConversationEntry.tsx in scope with those constants named.
- Priority mapping P1-danger, P2-warning, P3-neutral, P4-info, P5-neutral follows the hot-to-cool ramp in design system §2.1 ("P1 danger to P2 warning to P3 neutral to P4 info to P5 neutral/faint").
- `warning` and `danger` tokens already exist in `index.css` and `tailwind.config.js` for all three themes and do not need to be added — only the missing status and categorical tokens need restoration.
- Token RGB values must follow the values from commit 4c9e272 as the authoritative source for this branch, since the feature branch HEAD is currently missing them.

## Open questions

- None. Design system documentation, scout findings, and codebase evidence are fully aligned. The Phase 0 token revert is a known implementation constraint, not an analysis ambiguity.

## Next consumer brief

Design agent: read `traceability[]` (R1-R13) and `## Scope` first.

Key decision points for iteration planning:

1. **Iteration ordering constraint (R1 must be I1):** Verify and restore Phase 0 tokens in `index.css` and `tailwind.config.js` on `feature/gui-refactor` before any Badge component work. Commit 4c9e272 is the authoritative source for token values. This concrete I1 gates all other iterations.

2. **Tailwind config gap:** `tailwind.config.js` currently exposes only `warning` and `danger` as semantic tokens. A dedicated iteration must add `running`, `success`, `info`, `neutral`, `goal`, `feature`, `fix`, `issue`, `plan`, `ask` (and `brand`) to the `colors` block using `rgb(var(--color-*) / <alpha-value>)` for status tokens and `rgb(var(--cat-*) / <alpha-value>)` for categorical tokens.

3. **badgeTone.ts design choice:** The design agent may choose a single `getTone(context, value)` dispatcher or separate per-context helpers. Either is valid; document the choice in the design report.

4. **R8 design decision (ConversationEntry.tsx):** MODEL_COLOR uses `text-{color}-400` (text-only, no bg/ring), which differs from the full badge recipe. If these labels should remain inline colored text rather than full badge elements, document this as a design deviation rather than excluding them from the deletion requirement.

5. **Suggested iteration batching:** I1 token restoration; I2 Badge.tsx + badgeTone.ts + unit tests; I3 Card.tsx + Detail.tsx migration; I4 Forms migration (TaskForm, FeatureForm, FeatureDetail); I5 ConversationEntry + HarnessRunsPage + RunOverlay migration; I6 grep audit + build/test green gate.
