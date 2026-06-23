---
cc_version: '1.0'
agent: pipeline-implementor
slug: gui-detail-ux--i6
phase: impl
status: done
confidence: 0.95
inputs_used:
- .cronos/pipeline/gui-detail-ux/design-report-gui-detail-ux.md
- frontend/src/components/TreeNode.tsx
- frontend/src/components/__tests__/Tree.test.tsx
- frontend/src/components/__tests__/TreeDnd.test.tsx
iteration_id: I6
files_changed:
- frontend/src/components/TreeNode.tsx
- frontend/src/components/__tests__/Tree.test.tsx
- frontend/src/components/__tests__/TreeDnd.test.tsx
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
- .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i6.md
blockers: []
next_consumer: review
metrics:
  tool_calls: 14
  files_read: 4
  memory_hits: 1
  diff_lines_added: 65
  diff_lines_removed: 55
---

## Summary

Replaced `<Card density="tight">` in `TreeNode.tsx` with a compact inline
button row using `STATE_BADGE` + `<h3>` title. Added vertical connector line
for expanded children. Preserved GapZone and all dnd-kit wiring. 94/94
Tree+TreeDnd tests pass.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/TreeNode.tsx | modified | +45 / -45 | Replace Card wrapper with native button row; add `border-l border-hairline` vertical connector on expanded children group |
| frontend/src/components/__tests__/Tree.test.tsx | modified | +10 / -5 | Update selectors from Card-based to button/heading queries |
| frontend/src/components/__tests__/TreeDnd.test.tsx | modified | +10 / -5 | Update selectors from Card-based to button/heading queries |

## Out-of-scope findings

None.

## Assumptions

- GapZone and all dnd-kit `useSortable` attributes/listeners/setNodeRef are preserved on the outer `<li>` element.
- The compact row is a `<button>` for keyboard/click focus on the node itself; the expand/collapse toggle is a separate child element.
- `STATE_BADGE` provides inline state indicator (badge text + color class) for the task state.

## Open questions

None.

## Next consumer brief

Validation command:
```
cd /data/spaces/cronos-development/frontend
npm test -- src/components/__tests__/Tree.test.tsx src/components/__tests__/TreeDnd.test.tsx --run
```

All 94 tests pass. I7 builds on top to add the DAG toggle in TreeToolbar
and the view-mode switch in TreeView.
