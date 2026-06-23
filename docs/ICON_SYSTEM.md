# Icon System

This document describes the Cronos icon system, covering integration, component API, migration status, testing, and performance considerations.

## Overview

Cronos adopts **`lucide-react`** as the single canonical source for all structural UI icons. This replaces a previous mixed approach using 77 Unicode emoji glyphs and scattered inline SVG definitions.

**Key properties of lucide-react for Cronos:**
- Tree-shakeable (only bundled icons are included)
- Stroke-based design with consistent hand-drawn appearance
- Theme-aware styling via `currentColor` CSS property
- Line weight (1.5px) matches the existing SVG aesthetic
- Extensive icon library (1000+ icons) covers all Cronos use cases

## Icon Component

### API

```tsx
import { Icon } from '@/components/ui/Icon'
import { ChevronDown, Plus, X } from 'lucide-react'

<Icon icon={ChevronDown} />
<Icon icon={Plus} size="lg" />
<Icon icon={X} className="text-red-600" />
```

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `icon` | `LucideIcon` | required | Lucide icon component (e.g., `ChevronDown`, `Plus`) |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | Predefined size and stroke width |
| `className` | `string` | — | Additional Tailwind classes; merged with defaults |

**Size variants:**

| Size | Px | Stroke | Use case |
|------|----|---------|----|
| `sm` | 14 | 1.5 | Inline text, dense toolbars, badges |
| `md` | 16 | 1.5 | Default; buttons, nav, list rows |
| `lg` | 20 | 1.75 | Page headers, empty states, large glyphs |

### Implementation details

The `Icon` component in `frontend/src/components/ui/Icon.tsx` **does not** use naive prop spreading. Instead, it constructs an explicit resolved-props object to avoid duplicate DOM attributes:

1. **Size → width + height** mapping (sm: 14, md: 16, lg: 20)
2. **Stroke width** derived from size (1.5 for sm/md, 1.75 for lg)
3. **Forced attributes:**
   - `aria-hidden="true"` (icons are decorative; text labels carry meaning)
   - `stroke="currentColor"` (respects text color and theme variables)
4. **className passthrough** — user-supplied classes merged with defaults

### Accessibility

- **Decorative icons:** Icons render with `aria-hidden="true"` because they are visual enhancements adjacent to text labels. The text carries the semantic meaning.
- **Icon-only affordances** (e.g., close button): Pair with `aria-label` on the surrounding button:
  ```tsx
  <IconButton aria-label="Close editor">
    <Icon icon={X} />
  </IconButton>
  ```
- **Contrast:** Icons inherit the parent text color, ensuring sufficient contrast when placed over backgrounds. Verify 4.5:1 contrast for any custom color overrides.

## Migration

### Files migrated (Phase 4 complete)

The gui-icons phase (77 total structural emoji/SVG replacements) is split across 10 scope files:

| File | Emoji/SVG replaced | Migration | Notes |
|------|-------|---------|-------|
| `frontend/src/components/ui/Icon.tsx` | — | Created | Wrapper component + 11 unit tests |
| `frontend/src/components/FileBrowser.tsx` | `CATEGORY_ICON` map (11 emoji) | Complete | File categories: 🤖→Bot, ⚡→Zap, ⌘→Command, 📄→FileText, 💻→Terminal, 🖼→Image, etc. |
| `frontend/src/components/Lane.tsx` | `＋` (fullwidth plus) | Complete | New-task button |
| `frontend/src/components/SpaceFilterDropdown.tsx` | `▾` (triangle chevron) | Complete | Dropdown trigger glyph |
| `frontend/src/components/ViewPicker.tsx` | `▾` (triangle chevron) | Complete | Dropdown trigger glyph |
| `frontend/src/components/MarkdownEditorModal.tsx` | `✕` (cross glyph) | Complete | Close button |
| `frontend/src/components/TimeFrameSelector.tsx` | (no changes needed) | Skipped | Uses only `→` text range separator (out of scope) |
| `frontend/src/components/ThemeToggle.tsx` | 3 inline SVGs | Complete | Sun/Moon/Zap glyphs for light/dark/neon theme picker |
| `frontend/src/App.tsx` | 1 inline hamburger SVG | Complete | Mobile menu icon; space-avatar emoji preserved per R7 |
| `frontend/src/__tests__/icons-audit.test.ts` | — | Created | Scope-bounded regression test (19 tests) |

