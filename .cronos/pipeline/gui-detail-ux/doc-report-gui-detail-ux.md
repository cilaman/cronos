---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: gui-detail-ux
phase: doc
status: done
confidence: 0.85
inputs_used:
  - .cronos/pipeline/gui-detail-ux/review-report-gui-detail-ux--attempt2.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i1.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i2.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i3.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i4.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i5.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i6.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i7.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i8.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i9.md
  - CLAUDE.md
  - docs/ui-ux-review/README.md
outputs_produced:
  - .cronos/pipeline/gui-detail-ux/doc-report-gui-detail-ux.md
  - CLAUDE.md
  - docs/ui-ux-review/README.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: README.md
    reason: "Implementation is pure frontend UI refactoring; backend commands and architecture unchanged."
  - path: TESTING.md
    reason: "Test infrastructure and commands unchanged; implementation includes 30/30 green tests for Detail, 20/20 for DetailShell, and 10/10 for no-raw-palette-classes validator."
  - path: docs/HARNESSES.md
    reason: "TreePage and harness visualization remain unchanged in scope; F6 disclosure (TreeToolbar toggle placement) is a component-level detail not reflected in harness architecture docs."
metrics:
  tool_calls: 12
  files_read: 12
  memory_hits: 0
  docs_updated: 2
  docs_considered: 5
---

## Summary

Goal gui-detail-ux (2026-06-22-1335) delivers three major frontend UX improvements: (1) DetailShell shared modal component unifying task and feature detail views; (2) two-pane workspace in Detail.tsx (Context left | Conversation right, independently scrolling; mobile tab switch); (3) tree view enhancements (TreeNode connector lines, TreeToolbar Tree/DAG toggle). All 9 iterations passed review with zero new test regressions. Documentation updated to reflect: DetailShell + Detail + FeatureDetail + TreeNode + TreeToolbar entries in CLAUDE.md Key modules; implementation status section in ui-ux-review/README.md noting component adoption, layout changes, semantic token migration, and three non-blocking deviations (F6/F7/F8).

## Updated docs

| File | Change summary |
|------|----------------|
| CLAUDE.md | Added 5 frontend component entries to Key modules table: DetailShell (shared shell), Detail (two-pane workspace), FeatureDetail (shell adoption), TreeNode (connector lines), TreeToolbar (Tree/DAG toggle with F6 disclosure). |
| docs/ui-ux-review/README.md | Added "Implementation status" section documenting gui-detail-ux delivery, component layer-by-layer adoption, non-blocking deviations (F6: toggle placement, F7: test-only scope escape, F8: DetailShell unification deferred), and link to concurrent gui-refactor goal tree. |

## Intentionally not updated

- **README.md** — Implementation is pure frontend UI refactoring; backend commands, VPS setup, and overall architecture section remain unchanged.
- **TESTING.md** — Test infrastructure and commands unchanged; frontend test suite passes with zero new regressions (30/30 Detail, 20/20 DetailShell, 10/10 palette validator tests green).
- **docs/HARNESSES.md** — TreePage structure and harness visualization architecture scope are separate; F6 disclosure (TreeToolbar toggle placed by I7 design choice) is component-level detail, not arch-level.

## Assumptions

- Changelog hook extracted from review-report-gui-detail-ux--attempt2.md "Next consumer brief" (lines 81–91): three structural UX improvements (DetailShell, two-pane workspace, tree connectors) with disclosure of non-blocking deviations.
- files_changed[] union across all 9 impl reports: DetailShell.tsx + DetailShell.test.tsx (I1), Detail.tsx + Detail.test.tsx (I2/I4/I5), FeatureDetail.tsx (I3), TreeNode.tsx + TreeView.tsx (I6), TreeToolbar.tsx (I7), DetailPRSection.test.tsx (I8 scope escape disclosed), Toast.tsx + ToastProvider.test.tsx deletion (I9), cronos-state-active-animated.svg asset (I5).
- DetailShell owns Modal wrapper, skeleton, error+retry, header/footer slots; waiting bar and edit toggle intentionally kept per-variant (FeatureDetail/Detail inline) per F8 deferred-scope note.
- Mobile breakpoint md (768px) is canonical per review-report and impl-reports; two-pane collapses to tab switch on <768px devices.
- No new architecture or backend changes; all updates are documentation of existing/delivered frontend implementation.

## Open questions

- None.

## Next consumer brief

**Components now documented in CLAUDE.md Key modules:**
- **DetailShell** — unified shell primitive for task/feature details; `variant: 'task' | 'feature'`, Modal-wrapped, owns skeleton/error/header/footer slots. Used by both Detail and FeatureDetail, eliminating parallel header/skeleton implementations.
- **Detail** — task detail view now adopts DetailShell, adds two-pane workspace (Context left, Conversation right with independent scroll), sticky NOW running card for ACTIVE tasks, and semantic token badge styles (replaces 24 raw palette classes).
- **FeatureDetail** — feature detail view adopts DetailShell, replaces local skeleton/header markup, uses semantic token badge styles.
- **TreeNode** — compact row rendering with connector lines; dnd-kit useSortable wiring preserved.
- **TreeToolbar** — Tree/DAG toggle button (Note F6: button placement is in TreeToolbar, not TreePage, by I7 design choice — substantively equivalent to spec).

**Non-blocking deviations disclosed in review (for future readers):**
- **F6:** Tree/DAG toggle lives in TreeToolbar.tsx (not TreePage.tsx as design body mentioned). Intentional I7 placement; toolbar is the natural home.
- **F7:** DetailPRSection.test.tsx received a mock-fix (I8, undisclosed scope escape); test-only, non-blocking.
- **F8:** DetailShell does NOT own waiting bar or edit toggle (design mentioned unification); kept inline in Detail/FeatureDetail to avoid prop-surface expansion. Intentional deferred scope.

**Build & test gate:** npm run build clean (tsc + vite 0 errors), npm test shows exactly 5 pre-existing failing files (Card, MarkdownEditorModal, etc.) from prior gui goals, zero new regressions. Mobile-responsive two-pane layout and tab-switch tested at md (768px) breakpoint.

Forward: Documentation now ready for future contributors to understand DetailShell contract, two-pane workspace layout constraints (`h-full min-h-0` flex patterns), and mobile responsive design. See CLAUDE.md Key modules and docs/ui-ux-review/README.md for implementation lineage.
