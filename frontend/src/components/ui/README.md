# UI Components

Reusable component library for the Cronos frontend. All components follow the design system tokens defined in `docs/ui-ux-review/02-design-system.md`.

## Layout primitives

### PageHeader

Standard page title / breadcrumb / actions bar for all pages.

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `breadcrumbs` | `BreadcrumbItem[]` | undefined | Optional navigation breadcrumbs rendered as `<nav><ol>` with semantic `<li><Link>` items |
| `title` | `string` | required | Page title; rendered as `<h1 className="text-title">` per design §2.2 |
| `subtitle` | `ReactNode` | undefined | Optional description or contextual control below the h1 (e.g. filters, date pickers) |
| `actions` | `ReactNode[]` | undefined | Optional action buttons/controls. Up to 3 render inline in flex row; 4+ uses native `<details>/<summary>` "More" disclosure for overflow items (keyboard-accessible, ESC-closable) |
| `sticky` | `boolean` | false | When true, applies `sticky top-0 z-30` with backdrop-blur. **Warning:** z-30 > StickyToolbar's z-20; do NOT set sticky=true on pages retaining StickyToolbar (z-index collision risk). |
| `className` | `string` | undefined | Additional CSS classes (merged via `cn()`) |

**Example:**

```tsx
import { PageHeader, PageContainer } from "./ui";

export function MyPage() {
  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Settings" }]}
        title="Space Settings"
        actions={[<Button>Save</Button>]}
      />
      <PageContainer>
        {/* page body */}
      </PageContainer>
    </>
  );
}
```

**Semantic markup:**

- Root element is `<header>`
- Breadcrumbs wrapped in `<nav>` with `<ol>` list semantics
- Title is `<h1>` with `text-title` class (mono 22px 600 weight -0.01em tracking, no uppercase)
- No ad-hoc h1 classes (e.g., `font-display text-sm uppercase tracking-wider`) — use PageHeader or apply `text-title` only

**Notes:**

- `text-title` is a CSS utility in `frontend/src/index.css` `@layer utilities` — not a Tailwind JIT class. Always available at runtime.
- Overflow actions (4+) use a native `<details>` element for accessibility (keyboard-navigable, ESC-closable on blur).
- No page currently uses overflow actions; the feature is implemented for spec compliance.

### PageContainer

Standard page body wrapper with responsive padding and content-width options.

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `width` | `'content' \| 'reading'` | `'content'` | Layout width: `'content'` = max-w-[1280px] (dashboard pages); `'reading'` = max-w-[768px] (settings, docs-heavy pages) |
| `className` | `string` | undefined | Additional CSS classes (merged via `cn()`) |
| `children` | `ReactNode` | required | Page body content |

**Spacing:**

- Mobile: `p-6` (24px)
- Desktop (`lg`): `p-8` (32px)
- Follows the 4/8 rhythm per design-system §2.3

**Example:**

```tsx
<PageContainer width="content">
  <div>{/* dashboard cards, tables */}</div>
</PageContainer>
```

**Exemptions:**

- **HarnessEditor, FileBrowserPage**: These pages use full-canvas / split-pane layouts. They do NOT wrap their body in PageContainer. Only the sidebar/top-bar h1 applies the `text-title` class.

### Badge

Reusable styled badge component with semantic color tones for status, priority, task type, feature state, agent mode, and harness run status.

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `tone` | `Tone` | required | Semantic tone string determining badge color classes. See Tone list below. |
| `children` | `string \| ReactNode` | required | Badge label text or elements (e.g. "Active", "P1", "Goal") |
| `className` | `string` | undefined | Additional CSS classes (merged via `cn()`) |

**Tone values (12 semantic tones):**

