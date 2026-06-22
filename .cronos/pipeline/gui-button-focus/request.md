GUI button enforcement — Button/IconButton migration (Phase 3)

Expands the existing Button and IconButton primitives with missing variants and
universal keyboard accessibility, then migrates ~160 ad-hoc styled `<button>` elements.
Currently 160/171 buttons bypass the primitives, making keyboard navigation broken for
most interactive elements.

**Concrete changes:**
- `Button.tsx`: add `tertiary` (outlined, low emphasis), `link` (text-only) variants;
  `focus-visible:ring-1 focus-visible:ring-accent focus:outline-none` ring on ALL variants;
  `loading` prop (spinner + disabled); `leadingIcon` slot; toolbar-chip / dropdown-trigger /
  segmented / list-row button archetypes; 44px hit area on `md` size.
- `IconButton.tsx`: `focus-visible` ring; guarantee ≥44px hit area for all sizes.
- Migrate inline buttons in waves:
  - Shell: Lane.tsx (lane ＋/×), SpaceFilterDropdown, ViewPicker, StickyToolbar
  - Board: Card.tsx, BoardPage.tsx
  - Pages: all remaining inline styled `<button>` elements
- Replace `role="button"` divs with real `<button>` elements.

**Exit criteria:** ≈160 inline button className strings replaced; focus rings on all
interactive elements; `npm run build` + `npm test` green.

Scope: frontend/src/components/ui/Button.tsx, frontend/src/components/ui/IconButton.tsx, frontend/src/components/Lane.tsx, frontend/src/components/SpaceFilterDropdown.tsx, frontend/src/components/ViewPicker.tsx, frontend/src/components/StickyToolbar.tsx, frontend/src/components/Card.tsx, frontend/src/pages/BoardPage.tsx, frontend/src/components/MarkdownEditorModal.tsx, frontend/src/components/TimeFrameSelector.tsx
