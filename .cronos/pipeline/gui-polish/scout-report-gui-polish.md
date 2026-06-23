---
cc_version: "1.0"
agent: pipeline-scout
slug: gui-polish
phase: scout
status: done
confidence: 0.88
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:project_gui_tokens_brand_review_attempt1
  - frontend/src/components/ui/IconButton.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/Lane.tsx
  - frontend/src/components/ui/EmptyState.tsx
  - frontend/src/components/Detail.tsx
  - frontend/src/components/ui/Button.tsx
  - frontend/src/components/ViewPicker.tsx
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/pages/SpaceToolsPage.tsx
  - docs/ui-ux-review/02-design-system.md
  - docs/ui-ux-review/05-roadmap.md
outputs_produced:
  - .cronos/pipeline/gui-polish/scout-report-gui-polish.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - frontend/src/components/ui/
    - frontend/src/pages/
    - docs/ui-ux-review/
    - frontend/src/components/Lane.tsx, Modal.tsx, Detail.tsx, ViewPicker.tsx
  excluded:
    - backend/: not relevant to frontend polish scope
    - .claude/agents/: design system already established
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "GUI polish — touch targets, Toast, utility primitives (Phase 6). Sweep all interactive elements below 44px, extract Toast/Tabs/Dropdown/Tooltip/StatTile/ProgressBar into primitives, rewrite error/loading/empty copy, wire aria-live notifications."
metrics:
  tool_calls: 26
  files_read: 12
  memory_hits: 2
---

## Summary

The GUI Polish phase (Phase 6 of design system rollout) is a final-pass sweep covering touch
targets (44px minimum hit areas), Toast notifications with aria-live, and extraction of six
utility primitives (Tabs, Dropdown, Tooltip, StatTile, ProgressBar, SegmentedControl) from
scattered inline usage across Detail, SpaceTools, and Dashboard. Key gaps: Lane.tsx lane-header
buttons (p-1 ≈ 24px), Modal close (p-1 ≈ 28px), IconButton sm/md (h-7/h-8 ≈ 28–32px) all
below 44px. Design system tokens and specs exist (docs/ui-ux-review/02-design-system.md,
05-roadmap.md); error/loading/empty copy patterns are scattered across Detail/SpaceTools/Dashboard
with opportunities for user-voiced rewrites.

## Coverage

### Searched
- `frontend/src/components/ui/`: Button, IconButton, Modal, EmptyState, Icon (existing primitives)
- `frontend/src/components/`: Lane, Detail, ViewPicker (touch target & pattern inventory)
- `frontend/src/pages/`: DashboardPage, SpaceToolsPage (StatTile, Tabs, empty/loading copy)
- `docs/ui-ux-review/`: 02-design-system.md (Phases 0–6), 05-roadmap.md (component specs)

### Excluded
- backend/: not in scope (frontend-only polish)
- .claude/: agent configuration, not design system content

### Strategies
- memory_retrieval: 2 memory hits (gui-refactor board setup + prior gui-tokens-brand context)
- glob_structural: found 14 UI components in frontend/src/components/ui/
- grep_symbol: identified Tab/Dropdown/Toast/notification patterns via search
- read_targeted: read 12 files to inventory touch targets, inline patterns, and design specs

## Findings

### 1. Touch target gaps (44px minimum)

**Lane.tsx header buttons (lines 73–95):**
- Add button: `p-1` with Icon sm (14px) = ~24px hit area. Needs `min-w-[44px] min-h-[44px]` + padding adjustment.
- Hide lane button: `p-1` with custom SVG 12×12 = ~24px hit area. Same fix.
- Both use inline className with `p-1` padding; migration path: swap to `min-w-[44px] min-h-[44px]` + adjust padding (likely `p-2` or `p-2.5`).

**Modal.tsx close button (line 121–142):**
- Current: `p-1` with 16×16 SVG = ~28px hit area. Needs `min-w-[44px] min-h-[44px]` + padding correction.

**IconButton.tsx sizes (lines 15–18):**
- `sm`: `h-7 w-7` = 28px. Below 44px. Proposal: `h-11 w-11` (44px) or keep 28px in dense toolbar only with padding-wrap.
- `md`: `h-8 w-8` = 32px. Below 44px. Proposal: `h-11 w-11` (44px) or context-sensitive sizing.

**Button.tsx sizes (lines 12–15):**
- `sm`: `px-3 py-1` = ~28px tall (1 = 4px). Below 44px on touch. Proposal: ensure 44px minimum via `min-h-[44px]` + padding recalc.
- `md`: `px-4 py-2` = ~32px tall (2 = 8px). Below 44px on touch. Proposal: `min-h-[44px]` or taller padding.

### 2. Toast system (missing)

No current Toast or notification primitive. Patterns observed:
- Detail.tsx, SpaceTools use success/error messaging inline (no dedicated component).
- No `aria-live` regions found in codebase.
- Roadmap spec (05-roadmap.md, line 94): `<Toast />` + `useToast()` hook, `tone`, `message`, `action?`, auto-dismiss 3–5s, `aria-live="polite"`.

