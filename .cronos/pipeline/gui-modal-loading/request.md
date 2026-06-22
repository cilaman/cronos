GUI modal contract + Skeleton loading states (Phase 5)

Enforces a single Modal contract and ships a Skeleton component to eliminate layout
shift on data load. Currently 10 `fixed inset-0` implementations use different scrim
opacities (bg-black/50 to bg-black/80) and inconsistent Escape/close behavior.
Plain text/spinner loaders cause visible layout shift when data arrives.

**Concrete changes:**
- `Modal.tsx`: enforce the single contract — `bg-black/60` + `backdrop-blur-sm` scrim
  (z-scrim=30), panel z-modal=40, scale-fade entrance at motion-slow(280ms),
  Escape key handler, focus-trap (first focusable element on open, return on close),
  `dismissable=false` for unsaved-changes guard, single SVG X close button.
- Migrate 4 ad-hoc modal implementations to use Modal.tsx:
  - MarkdownEditorModal (currently bg-black/80, ✕ emoji)
  - FileViewer (currently bg-black/80, no Escape)
  - View-delete dialog (currently bg-black/60)
  - ToolDetailPanel (currently bg-canvas/60)
- `Skeleton.tsx`: three variants — `text` (single line shimmer), `block` (fixed height),
  `card` (card-shaped with header + rows). Shimmer at motion-base(180ms).
- Replace spinner/text loaders: FeaturesPage spinner, Dashboard "Loading statistics…"
  text, HarnessList spinner+text — each replaced with reserved-space Skeleton.

**Exit criteria:** one scrim/escape/focus behavior across all modals; no layout shift
on data load; `npm run build` + `npm test` green.

Scope: frontend/src/components/ui/Modal.tsx, frontend/src/components/ui/Skeleton.tsx, frontend/src/components/MarkdownEditorModal.tsx, frontend/src/components/FileViewer.tsx, frontend/src/pages/FeaturesPage.tsx, frontend/src/pages/Dashboard.tsx, frontend/src/pages/HarnessListPage.tsx, frontend/src/components/ToolDetailPanel.tsx
