---
cc_version: "1.0"
agent: pipeline-scout
slug: gui-modal-loading
phase: scout
status: done
confidence: 0.92
inputs_used:
  - memory:GUI Refactor Board Setup
  - memory:gui-tokens-brand RESOLVED
  - memory:gui-layout-primitives review RESOLVED
  - memory:gui-badge-system review RESOLVED
  - memory:gui-button-focus review RESOLVED
  - memory:gui-icons review RESOLVED
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/ToolDetailPanel.tsx
  - frontend/src/components/ViewEditor.tsx
  - frontend/src/components/FileBrowser.tsx
  - frontend/src/pages/FeaturesPage.tsx
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/pages/HarnessListPage.tsx
  - frontend/src/index.css
  - frontend/tailwind.config.js
outputs_produced:
  - .cronos/pipeline/gui-modal-loading/scout-report-gui-modal-loading.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - frontend/src/components/ui/
    - frontend/src/components/ (Modal implementations + loaders)
    - frontend/src/pages/ (Loading states)
    - frontend/src/index.css (Animation tokens)
  excluded:
    - backend/: not relevant to GUI phase
    - tests/: scope is UI implementation, not test-only analysis
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "GUI modal contract + Skeleton loading states (Phase 5). Enforces a single Modal contract and ships a Skeleton component to eliminate layout shift on data load. Currently 10 `fixed inset-0` implementations use different scrim opacities (bg-black/50 to bg-black/80) and inconsistent Escape/close behavior. Plain text/spinner loaders cause visible layout shift when data arrives."
metrics:
  tool_calls: 15
  files_read: 10
  memory_hits: 6
---

## Summary

Modal implementations are currently fragmented across 5 components with 3 distinct scrim opacities (bg-black/50, bg-black/60, bg-black/70, bg-black/80, bg-canvas/60) and z-index values (z-40, z-50) that violate a consistent contract. Loading states use inline text ("Loading…") and CSS `animate-pulse` spinners causing layout shift. The existing Modal.tsx is minimal (22 lines) with no focus trap, dismissal guards, or entrance animation. Skeleton loaders exist as ad-hoc functions in Detail.tsx and FeatureDetail.tsx but no shared Skeleton.tsx component yet. DashboardPage shows "Loading statistics…" plaintext at line 699; HarnessListPage and FeaturesPage use `animate-spin` spinners. The task requires a unified Modal contract (bg-black/60 scrim, z-scrim=30, z-modal=40, scale-fade entrance at 280ms, Escape handler, focus-trap, dismissable guard) and a reusable Skeleton.tsx with text/block/card variants (180ms shimmer animation).

## Coverage

### Searched
- `frontend/src/components/ui/Modal.tsx` (existing, 22 lines)
- `frontend/src/components/MarkdownEditorModal.tsx` (452 lines, bg-black/80 scrim, no Escape handler in outer container, uses Icon X close button)
- `frontend/src/components/ToolDetailPanel.tsx` (210 lines, backdrop scrim bg-canvas/60 z-40, slide-over panel z-50, Escape handler at line 86–89, loading spinner lines 188–192)
- `frontend/src/components/ViewEditor.tsx` (modal child of Modal.tsx at line 300, delete dialog at line 519 with bg-black/60 scrim)
- `frontend/src/components/FileBrowser.tsx` (FileViewerModal lines 75–154, bg-black/80, Escape handler line 91–96, text loader line 144 "Loading…")
- `frontend/src/pages/FeaturesPage.tsx` (animate-spin spinner line 90–93, "Loading spaces…" text)
- `frontend/src/pages/DashboardPage.tsx` (plaintext "Loading dashboard…" line 601, "Loading statistics…" line 699, test reports loading "Loading…" line 816)
- `frontend/src/pages/HarnessListPage.tsx` (CreateHarnessModal z-50 bg-black/50 lines 104–160, delete confirm z-50 bg-black/50 lines 263–290, harnesses loading spinner + text lines 216–220)
- `frontend/src/index.css` (animation keyframes: streamEnter 180ms, pulseDot 1.8s, neonPulseDot 2s, neonFlicker)
- `frontend/tailwind.config.js` (no duration/animation extensions; uses Tailwind defaults)

