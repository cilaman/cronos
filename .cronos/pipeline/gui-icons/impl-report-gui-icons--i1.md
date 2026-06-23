---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-icons--i1
phase: impl
status: done
confidence: 0.9
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:project_gui_badge_system_impl
  - .cronos/pipeline/gui-icons/design-report-gui-icons.md
  - frontend/package.json
  - frontend/src/components/ui/__tests__/ui.test.tsx
iteration_id: I1
files_changed:
  - frontend/package.json
  - frontend/src/components/ui/Icon.tsx
  - frontend/src/components/ui/__tests__/Icon.test.tsx
validation_command_passed: true
out_of_scope_findings:
  - description: "lucide-react always injects 'lucide lucide-{name}' class names on the SVG element even when no className prop is passed; this is library-default behaviour and does not affect rendering correctness."
    location: "frontend/node_modules/lucide-react/dist/cjs/lucide-react.js:63"
    severity: low
outputs_produced:
  - .cronos/pipeline/gui-icons/impl-report-gui-icons--i1.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 28
  files_read: 5
  memory_hits: 2
  diff_lines_added: 187
  diff_lines_removed: 0
---

## Summary

Iteration I1 implements the lucide-react foundation for the Cronos GUI icon system. `lucide-react@^0.511.0` was added to `frontend/package.json` dependencies, `frontend/src/components/ui/Icon.tsx` was created as a thin explicit-props wrapper (no naive spread) with sm/md/lg size variants, and `frontend/src/components/ui/__tests__/Icon.test.tsx` was created with 11 tests covering all size variants, default size, aria-hidden, stroke=currentColor, className passthrough, and the no-duplicate-attributes invariant. Validation passed with 11/11 tests green. One notable implementation detail: the no-duplicate-attributes tests use the DOM `svg.attributes` collection (not innerHTML string-matching) because `\bwidth=` regex would false-positive on `stroke-width=`; I5 and sibling implementors should use the same DOM-API approach for attribute checks.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/package.json | modified | +1 / 0 | Add lucide-react ^0.511.0 to dependencies |
| frontend/src/components/ui/Icon.tsx | created | +51 / 0 | Icon wrapper with explicit resolved-props (size→px, strokeWidth per size, aria-hidden, stroke=currentColor) |
| frontend/src/components/ui/__tests__/Icon.test.tsx | created | +135 / 0 | 11 unit tests: 3 size variants, default size, a11y attrs, className passthrough, no-duplicate-attributes via DOM attrs API |

## Out-of-scope findings

- `lucide-react` always merges `"lucide lucide-{iconName}"` into the class attribute even when no `className` prop is passed to the LucideIcon component. This is library-default behaviour (`mergeClasses("lucide", className)` in the library source). The Icon.tsx wrapper does not suppress these classes; they are harmless but relevant if I2–I4 test code checks for an empty class attribute on the SVG. Tests must assert `classList.contains('lucide')` (which is always true) rather than asserting an empty class. Already handled in Icon.test.tsx by adjusting the "className omitted" test accordingly.

## Assumptions

- `lucide-react ^0.511.0` is a stable release that supports `currentColor` stroke and CSS-variable styling; no specific version pinning beyond the caret range.
- The `ui/` directory already existed from prior gui-badge-system phase (Badge.tsx, EmptyState.tsx, etc.) — only the two new files were created.
- `Icon.tsx` uses lucide's `size` prop (sets both `width` and `height` in one pass) to ensure the SVG element carries exactly one `width` and one `height` attribute. Passing separate `width` and `height` props alongside `size` would cause duplicates because lucide's render function spreads `defaultAttributes` (which sets `width: 24, height: 24`) then overrides with `width: size, height: size` — if we then added `width`/`height` in `...rest` they would appear as third occurrences.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Validation command to rerun: `cd frontend && npm test -- src/components/ui/__tests__/Icon.test.tsx`

**Cross-iteration invariants (binding for I2/I3/I4):**
1. `Icon.tsx` is read-only after I1 — I2/I3/I4 must NOT modify it.
2. Import from `'lucide-react'` (not `'@lucide/react'`); icon names are PascalCase (Bot, Zap, Command, FileText, Terminal, Image, FileCode, Plus, X, ChevronDown, ChevronRight, Sun, Moon, Menu).
3. The Icon wrapper always renders `class="lucide lucide-{name}"` on the SVG (library default). Tests checking class must use `classList.contains()`, not assert empty class.
4. For no-duplicate-attributes assertions, use `Array.from(svg.attributes).filter(a => a.name === 'width')` — do NOT use `innerHTML.match(/\bwidth=/)` as the `\b` word boundary makes that regex match `stroke-width=` as well.
5. `npm install` was run to install lucide-react; I2/I3/I4 start from a state where node_modules already has the package.
