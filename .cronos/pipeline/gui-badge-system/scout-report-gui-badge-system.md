---
cc_version: "1.0"
agent: pipeline-scout
slug: gui-badge-system
phase: scout
status: done
confidence: 0.88
inputs_used:
  - memory:GUI Refactor Board Setup
  - docs/ui-ux-review/02-design-system.md
  - docs/ui-ux-review/03-consistency-findings.md
  - docs/ui-ux-review/06-brand.md
  - frontend/src/components/Card.tsx
  - frontend/src/components/Detail.tsx
  - frontend/src/components/ConversationEntry.tsx
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/TaskForm.tsx
  - frontend/src/components/FeatureForm.tsx
  - frontend/src/components/harness/RunOverlay.tsx
  - frontend/src/pages/HarnessRunsPage.tsx
  - frontend/src/index.css
outputs_produced:
  - .cronos/pipeline/gui-badge-system/scout-report-gui-badge-system.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - frontend/src/components/ (badge styles, scope files)
    - frontend/src/pages/ (badge definitions)
    - docs/ui-ux-review/ (design system reference)
    - frontend/src/index.css (theme tokens)
  excluded:
    - backend/: out of scope for this UI component
    - test files: scope focus is production code
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "GUI badge system — tone-driven Badge component (Phase 2). Ships a single `<Badge tone=…>` component that replaces 63 raw Tailwind-palette classes duplicated across 8+ files. Currently P1=red is defined in 4+ places and none of these colors adapt to the neon theme. After this phase all badges are theme-aware."
metrics:
  tool_calls: 12
  files_read: 12
  memory_hits: 1
---

## Summary

The brief requires consolidating 63 raw Tailwind badge classes across 11 files into a single tone-driven `<Badge>` component with theme-aware CSS variables. The design system (02-design-system.md §2.1) specifies 12 tones (running/success/info/warning/danger/neutral/goal/feature/fix/issue/plan/ask) mapped to semantic status and categorical type colors. Current state: Badge.tsx and badgeTone.ts do not exist; badge styles are duplicated across Card.tsx, Detail.tsx, FeatureDetail.tsx, TaskForm.tsx, FeatureForm.tsx, ConversationEntry.tsx, HarnessRunsPage.tsx, and RunOverlay.tsx. Theme tokens for --running, --success, --info, --warning, --danger, --brand, and categorical tones (--cat-goal, --cat-feature, etc.) are not yet defined in index.css; only the old --warning and --danger exist. Neon theme has no status color tokens. Current badge recipe uses inline `border-{color}-{shade} bg-{color}-{shade}/N` with hand-tuned dark: variants per definition — non-theme-aware.

## Coverage

### Searched
- frontend/src/components/ (Card.tsx, Detail.tsx, ConversationEntry.tsx, FeatureDetail.tsx, TaskForm.tsx, FeatureForm.tsx, ToolBlock.tsx, harness/RunOverlay.tsx)
- frontend/src/pages/ (HarnessRunsPage.tsx)
- docs/ui-ux-review/ (02-design-system.md, 03-consistency-findings.md, 06-brand.md)
- frontend/src/index.css (current theme variables and structure)

### Excluded
- backend/: not in scope for UI component
- test files: focused on production code structure

### Strategies
- memory_retrieval: 1 hit (GUI Refactor Board Setup identifying 8 CC-v1 subgoals; this is SG3)
- glob_structural: identified 11 scope files and 3 design docs (02/03/06)
- grep_symbol: located PRIORITY_BADGE_STYLES, TYPE_BADGE_STYLES, STATE_BADGE_STYLES, MODE_STYLES, FEATURE_STATE_BADGE, RUN_BADGE_STYLE, MODEL_COLOR, AGENT_TYPE_COLOR, hex #22c55e
- read_targeted: extracted exact style definitions and mapped to design system tones

## Findings