### Excluded
- `backend/`: out-of-scope for this GUI phase
- non-scope components (App.tsx sidebar, Tree.tsx toast, etc.): not in brief scope
- existing test files: not required for scout phase
- Detail.tsx, FeatureDetail.tsx: discovered via grep, not consulted for detailed pattern analysis

### Strategies
- **memory_retrieval** (6 hits): Prior GUI SGs (tokens-brand, layout-primitives, badge-system, button-focus, icons) all RESOLVED; establishes context that modal-loading is 6th SG on feature/gui-refactor branch
- **glob_structural**: targeted `frontend/src/components` TSX and `frontend/src/pages` TSX to map modal + loading implementations
- **grep_symbol**: cross-repo grep for scrim opacities (`bg-black/50`, `bg-black/60`, `bg-black/70`, `bg-black/80`, `bg-canvas/60`) and z-strata (`z-40`, `z-50`)
- **read_targeted**: full-file reads of Modal.tsx, MarkdownEditorModal, ToolDetailPanel, ViewEditor, FileBrowser, FeaturesPage, DashboardPage, HarnessListPage; selective reads of CSS for animation tokens

## Findings

### Current Modal Fragmentation
1. **Modal.tsx (ui/Modal.tsx)** — Base component, 22 lines, `z-40` + `bg-black/70` + `backdrop-blur-sm`. Props: `onClose`, `className`, `children`. No focus trap, Escape handler, or entrance animation. Used by ViewEditor (line 300).
2. **MarkdownEditorModal** — Standalone 170-line modal, `z-50` + `bg-black/80`, Escape handler at line 49–64 (window keydown listener), X close button via Icon, stopPropagation at line 89, inner container border + rounded. **Inconsistencies:** z-index collision, scrim opacity, no scale-fade entrance.
3. **ToolDetailPanel** — Slide-over with split backdrop/panel. Backdrop: `z-40` + `bg-canvas/60`. Panel: `z-50`. Escape handler at line 85–89 (window keydown). Spinner loader lines 61–78 (SVG animate-spin). **Inconsistencies:** mixed z-index (40 backdrop, 50 panel), non-standard scrim, no unified contract.
4. **ViewEditor** — Uses Modal.tsx wrapper (line 300, inherits `z-40`), delete confirm dialog at line 519 has `z-50` + `bg-black/60` + Escape handler (line 283). **Inconsistency:** inner dialog overrides z-index.
5. **FileBrowser (FileViewerModal)** — 154-line modal, `z-50` + `bg-black/80`, Escape handler line 91–96, text loader "Loading…" line 144. **Inconsistencies:** z-index collision, scrim opacity, plaintext loader causes layout shift.

### Loading State Fragmentation
1. **Plaintext loaders:** DashboardPage "Loading dashboard…" (line 601), "Loading statistics…" (line 699), FileBrowser "Loading…" (line 144), FeaturesPage "Loading spaces…" (line 90), HarnessListPage "Loading…" (line 219).
2. **Spinner patterns:**
   - FeaturesPage: `<span>` with `h-4 w-4 animate-spin rounded-full border-2 border-hairline border-t-accent`
   - HarnessListPage: identical spinner
   - DashboardPage: re-used spinner (line 814–815)
   - ToolDetailPanel: custom SVG spinner (lines 61–78) with `animate-spin text-ink-faint`
3. **Ad-hoc skeleton components:**
   - `DetailSkeleton()` in Detail.tsx: `animate-pulse p-6 space-y-4` + `bg-surface-3` divs
   - `FeatureDetailSkeleton()` in FeatureDetail.tsx: similar pattern
   - No shared Skeleton.tsx component; no shimmer animation (only CSS `animate-pulse`)

### Animation Tokens
- **index.css** provides `@keyframes streamEnter` (180ms ease-out), `pulseDot` (1.8s infinite), `neonPulseDot` (2s infinite), `neonFlicker`
- No `motion-slow` (280ms) or `motion-base` (180ms) Tailwind utilities defined in tailwind.config.js
- Tailwind config (tailwind.config.js) has no `duration`, `animation`, or `keyframes` extensions; uses defaults (150ms, 300ms, etc.)