### Partially migrated / deferred

The following files are explicitly deferred to a future phase (out of Phase 4 scope):

| File | Remaining emoji/SVG | Status | Reason |
|------|--------|--------|--------|
| `frontend/src/components/FileBrowser.tsx` | `✕` (line 126), `▸` (line 309) | Deferred | Modal close and upload-toggle glyphs are UI chrome, not file-category icons |
| `frontend/src/components/Lane.tsx` | `<svg>` (line ~90) | Deferred | Hide-lane close button SVG; independent scope from `＋` |
| `frontend/src/components/ViewPicker.tsx` | StarIcon, CheckIcon SVGs (lines ~15–46) | Deferred | Decorative icons; not structural chrome |
| `frontend/src/components/PluginsPanel.tsx` | `KIND_ICON` map (3 emoji) | Deferred | Component is out of scope; test only |
| `frontend/src/components/Sidebar.tsx` | 2 inline SVGs | Deferred | Out of Phase 4 scope |
| `frontend/src/types.ts::SPACE_AVATAR_CHOICES` | Emoji list | Intentional | User-content avatars (R7) — must preserve |

### Lucide icon names used

```typescript
// File categories
Archive, Binary, BookOpen, Bot, Command, FileCode, FileText, Folder, Image, Terminal, Zap

// Chrome glyphs
ChevronDown, ChevronLeft, ChevronRight, Plus, X

// Navigation & theme
Menu, Sun, Moon
```

All icons are imported from `lucide-react` (not `@lucide/react`). Names are PascalCase.

## Testing

### Unit tests: `Icon.tsx`

Located at `frontend/src/components/ui/__tests__/Icon.test.tsx` (11 tests):

- Size variants (sm, md, lg): check px dimensions and stroke width
- Default size: verify md is applied when size prop omitted
- Accessibility: aria-hidden="true" and stroke="currentColor"
- className passthrough: user classes merge correctly
- No duplicate attributes: exactly one width, one height, one stroke-width per size

### Integration tests: per-component

Each scope file has accompanying test suites that verify:
- Lucide icons render correctly (`<Icon icon={...} />`)
- Icon-only buttons have proper aria-labels
- Emoji migrations do not break existing component behavior
- Snapshot tests updated (if applicable)

Test files:
- `FileBrowser.test.tsx` (6 tests)
- `Lane.test.tsx` (29 tests)
- `SpaceFilterDropdown.buttons.test.tsx` (9 tests)
- `ViewPicker.buttons.test.tsx` (9 tests)
- `MarkdownEditorModal.buttons.test.tsx` (10 tests)
- `ThemeToggle.test.tsx` (9 tests)
- `App.test.tsx` (6 tests)
- `PluginsPanel.test.tsx` (23 tests, updated line 229 assertion)

### Regression audit: `icons-audit.test.ts`

Located at `frontend/src/__tests__/icons-audit.test.ts` (19 tests):

This is a scope-bounded guardrail that prevents regressions in Phase 4 scope files:

- **Emoji audit**: For each of the 10 production scope files, asserts zero matches of the closed emoji set:
  ```
  {🤖,⚡,⌘,📖,🖼,📄,💻,📑,🗜,⬛,＋,✕,▾,▸}
  ```
  (with documented exceptions for FileBrowser.tsx and deferred files)

- **SVG audit**: For fully migrated files (ThemeToggle, App, SpaceFilterDropdown, MarkdownEditorModal, TimeFrameSelector), asserts zero inline `<svg` tags in source text.

- **Scoping**: The test enumerates only the 11 in-scope files (10 production + Icon.tsx). Out-of-scope siblings (Sidebar, ToolDetailPanel, PluginsPanel, etc.) may still legitimately contain old emoji/SVG and are not checked.

Run via:
```bash
cd frontend
npm test -- src/__tests__/icons-audit.test.ts
```

## Performance

### Bundle size