### Design System Reference
- **02-design-system.md §2.1** specifies the complete badge token system: six status tokens (`--running`, `--success`, `--warning`, `--danger`, `--info`, `--neutral`) + one brand identity token (`--brand`) + six categorical tokens (`--cat-goal`, `--cat-feature`, `--cat-fix`, `--cat-issue`, `--cat-plan`, `--cat-ask`).
- **One badge recipe** (§2.1): `inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ring-1 ring-inset bg-{tone}/12 text-{tone} ring-{tone}/30`.
- **06-brand.md §6.4** defines how brand state palette values map to themes: light uses contrast-safe darker shades (e.g., lime-700 `77 124 15`), dark/neon use brand values directly (e.g., lime `184 255 92`). Full token table:
  - `--running`: lime-700 (light) / lime-184-255-92 (dark/neon)
  - `--success`: cyan-600 (light) / cyan-46-196-255 (dark/neon)
  - `--warning`: amber-700 (light) / amber-255-166-46 (dark/neon)
  - `--danger`: red-700 (light) / red-255-110-92 (dark/neon)
  - `--info`: sky-700 (light) / sky-56-189-248 (dark/neon)
  - `--neutral`: ink-faint (light/dark/neon)
  - `--brand`: violet-122-79-176 (all themes, identity only)
- **03-consistency-findings.md §3.1** documents the bug: "63 raw Tailwind-palette classes bypass the token system" with 4+ separate definitions of P1=red in different files. Neon case shows "cyan accent but badges stay emerald/red" — badges are not theme-aware.

### Current Badge Style Inventory

**Card.tsx (lines 73–121):**
- PRIORITY_STYLES (5 priorities): red, orange, amber, teal, neutral
- MODE_STYLES (3 modes): indigo, neutral, violet
- TYPE_BADGE_STYLES (4 types): violet, orange, emerald, rose
- STATE_BADGE_STYLES (5 states): neutral, emerald, amber, sky, neutral/faint

**Detail.tsx (lines 280–352):**
- PRIORITY_BADGE_STYLES (5 priorities): **identical to Card.tsx**
- TYPE_BADGE_STYLES (2 types): violet, orange

**FeatureDetail.tsx (lines 9–19):**
- FEATURE_STATE_BADGE (5 states): neutral, violet, indigo, amber, sky
- Inline type badge (lines 145–149): rose (fix), emerald (feature)

**TaskForm.tsx (lines 9–15):**
- PRIORITY_OPTIONS (5 priorities): **identical to Card.tsx/Detail.tsx** (defines both label and cls)

**FeatureForm.tsx (lines 8–14):**
- PRIORITY_OPTIONS (5 priorities): **identical to TaskForm.tsx/Card.tsx/Detail.tsx**

**ConversationEntry.tsx (lines 35–49):**
- MODEL_COLOR (3 models): purple-400, accent-bright, emerald-400
- AGENT_TYPE_COLOR (7 agent types): sky-400, purple-400, emerald-400, emerald-300, rose-400, amber-400, accent-bright

**HarnessRunsPage.tsx (lines 15–20):**
- RUN_BADGE_STYLE (4 run statuses): amber, accent, danger, neutral

**RunOverlay.tsx (line 119):**
- Hardcoded hex `#22c55e` (emerald) for "done" edge color

### Color Palette Audit

| Palette | Usage | Files | Duplicates | Theme-Aware |
|---------|-------|-------|-----------|------------|
| Red (P1) | priority | Card, Detail, TaskForm, FeatureForm | ✓ ✓ ✓ ✓ | No, hand `dark:` only |
| Orange (P2, issue) | priority, type | Card, Detail, TaskForm, ConversationEntry | ✓ ✓ ✓ | No, hand `dark:` only |
| Amber (P3, waiting, running) | priority, state, run | Card, Detail, TaskForm, HarnessRunsPage | ✓ ✓ ✓ | No, hand `dark:` only |
| Teal (P4) | priority | Card, Detail, TaskForm | ✓ ✓ | No, hand `dark:` only |
| Sky (done state, info) | state, agent | Card, FeatureDetail, ConversationEntry | ✓ ✓ | No, hand `dark:` only |
| Emerald (active, feature, haiku) | state, type, agent | Card, FeatureDetail, ConversationEntry | ✓ ✓ | No; **fails in neon** (neon has cyan, not emerald) |
| Violet (goal, ask, plan) | type, mode, agent | Card, Detail, ConversationEntry | ✓ ✓ ✓ | No, hand `dark:` only |
| Rose (fix, security-officer) | type, agent | Card, FeatureDetail, ConversationEntry | ✓ ✓ | No, hand `dark:` only |
| Indigo (plan mode, planned state) | mode, feature-state | Card, FeatureDetail, ConversationEntry | ✓ ✓ | No, hand `dark:` only |
| Accent (done run, claude agent, user role) | run, agent, role | HarnessRunsPage, ConversationEntry | ✓ ✓ | **Yes, theme-aware** ✓ |