### 3. Tab switching patterns (Detail.tsx inline)

Detail.tsx (lines 827–1066):
- Hard-coded tab bar using raw button + inline className logic for active/inactive styling (lines 1038–1065).
- State: `useState<"details" | "stats" | "trace" | "files">` (line 827).
- Tab styling: absolute bottom underline accent bar (line 1046).
- Extraction opportunity: create `<Tabs items={[{value, label}]} value onChange />` component.

### 4. Dropdown/Menu patterns (ViewPicker.tsx as template)

ViewPicker.tsx (lines 49–159):
- Custom dropdown using `useState(false)` + manual ESC/mousedown close (lines 54–70).
- Trigger button: `h-8`, `px-2.5` (not 44px).
- Dropdown container: `w-52`, `z-30` (correct z-layer per design system), scrollable items (line 106).
- Extraction opportunity: extract to `<Dropdown trigger={...} items={[{label, onClick}]} />`.

SpaceToolsPage.tsx (lines 155–188) shows no dedicated dropdown, but ScopeBadge/ToolCard are consistent.

### 5. Existing primitives inventory

| Component | Status | Notes |
|-----------|--------|-------|
| Button | ⬆ Expand | needs `focus-visible`, `tertiary`/`link` variants, loading state, leading-icon |
| IconButton | ⬆ Expand | needs 44px hit-area guarantee, `focus-visible` ring |
| Modal | ⬆ Enforce | close button below 44px; scrim/escape/focus-trap in place |
| EmptyState | ✅ Ship | already good; add optional primary action slot |
| Icon | ✅ Live | lucide-react, 3 sizes (sm/md/lg), currentColor theming |
| ViewPicker | ↔ Extract | dropdown pattern; move to generic `<Dropdown>` |

### 6. Copy patterns for rewrite (user voice)

**Loading states (scattered):**
- Detail.tsx StatChip: "Loading stats…" (line 127).
- DashboardPage: no explicit loading copy observed (uses Skeleton).
- Opportunity: standardize to "Loading {noun}…" (e.g., "Loading task details…").

**Empty states (EmptyState component):**
- Lane.tsx: "No tasks" (used generically, line 101).
- EmptyState supports `title` + `description` + optional `children` (line 8–25).
- Roadmap calls for: "include a primary action" (05-roadmap.md, line 238).
- Current implementation: no action slot. Needs `children` slot for CTA button.

**Error copy (not surveyed in detail):**
- Likely inline error messages throughout; rewrite opportunities per brief ("cause + fix" framing).

### 7. Design system specs already written

**02-design-system.md:**
- §2.5: z-index ladder named (base/raised/dropdown/scrim/modal/toast/tooltip).
- §2.8: primitive catalog lists 9 new primitives needed for Phase 6: Badge, PageHeader, PageContainer, Skeleton, Toast/ToastProvider, Dropdown/Menu, Tooltip, Tabs, StatTile, ProgressBar.

**05-roadmap.md:**
- Phase 6 (lines 56–62): Touch-target sweep, Toast/aria-live, Tab/Dropdown/SegmentedControl/Tooltip/StatTile/ProgressBar extraction.
- Acceptance criteria (lines 102–112): all interactive ≥44px, no layout shift on load, focus rings everywhere, one modal behavior.

---

## Assumptions
- Touch target = minimum 44px × 44px per WCAG guidelines (confirmed in brief).
- Design system tokens and Phase 0–5 are already shipped (gui-tokens-brand goal completed; memory confirms).
- StatTile pattern exists inline in DashboardPage (lines 55–102); similarly ProgressBar inline in Detail MiniBar (lines 103–118).
- Tabs inline pattern in Detail is representative of SpaceTools (similar structure per scope brief).
- ESLint guardrail for raw palette classes (optional per brief) not prioritized in this phase.

## Open questions
- None.

## Next consumer brief

The analysis agent should:
1. Inventory all touch targets across Lane/Detail/Modal/Button/IconButton to confirm hit-area gaps vs 44px minimum.
2. Map all inline StatTile and ProgressBar instances (Dashboard, Stats, Detail) to identify extraction scope.
3. Verify Toast integration point (App.tsx or root provider); confirm aria-live semantics needed.
4. List all Tab implementations in Detail/SpaceTools/Stats; check if single `<Tabs>` contract covers all.
5. Identify all Dropdown/Menu trigger patterns (ViewPicker is template; check SpaceFilter, other boards).
6. Categorize error/loading/empty copy by page for rewrite prioritization (user voice).
7. Assess scope risk: does primitive extraction require breaking changes to existing Detail/Dashboard?

Gate decision: PROCEED if touch-target and extraction scopes are concrete and isolated; BLOCKED if cross-cutting refactoring required.
