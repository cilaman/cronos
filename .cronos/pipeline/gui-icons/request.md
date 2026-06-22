GUI icon system — adopt lucide-react (Phase 4)

Adopts `lucide-react` as the single icon library and replaces all 77 structural
emoji and hand-rolled inline SVGs with Lucide icons. Currently icons render differently
per OS/font, can't be themed, and have no shared sizing. User-chosen space-avatar emoji
are explicitly preserved.

**Concrete changes:**
- `package.json`: add `lucide-react` dependency.
- `Icon.tsx`: wrapper component — `size?: 'sm'(14)/'md'(16,default)/'lg'(20)`,
  stroke 1.5 (sm/md) / 1.75 (lg), `currentColor`, accessible `aria-hidden="true"`.
- Replace structural emoji icons:
  - File categories in FileBrowserPage.tsx: 🤖→Bot, ⚡→Zap, ⌘→Command,
    📄→FileText, 💻→Terminal, 🖼→Image, 📑→FileCode, etc.
  - Chrome glyphs: ＋→Plus, ✕→X, ▾→ChevronDown, →→ArrowRight across Lane,
    SpaceFilter, ViewPicker, MarkdownEditorModal, TimeFrameSelector.
- Replace hand-rolled inline SVGs in ThemeToggle, App.tsx nav actions with Lucide.
- Keep emoji only for user-chosen space avatars (App.tsx space selector).

**Exit criteria:** `lucide-react` is the only icon source (plus space avatars); no
structural emoji in codebase; `npm run build` + `npm test` green.

Scope: frontend/package.json, frontend/src/components/ui/Icon.tsx, frontend/src/components/FileBrowserPage.tsx, frontend/src/components/Lane.tsx, frontend/src/components/SpaceFilterDropdown.tsx, frontend/src/components/ViewPicker.tsx, frontend/src/components/MarkdownEditorModal.tsx, frontend/src/components/TimeFrameSelector.tsx, frontend/src/components/ThemeToggle.tsx, frontend/src/App.tsx (nav icons)