| Tone | Use case | Colors |
|------|----------|--------|
| `'running'` | Task status ACTIVE; harness nodes in progress | bg-running/12, text-running, ring-running/30 |
| `'success'` | Task status DONE; successful run completion | bg-success/12, text-success, ring-success/30 |
| `'warning'` | Warning/info state (not an error) | bg-warning/12, text-warning, ring-warning/30 |
| `'danger'` | Task status FAILED; harness node error | bg-danger/12, text-danger, ring-danger/30 |
| `'info'` | Neutral informational state | bg-info/12, text-info, ring-info/30 |
| `'neutral'` | Default fallback; unrecognized or generic | bg-neutral/12, text-neutral, ring-neutral/30 |
| `'goal'` | Task type = goal | bg-goal/12, text-goal, ring-goal/30 |
| `'feature'` | Task type = feature | bg-feature/12, text-feature, ring-feature/30 |
| `'fix'` | Task type = fix | bg-fix/12, text-fix, ring-fix/30 |
| `'issue'` | Task type = issue | bg-issue/12, text-issue, ring-issue/30 |
| `'plan'` | Agent mode = plan | bg-plan/12, text-plan, ring-plan/30 |
| `'ask'` | Agent mode = ask | bg-ask/12, text-ask, ring-ask/30 |

**Helper functions (in `src/utils/badgeTone.ts`):**

To avoid hardcoding tone strings, use typed helper functions that map domain enums to tones:

```tsx
import { Badge } from "./ui/Badge";
import {
  getToneRunStatus,
  getToneTaskState,
  getToneFeatureState,
  getTonePriority,
  getToneType,
  getToneMode
} from "src/utils/badgeTone";

// Task state badge
<Badge tone={getToneTaskState(task.state)}>
  {task.state}
</Badge>

// Priority badge
<Badge tone={getTonePriority(priority)}>
  P{priority + 1}
</Badge>

// Feature state badge
<Badge tone={getToneFeatureState(feature.state)}>
  {feature.state}
</Badge>

// Harness run status
<Badge tone={getToneRunStatus(run.status)}>
  {run.status}
</Badge>

// Agent mode
<Badge tone={getToneMode(agent.mode)}>
  {agent.mode}
</Badge>

// Task/feature type
<Badge tone={getToneType(item.type)}>
  {item.type}
</Badge>
```

All helpers guard against unrecognized inputs by returning `'neutral'` as a fallback.

**Example:**

```tsx
import { Badge } from "./Badge";

export function TaskCard({ task }) {
  return (
    <div className="flex items-center gap-3">
      <h3>{task.title}</h3>
      <Badge tone={task.state === "done" ? "success" : "running"}>
        {task.state}
      </Badge>
    </div>
  );
}
```

**Notes:**

- Tone classes use Tailwind color variables (e.g., `bg-running/12` expands to `rgb(var(--color-running) / 0.12)`).
- The TONE_CLASSES record in `Badge.tsx` is frozen and explicitly lists all 12 tone strings; this allows Tailwind's JIT compiler to statically scan all required classes at build time.
- Do NOT use raw palette classes (e.g., `bg-emerald-500`, `text-rose-400`) in badge-adjacent code — use Badge + tone helpers instead.
- All badge migrations are guarded by the `frontend/tests/no-raw-palette-classes.test.ts` audit, which fails CI if raw palette classes are found in badge-touched files.

## Button components

### Button

Styled button component with multiple variants, sizes, loading states, and contextual archetypes. All variants feature a universal keyboard focus ring: `focus:outline-none focus-visible:ring-1 focus-visible:ring-accent`.

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `variant` | `'primary' \| 'secondary' \| 'ghost' \| 'danger' \| 'tertiary' \| 'link'` | `'primary'` | Visual style. Primary (accent bg), secondary (muted), ghost (transparent), danger (red), tertiary (minimal border), or link (text + underline). All except link are bordered. |
| `size` | `'sm' \| 'md'` | `'md'` | Button size. `sm` = 12px text + 3px/1px padding; `md` = 14px text + 4px/2px padding + minimum 44px height (WCAG touch target) |
| `loading` | `boolean` | false | When true, disables the button and renders a spinner element (animated `border-t-transparent` circle). Replaces text content during load. |
| `disabled` | `boolean` | false | Disables the button and applies disabled state styling |
| `leadingIcon` | `ReactNode` | undefined | Optional icon node rendered before the button text. Hidden when `loading=true`. |
| `archetype` | `'toolbar-chip' \| 'dropdown-trigger' \| 'segmented' \| 'list-row'` | undefined | Optional semantic shape archetype. Overrides default border/padding for specific UI patterns. See Archetype guide below. |
| `className` | `string` | undefined | Additional CSS classes (merged via `cn()`) |
| ...rest | `React.ButtonHTMLAttributes` | — | All standard HTML button attributes (onClick, type, etc.) |