Lucide-react is tree-shakeable. Only imported icons are bundled. Typical icon usage:

- Per icon imported: ~200 bytes (gzipped)
- Icon.tsx wrapper: ~1 KB
- Total overhead for Phase 4 migration: ~3–4 KB gzipped

This is negligible compared to the removed inline SVG duplication and emoji glyph overhead.

### Runtime

- Icon component renders a single `<svg>` element with resolved props
- No runtime compilation or transformation
- Inherits parent text color via CSS (no JavaScript color logic)
- Compatible with theme switching via CSS variables

## Design decisions

### Why lucide-react?

1. **Consistency**: One icon set (1000+ icons) vs. scattered emoji and 77 hand-rolled SVG snippets
2. **Theming**: `currentColor` stroke respects parent text color and theme variables automatically
3. **Aesthetics**: Stroke weight and hand-drawn appearance match Cronos's existing SVG aesthetic
4. **Accessibility**: Proper SVG semantics; simple to pair with aria-labels for icon-only buttons
5. **Tree-shaking**: Only imported icons are bundled; no unused icon penalty
6. **Maintenance**: Upstream icon updates; no custom SVG maintenance burden

### Why preserve space-avatar emoji?

Space avatars (`SPACE_AVATAR_CHOICES` in `frontend/src/types.ts`) are user-chosen identity markers, not structural UI icons. Emoji are appropriate here because:
- Users expect emoji picker UX
- Emoji render natively without additional dependencies
- Treating user content differently from UI chrome maintains clear separation of concerns

### Why explicit props in Icon.tsx?

The Icon component does not use naive prop spreading (`<Lucide {...props} />`). Instead, it constructs an explicit resolved-props object. Reasons:

1. **Attribute safety**: Lucide's default props (`width: 24, height: 24`, `stroke-width: 2`) combined with user props could produce duplicate attributes if not carefully managed.
2. **Size semantics**: By translating `size: 'sm' | 'md' | 'lg'` to pixel values and stroke width, Icon becomes a design-system primitive rather than a pass-through.
3. **Consistency**: The explicit approach guarantees that all icons render with the same structure (single width, single height, single stroke-width) — a precondition for testing and theming.

## Related documentation

- **[02-design-system.md §2.7](../ui-ux-review/02-design-system.md)** — Icon system in the broader design system context; size tokens, accessibility, and brand glyphs
- **[frontend/src/components/ui/Icon.tsx](../../../frontend/src/components/ui/Icon.tsx)** — Implementation
- **[frontend/src/__tests__/icons-audit.test.ts](../../../frontend/src/__tests__/icons-audit.test.ts)** — Regression audit test

## Troubleshooting

### `cannot find module 'lucide-react'`

Run `npm install` in the frontend directory:
```bash
cd frontend && npm install
```

### Icon renders but has wrong stroke width

Check the `size` prop. Lucide icons have a default size of 24 and stroke width of 2; the Icon wrapper overrides both. If you pass `size="sm"`, the icon renders at 14px with stroke 1.5.

### Custom color doesn't apply

Icons inherit color via `currentColor`. Ensure the parent element has a text-color class:
```tsx
<div className="text-red-600">
  <Icon icon={AlertCircle} />
</div>
```

For Tailwind utility application, use the parent's text color:
```tsx
<Button className="text-blue-500">
  <Icon icon={Settings} />
</Button>
```

### Missing aria-label on icon-only button

When an icon is the only content of a button, always add an aria-label to the button (not the icon):
```tsx
// ✓ Correct
<IconButton aria-label="Settings">
  <Icon icon={Settings} />
</IconButton>

// ✗ Wrong
<Button aria-label="Settings">
  <Icon icon={Settings} aria-label="Settings" />
</Button>
```

## Future work

1. **Deferred icon migrations** (FileBrowser modal chrome, Lane close, ViewPicker decorative icons, PluginsPanel KIND_ICON, Sidebar SVGs)
2. **Brand mark and runtime-state marks** — separate identity assets managed via `brand/` directory
3. **Tooltip component** — for icon-only affordances without wrapping in buttons
4. **Icon-only button component** — standardized size and hit-area guarantees