### Z-Index Strategy
- Current z-strata scattered: z-40 (App sidebar, Modal base, ToolDetailPanel backdrop), z-50 (modals, panels)
- No explicit z-scrim vs z-modal separation documented
- Brief specifies z-scrim=30, z-modal=40 (tighter hierarchy than current z-40/z-50 split)

### Dismiss Behavior Inconsistencies
- MarkdownEditorModal, ViewEditor delete dialog, FileBrowser: all have Escape handlers registered on `window.keydown`
- Modal.tsx has `onClick={onClose}` at root level, propagates to children (stopped with `onClick={(e) => e.stopPropagation()}`)
- No unified `dismissable` prop to guard against unsaved changes

### Missing Features
1. **Focus trap** — No FocusScope or manual focus management on open/close in any existing modal
2. **Entrance animation** — No scale or fade entrance (all components appear instantly)
3. **Unified escape/close contract** — Escape handlers are ad-hoc per-component window listeners
4. **Skeleton component library** — No Skeleton.tsx; loaders are inline (text, spinners, or `animate-pulse`)
5. **Shimmer animation** — Only CSS `animate-pulse`; brief requires shimmer effect

## Assumptions
- Motion token names (motion-slow, motion-base) are either Tailwind plugin extensions or custom CSS classes to be defined in Phase 5. Given index.css already has streamEnter (180ms) and pulseDot timings, assume motion-base=180ms, motion-slow=280ms, and brief means to use those semantics in new animations.
- Focus-trap behavior should trap focus within the modal while open and restore to trigger element on close; candidate library is @headlessui/react or a simple custom hook (no external library in current deps audit).
- Skeleton component is a UI primitive (like Button, Modal) and should live in `frontend/src/components/ui/Skeleton.tsx`.
- "Scale-fade entrance" likely means CSS transform scale-up + opacity fade-in, starting at scale(0.95) or similar.
- ToolDetailPanel slide-over (not a centered modal) may not need migration if brief scope is only the 4 ad-hoc modals; confirm with analyst.

## Open questions
- Does "dismissed=false for unsaved-changes guard" mean a prop on Modal, or on individual callers (MarkdownEditorModal already handles dirty state)?
- Should focus-trap be enforced by Modal.tsx itself, or left to callers? (MarkdownEditorModal has autoFocus on inputs, ViewEditor does not.)
- Is ToolDetailPanel slide-over (z-40 backdrop, z-50 panel) in scope for modal contract enforcement, or only the 4 centered modals (MarkdownEditorModal, FileBrowser, ViewEditor delete, HarnessListPage/CreateHarnessModal)?
- Should Skeleton.tsx support configurable animation duration (motion-base vs motion-slow), or hard-code both to 180ms?
- CreateHarnessModal in HarnessListPage (lines 86–160) uses inline modal (not Modal.tsx) with bg-black/50. Is this in scope? Brief lists "View-delete dialog" (ViewEditor) but HarnessListPage has two modals.

## Next consumer brief

The analysis agent should focus on:
1. Traceability: confirm that all 4 modal migrations (MarkdownEditorModal, FileBrowser, ViewEditor delete, ToolDetailPanel slide-over OR HarnessListPage create+delete) are feature-gated requirements or optional stretch goals.
2. Scope narrowing: z-50 instances in HarnessListPage (create), DeleteConfirmation dialogs suggest wider modal fragmentation than the 4 listed in brief; request clarification on full list vs. sample.
3. Skeleton variants: brief lists "text (single line shimmer), block (fixed height), card (card-shaped with header + rows)"; verify these are the only 3 required or if more variants expected (e.g., line-group, avatar, etc.).
4. Motion tokens: confirm that motion-slow(280ms) and motion-base(180ms) should be added to tailwind.config.js or defined as custom @keyframes in index.css.
5. Focus management: decide whether focus-trap is a Modal.tsx built-in (with optional `trapFocus={true}` prop) or left to caller via useEffect + refs.
6. Test expectations: what are the acceptance criteria for focus behavior (first focusable on open, return on close) and entrance animation (visual regression test or timing constraint).
7. Slide-over vs. modal: ToolDetailPanel is a persistent right-side panel (not centered, not dismissed by scrim click in default position). Confirm scope boundary.