**Variants:**

| Variant | Usage | Appearance |
|---------|-------|-----------|
| `primary` | Default call-to-action; save, create, submit | Accent background, white text, bright hover shadow |
| `secondary` | Secondary action; apply filter, cancel | Muted background, ink text, subtle hover |
| `ghost` | Tertiary action; toggle, optional; low emphasis | Transparent, muted text, light hover background |
| `danger` | Destructive action; delete, remove | Red background, ink text |
| `tertiary` | Minimal style; tertiary UI; pills, chips | Thin border, muted text, no fill |
| `link` | Text link style; navigation, help | No border, accent text, underline on hover |

**Archetypes:**

When `archetype` is set, the button shape is modified for a specific UI context. This allows consistency across patterns:

- `'toolbar-chip'` — Rounded-full pill style for toolbar toggles (e.g. "Mode: Plan"). Border-hairline, small padding.
- `'dropdown-trigger'` — Right-aligned with gap for dropdown indicator (e.g. chevron). Justifies between label and icon.
- `'segmented'` — Zero border-radius except first/last in a group; removes right border except last item. Use in toggles (e.g. "Table | List | Grid").
- `'list-row'` — Full-width left-aligned with bottom border-hairline (except last). For dropdown menus and lists.

**Focus behavior:**

Every variant unconditionally includes the universal focus ring:

```
focus:outline-none focus-visible:ring-1 focus-visible:ring-accent
```

This ensures keyboard navigation is always visible and consistent across all button styles.

**Loading example:**

```tsx
const [loading, setLoading] = useState(false);

<Button
  loading={loading}
  onClick={async () => {
    setLoading(true);
    try {
      await saveTask();
    } finally {
      setLoading(false);
    }
  }}
>
  Save task
</Button>
```

**Archetype example (segmented mode toggle):**

```tsx
<div className="flex">
  <Button
    archetype="segmented"
    variant={mode === "plan" ? "primary" : "secondary"}
    onClick={() => setMode("plan")}
  >
    Plan
  </Button>
  <Button
    archetype="segmented"
    variant={mode === "execute" ? "primary" : "secondary"}
    onClick={() => setMode("execute")}
  >
    Execute
  </Button>
</div>
```

**Notes:**

- Always prefer `archetype` over raw className strings for consistent styling.
- The focus ring is applied unconditionally; callers should never add custom focus styling.
- Loading spinner is a built-in `<span>` element with `data-testid="button-spinner"` for testing.

### IconButton

Icon-only button for toolbar actions, menu triggers, and closers. All variants feature a universal keyboard focus ring: `focus:outline-none focus-visible:ring-1 focus-visible:ring-accent`.

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `aria-label` | `string` | required | Accessible label describing the button action (e.g., "Close dialog", "Add task", "Delete") |
| `variant` | `'default' \| 'accent' \| 'accent-soft' \| 'danger' \| 'danger-hover'` | `'default'` | Visual style. Default (muted), accent (bright), accent-soft (light), danger (red), or danger-hover (reveal on hover). |
| `size` | `'sm' \| 'md' \| 'compact'` | `'md'` | Icon button size and hit area. `sm` and `md` both default to 44px (WCAG touch target); `compact` = 32px (opt-in for dense toolbars). |
| `loading` | `boolean` | false | When true, disables the button and renders ellipsis ("…") |
| `disabled` | `boolean` | false | Disables the button and applies disabled state styling |
| `className` | `string` | undefined | Additional CSS classes (merged via `cn()`) |
| ...rest | `React.ButtonHTMLAttributes` | — | All standard HTML button attributes (onClick, etc.) |

