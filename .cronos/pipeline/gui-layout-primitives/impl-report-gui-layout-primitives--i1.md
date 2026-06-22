---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-layout-primitives--i1
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:gui-refactor-board-setup
  - memory:gui-tokens-brand-review-attempt1
  - .cronos/pipeline/gui-layout-primitives/design-report-gui-layout-primitives.md
  - frontend/src/index.css
  - frontend/src/components/ui/EmptyState.tsx
  - frontend/src/components/ui/StickyToolbar.tsx
  - frontend/src/components/ui/__tests__/ui.test.tsx
iteration_id: I1
files_changed:
  - frontend/src/index.css
  - frontend/src/components/ui/PageContainer.tsx
  - frontend/src/components/ui/PageHeader.tsx
  - frontend/src/components/ui/__tests__/PageContainer.test.tsx
  - frontend/src/components/ui/__tests__/PageHeader.test.tsx
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/gui-layout-primitives/impl-report-gui-layout-primitives--i1.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 22
  files_read: 8
  memory_hits: 2
  diff_lines_added: 416
  diff_lines_removed: 0
---

## Summary

I1 implements the three foundation deliverables for gui-layout-primitives: the `text-title` CSS utility added to `index.css` `@layer utilities`, the `PageContainer` component, and the `PageHeader` component plus their 23-test unit suites. All 23 tests pass (`vitest run` exit 0). The intentional visual restyle — `text-title` uses font-mono/22px/28px/600/-0.01em and explicitly removes uppercase and positive tracking — is a breaking divergence from all existing `tracking-[0.14em] uppercase` h1 usages; this is by design and documented as Risk #1 in the design report. Consumers in I2/I3/I4 must rely on `text-title` only and must not add back any `tracking-[…]` or `uppercase` class to page h1s.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/index.css | modified | +25 / 0 | Add `.text-title` utility in `@layer utilities` per design-system.md §2.2 |
| frontend/src/components/ui/PageContainer.tsx | created | +32 / 0 | New primitive: `width='content'` (1280px) / `'reading'` (768px) body wrapper |
| frontend/src/components/ui/PageHeader.tsx | created | +112 / 0 | New primitive: breadcrumbs, h1.text-title, subtitle, actions (3-inline / 4+ overflow via details/summary), optional sticky z-30 |
| frontend/src/components/ui/__tests__/PageContainer.test.tsx | created | +67 / 0 | 6 unit tests: width variants, padding, className merge, children render |
| frontend/src/components/ui/__tests__/PageHeader.test.tsx | created | +180 / 0 | 17 unit tests: h1/text-title, no-ad-hoc-classes, breadcrumbs, actions overflow, sticky, className, semantic markup |

## Out-of-scope findings

- None.

## Assumptions

- `cn()` utility at `frontend/src/utils/cn.ts` confirmed present before creating new files — matches EmptyState/StickyToolbar precedent.
- `react-router-dom` `Link` import in `PageHeader.tsx` confirmed available (used by multiple page files).
- `text-title` not present in `index.css` before this edit — confirmed by direct read of the file.
- Tests wrap `PageHeader` in `<MemoryRouter>` since `Link` requires a router context.
- `PageHeader` renders `<header>` as the root element — satisfies semantic markup requirement.
- `sticky` z-index is `z-30` (higher than StickyToolbar's `z-20`) — documented in both the JSDoc comment and the `text-title` block comment in index.css so I4 consumers can audit collision risk.
- Scope files read before editing: all listed individually in `inputs_used[]`.

## Open questions

- None.

## Next consumer brief

Rerun validation command verbatim:
```
cd frontend && npm test -- src/components/ui/__tests__/PageContainer.test.tsx src/components/ui/__tests__/PageHeader.test.tsx --run
```
Result at implementation time: 23/23 tests pass, exit 0.

Edge cases to flag for I2/I3/I4 implementors:
1. **text-title is NOT a Tailwind utility class** (it is a custom `@layer utilities` CSS class in `index.css`). Do not use `text-title` via `tw-merge` or `clsx` with Tailwind's purge — the class will always be present since it is defined in the CSS layer, not in Tailwind's JIT scan. Page tests should query `h1.className.includes('text-title')`, not use `toHaveClass('text-title')` through a Tailwind-aware helper.
2. **PageHeader sticky z-index is z-30**. StickyToolbar is z-20. I4 pages that carry StickyToolbar must NOT pass `sticky={true}` to PageHeader or they risk z-index collision.
3. **HarnessEditor (I3)**: PageContainer must be omitted; only the `h1` class needs to change to `text-title`.
4. **SpaceSettingsPage (I3)**: `PageContainer width='reading'` (768px) narrows the form from the previous 1024px — watch for field overflow, escalate via blockers[] rather than silently widening.
5. No out-of-scope findings from I1.