### Tone-to-Semantic Mapping

**Status tones:**
- `running` → active/in-progress (currently emerald in code; design says lime)
- `success` → done/passed (currently sky in code; design says cyan)
- `warning` → waiting/blocked (currently amber)
- `danger` → failed/destructive (currently red)
- `info` → linked/informational (currently sky; not yet used)
- `neutral` → backlog/idle/archived (currently ink-faint/hairline)

**Categorical tones:**
- `goal` → violet (type=goal)
- `feature` → emerald (type=feature)
- `fix` → rose (type=fix)
- `issue` → orange (type=issue)
- `plan` → indigo (mode=plan)
- `ask` → violet (mode=ask)

### Theme Token Gap Analysis

**index.css current state:**

✓ Light theme (`:root`):
- `--color-accent: 21 128 61` (emerald-700)
- `--color-warning: 180 83 9` (amber-700)
- `--color-danger: 185 28 28` (red-700)

✓ Dark theme (`.dark`):
- `--color-accent: 74 222 128` (emerald)
- `--color-warning: 212 166 71` (amber)
- `--color-danger: 168 74 74` (red)

✓ Neon theme (`.neon`):
- `--color-accent: 0 210 255` (cyan)
- `--color-warning: 251 191 36` (amber)
- `--color-danger: 248 113 113` (red)

**Missing tokens for Phase 2:**
- `--running` (lime in dark/neon; lime-700 in light)
- `--success` (cyan in dark/neon; cyan-600 in light)
- `--info` (sky across all themes)
- `--neutral` (reuse ink-faint)
- `--brand` (violet identity, all themes)
- `--cat-goal`, `--cat-feature`, `--cat-fix`, `--cat-issue`, `--cat-plan`, `--cat-ask`

**Neon badge color mismatch example:** Emerald-700/emerald-400 badges will have no neon equivalent (neon has cyan accent + purple accents but no emerald tokens). The design system specifies `--cat-feature: emerald-700 (light) / emerald-400 (dark/neon)` — this category-specific color must be explicitly added to neon theme.

### Risk Flag: Hardcoded Hex

RunOverlay.tsx:119: `stroke: status === 'done' ? '#22c55e' : undefined` — hardcoded emerald hex, must become CSS variable once tokens defined.

## Assumptions
- Design system doc (02-design-system.md §2.1) is the authoritative Badge spec and tone list.
- The 12 tones (6 status + 6 categorical) map exhaustively to all badge use cases (priority, type, mode, state, model, agent, feature-state, run-status).
- Token values in 06-brand.md §6.4 table are the ground truth for RGB triplets per theme.
- All current badge styles use the same recipe structure (inline-flex + border + bg + text + ring); only colors differ.
- Phase 0 (gui-tokens-brand, already shipped per memory) injected brand color tokens into index.css. Implementation assumes those tokens exist; if not, Phase 0 must be revisited.

## Open questions
- None. Design system, brief, and codebase alignment are clear.

## Next consumer brief

**For analyst phase:**

1. **Read first:** 02-design-system.md §2.1 (the one badge recipe), 06-brand.md §6.4 (token values per theme).
2. **Verify** Phase 0 (gui-tokens-brand) completed and injected `--running`, `--success`, `--info`, `--warning`, `--danger`, `--brand`, `--cat-{goal,feature,fix,issue,plan,ask}` into index.css for all three themes. Flag as blocker if missing.
3. **Decision point:** Determine badgeTone.ts design:
   - Single `getTone(context)` function handling all use cases, or
   - Separate helpers (getTonePriority, getToneType, getToneState, getToneMode, getToneAgent, getToneFeatureState, getToneRunStatus) for clarity and tree-shakeability.
4. **Clarification:** ConversationEntry.tsx MODEL_COLOR and AGENT_TYPE_COLOR are *not* badges in the design sense (they are inline text colors). Confirm whether these should migrate to `<Badge>` or stay as semantic text-color tokens (likely stay).
5. **Traceability:** This brief replaces 63 raw classes across 11 files (Card, Detail, FeatureDetail, TaskForm, FeatureForm, ConversationEntry, HarnessRunsPage, RunOverlay, + ToolBlock, AdoptedToolTelemetry if present). Confirm final artifact counts.
6. **Test scope:** Badges must contrast-validate in all three themes (light, dark, neon) with 4.5:1 minimum for text on colored fill per WCAG AA.