**Variants:**

| Variant | Usage | Appearance |
|---------|-------|-----------|
| `default` | Standard toolbar icon; filters, actions | Muted border/background, subtle hover |
| `accent` | Call-to-action icon; primary action | Accent background, bright shadow on hover |
| `accent-soft` | Secondary icon action; soft accent | Light accent background, brighter on hover |
| `danger` | Destructive icon; delete, remove | Red background, ink text |
| `danger-hover` | Hover-to-reveal danger; low-emphasis delete | Muted by default, reveals red on hover |

**Size guide:**

| Size | Dimensions | Use case |
|------|-----------|----------|
| `sm` | h-11 w-11 (44px) | Default size; meets WCAG 2.5.5 minimum touch target for small icons |
| `md` | h-11 w-11 (44px) | Same as `sm`; both default to 44px for accessibility |
| `compact` | h-8 w-8 (32px) | Opt-in for dense toolbars where 44px overflows. Explicitly waives WCAG minimum and requires UX justification. |

The 44px default ensures all icon buttons are easily clickable on touch devices. The `compact` size is available but should be used sparingly and documented when space is truly constrained.

**Focus behavior:**

Every variant unconditionally includes the universal focus ring:

```
focus:outline-none focus-visible:ring-1 focus-visible:ring-accent
```

**Example (close button):**

```tsx
<IconButton
  aria-label="Close dialog"
  variant="default"
  onClick={onClose}
>
  <CloseIcon />
</IconButton>
```

**Example (danger delete with hover reveal):**

```tsx
<IconButton
  aria-label="Delete task"
  variant="danger-hover"
  onClick={handleDelete}
>
  <TrashIcon />
</IconButton>
```

**Example (dense toolbar with compact size):**

```tsx
{/* Justified: inline toolbar in dense modal header */}
<div className="flex gap-1">
  <IconButton size="compact" aria-label="Undo">
    <UndoIcon />
  </IconButton>
  <IconButton size="compact" aria-label="Redo">
    <RedoIcon />
  </IconButton>
</div>
```

**Notes:**

- `aria-label` is required for all IconButton instances (accessibility requirement).
- The focus ring is applied unconditionally; callers should never add custom focus styling.
- Prefer `variant="danger-hover"` over `variant="danger"` for low-emphasis destructive actions (e.g., edit-mode delete buttons).
- When using `compact` size, document the UX rationale in an inline comment.

## Other components

| Component | Purpose |
|-----------|---------|
| `FormField.tsx` | Form field wrapper with label + error message |
| `FormInput.tsx` | Input element with error state |
| `Modal.tsx` | Modal dialog wrapper |
| `EmptyState.tsx` | Placeholder for empty collections |
| `StickyToolbar.tsx` | Sticky top toolbar (z-20); for secondary controls (filters, tabs) — not for page titles |
| `SpaceTag.tsx` | Space identifier badge |

## Design system alignment

All components use tokens from `docs/ui-ux-review/02-design-system.md`:

- **Typography**: `text-title` (page h1), `text-eyebrow` (section labels), `text-cardtitle` (card headings), `text-body` (prose)
- **Color**: Status tokens (`--color-running`, `--color-success`, `--color-warning`, `--color-danger`, `--color-info`, `--color-neutral`) and categorical tokens (`--cat-goal`, `--cat-feature`, `--cat-fix`, `--cat-issue`, `--cat-plan`, `--cat-ask`)
- **Spacing**: 4/8 rhythm (p-4, p-6, p-8, gap-4, gap-6, gap-8)
- **Focus ring**: Consistent `focus:outline-none focus-visible:ring-1 focus-visible:ring-accent` on all interactive components

## Migration checklist (gui-layout-primitives goal)

