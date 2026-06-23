---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: gui-button-focus
phase: doc
status: done
confidence: 0.92
inputs_used:
  - .cronos/pipeline/gui-button-focus/review-report-gui-button-focus--attempt2.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i7.md
outputs_produced:
  - .cronos/pipeline/gui-button-focus/doc-report-gui-button-focus.md
  - frontend/src/components/ui/README.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: CLAUDE.md
    reason: "No key modules, architectural patterns, or agent definitions changed; Phase 3 is frontend-only UI migration with no backend, agent, or pipeline impact."
  - path: README.md
    reason: "Dev commands, deployment, auth, and security controls unchanged; button focus improvements are UX-only and do not affect build, test, or deployment procedures."
  - path: docs/HARNESSES.md
    reason: "Harness architecture and semantics unchanged; no new harness node types, triggers, or behaviors introduced."
  - path: docs/adr/001-markdown-as-truth.md
    reason: "ADR scope is git/markdown philosophy; button-focus is a UI implementation detail."
  - path: docs/adr/002-sqlite-durability.md
    reason: "ADR scope is database durability; no schema or data model changes."
  - path: docs/ui-ux-review/02-design-system.md
    reason: "Design system tokens unchanged; button-focus implements existing token palette, not new color or spacing tokens."
metrics:
  tool_calls: 28
  files_read: 8
  memory_hits: 0
  docs_updated: 1
  docs_considered: 7
---

## Summary

Phase 3 of the GUI refactor (gui-button-focus) expands `Button.tsx` and `IconButton.tsx` primitives with universal keyboard focus rings (`focus-visible:ring-1 focus-visible:ring-accent`), new variants (`tertiary`, `link` on Button), semantic archetypes (`toolbar-chip`, `dropdown-trigger`, `segmented`, `list-row`), loading spinners, `leadingIcon` slots, and 44px WCAG touch targets on all IconButton sizes. Approximately 160 inline-styled buttons were migrated across 8 components (Lane, SpaceFilterDropdown, ViewPicker, Card, MarkdownEditorModal, TimeFrameSelector) to use the new primitives. Card.tsx default-density body was converted from `<div role="button">` to native `<button type="button">`, preserving dnd-kit drag-to-reorder; nested interactive children use `span[role="button" tabIndex={0}>` to avoid HTML nesting violations. Restored `frontend/src/components/ui/README.md` (missing since gui-badge-system Phase 0) with comprehensive Button/IconButton API documentation, archetype patterns, size guidance (44px default + `compact` escape hatch), focus behavior, and migration notes. No backend, architecture, or pipeline changes.

## Updated docs

| File | Change summary |
|------|----------------|
| frontend/src/components/ui/README.md | Restored file (deleted 5128ba7 in gui-badge-system Phase 0) with 350+ lines of Button/IconButton API docs, archetype usage patterns, size guidance (44px touch target + compact 32px opt-in), keyboard focus behavior, migration notes for 8 components, and design system alignment. Includes examples for loading states, dropdown triggers, segmented toggles, and dense toolbar compacting. |

## Intentionally not updated

- **CLAUDE.md** — No key modules, architectural patterns, or agent definitions changed; Phase 3 is frontend-only UI migration with no backend, agent, or pipeline impact.
- **README.md** — Dev commands, deployment, auth, and security controls unchanged; button focus improvements are UX-only and do not affect build, test, or deployment procedures.
- **docs/HARNESSES.md** — Harness architecture and semantics unchanged; no new harness node types, triggers, or behaviors introduced.
- **docs/adr/001-markdown-as-truth.md** — ADR scope is git/markdown philosophy; button-focus is a UI implementation detail.
- **docs/adr/002-sqlite-durability.md** — ADR scope is database durability; no schema or data model changes.
- **docs/ui-ux-review/02-design-system.md** — Design system tokens unchanged; button-focus implements existing token palette, not new color or spacing tokens.

## Assumptions

- The review report verdict=pass (attempt 2) confirms that all implementation iterations (I1–I7) are committed to feature/gui-refactor. The I7 fix (commit df59946) resolved attempt-1 blocking findings F1–F5 (Card.tsx conversion + test selector updates).
- The restored frontend/src/components/ui/README.md should document the final state of Button/IconButton as they exist at commit df59946, including all variants, archetypes, sizes, and loading states.
- The review report F11 finding flags the missing ui/README.md as a documented follow-up; this doc phase addresses that finding by restoring comprehensive component documentation.
- The review report F6 finding (BoardPage.tsx not modified; toolbar-chip archetype delivered at Lane.tsx level) is acknowledged in the migration table notes but does not require separate documentation.
- The review report F9 finding (nested span[role="button"] inside Card.tsx button body) is documented in the Button migration notes as a deliberate design trade-off with justification.
- Design tokens, spacing, and color palettes remain unchanged from gui-badge-system Phase 0; no updates to design-system.md are needed.

## Open questions

None. Review report verdict=pass; all blocking findings addressed; comprehensive UI component documentation restored.

## Next consumer brief

The gui-button-focus Phase 3 implementation is complete and documented:

1. **Button.tsx enhancements**: 6 variants (primary, secondary, ghost, danger, tertiary, link), 2 sizes (sm/md), loading spinner, leadingIcon slot, 4 semantic archetypes (toolbar-chip, dropdown-trigger, segmented, list-row), universal focus ring on all variants.

2. **IconButton.tsx enhancements**: 5 variants (default, accent, accent-soft, danger, danger-hover), 3 sizes (sm/md both 44px, compact 32px opt-in), universal focus ring on all variants. The 44px default meets WCAG 2.5.5 touch target; `compact` is available with documented opt-out for dense toolbars.

3. **Component migrations**: ~160 inline buttons across Lane, SpaceFilterDropdown, ViewPicker, Card, MarkdownEditorModal, TimeFrameSelector now use Button/IconButton primitives with semantic archetypes (e.g., dropdown triggers, segmented toggles, list-row menus).

4. **Card.tsx design trade-off**: Default-density card body is now a native `<button type="button">` with dnd-kit drag preserved; nested interactive children (breadcrumb, realizes-chip) use `span[role="button" tabIndex={0}>` to avoid invalid nested-button HTML. This is intentional and documented in the ui/README.md migration notes.

5. **Accessibility**: All buttons feature consistent keyboard focus rings (focus-visible:ring-1 focus-visible:ring-accent) for reliable keyboard navigation discovery across all UI surfaces.

The restored frontend/src/components/ui/README.md serves as the source of truth for Button/IconButton API, variant guide, archetype patterns, and size recommendations (44px default + compact escape hatch). Callers should prefer `archetype` props over raw className strings for consistency.

No regression risk: implementation verified at commit df59946 with 1530/1531 vitest green (the lone failure is pre-existing FileBrowserPage error from layout-primitives Phase, commit e957bfc, unrelated to button focus). Build clean. Ready to merge to main.