The following pages were migrated to PageHeader + PageContainer in this release:

| Page | Width | Sticky | Notes |
|------|-------|--------|-------|
| DashboardPage | content | false | 3 actions: New task, New space, Import space |
| StatsPage | content | false | Space filter + TimeFrameSelector as subtitle |
| HarnessRunsPage | content | false | Run now action button |
| TestReportsPage | content | false | Space filter as action |
| SpaceCreatePage | reading | false | Breadcrumb: Dashboard/; narrower form (768px) |
| HarnessListPage | content | false | Harness list, create modal |
| SpaceSettingsPage | reading | false | Back to board action; narrower form (768px) |
| SpaceToolsPage | content | false | Space selector moved to actions[] |
| FeaturesPage (scoped) | content | false | Removed StickyToolbar; moved filter to actions |
| FeaturesPage (global) | content | false | Removed StickyToolbar; moved filter to actions |
| ArchivedPage | content | false | Removed StickyToolbar; moved filter to actions |
| MemoryPage | reading | false | Unconfirmed badge as actions prop |
| FileBrowserPage | (no container) | false | h1 class swap only; split-pane layout exemption |
| HarnessEditor | (no container) | false | h1 class swap only; full-canvas layout exemption |

Two pages retain layout exemptions and do NOT host PageContainer:
- **HarnessEditor**: full-screen canvas layout (design risk R3, analyst R9)
- **FileBrowserPage**: split-pane master-detail layout (structural precedent with HarnessEditor)

Both apply the `text-title` class directly to their h1 element.

## Button migration (gui-button-focus goal)

Phase 3 of the GUI refactor migrated approximately 160 inline-styled buttons across 8 components to the new Button/IconButton primitives with focus rings and semantic archetypes:

| Component | Changes | Migration notes |
|-----------|---------|-----------------|
| Lane.tsx | Add-task icon → IconButton; hide-lane icon → IconButton | Both use default variant, 44px hit area |
| SpaceFilterDropdown.tsx | Trigger → Button archetype="dropdown-trigger"; items → Button archetype="list-row" | Dropdown menu pattern |
| ViewPicker.tsx | Trigger → Button archetype="dropdown-trigger"; manage-views → Button archetype="list-row" | Dropdown menu pattern |
| Card.tsx | Default-density body → native `<button type="button">` with focus ring and dnd-kit drag preserved | Drag-to-reorder still functional; nested interactive children use `span[role="button"]` to avoid nested-button HTML violation |
| MarkdownEditorModal.tsx | Mode toggles → Button archetype="segmented"; save button → Button variant="secondary"; close icon → IconButton | Segmented toggle pattern |
| TimeFrameSelector.tsx | Preset tabs → Button archetype="segmented" | Segmented toggle pattern |

**Design trade-off (nested interactive children in Card.tsx):**

The Card.tsx default-density body was converted from `<div role="button">` to a native `<button type="button">` to improve keyboard accessibility. However, nested interactive descendants (parent-breadcrumb chip, realizes-chip, proposed_pr link, proposed_issue link) cannot also be native `<button>` elements, as HTML does not allow nested buttons. These nested elements use `<span role="button" tabIndex={0}>` with `onKeyDown` handlers instead, which preserves keyboard activation while avoiding the invalid nested-interactive HTML structure. This is a deliberate design trade-off documented in the implementation: the card body itself is the primary clickable surface, with meta-action chips rendered as lower-precedence keyboard targets inside it.

## Keyboard accessibility

All Button and IconButton variants include a universal keyboard focus ring for discoverability:

- **Focus indicator**: `focus:outline-none focus-visible:ring-1 focus-visible:ring-accent`
- **Ring color**: `accent` (bright, stands out against all backgrounds)
- **Ring width**: 1px (minimal visual noise)
- **Focus-visible pseudo-selector**: Only shows on keyboard navigation; not on mouse click (follows platform conventions)

The focus ring is applied unconditionally — callers should never override or disable it.
