# gui-refactor — forensic analysis & recovery

**Date:** 2026-06-24
**Branch analyzed:** `origin/feature/gui-refactor` (tip `26bf6d9`, 25 commits over base `aaf5e65`)
**Recovery branch produced:** `feature/gui-refactor-recovered` (off `main`)

## TL;DR

The `gui-refactor` branch is a **failed multi-phase pipeline run**. Its commit messages
and `.cronos/pipeline/*/pipeline-state.json` files claim every phase passed, but the
branch's **net diff against `main` contains zero frontend code** — every GUI feature it
produced was deleted again later in the same branch. Merging it as-is would land ~49k lines
of misleading pipeline bookkeeping and **no UI change**.

The actual delivered functionality still exists in intermediate commits. It has been
recovered onto `feature/gui-refactor-recovered`.

## How the branch self-destructed

The pipeline ran 8 GUI phases, each as `impl → fix → doc` commits:

| Phase | impl commit | What it delivered |
|-------|-------------|-------------------|
| gui-tokens-brand | `598f170` | design-token layer, brand mark (`CronosMark`), favicons, `TOKENS.md`, tailwind tokens |
| gui-layout-primitives | `350eb06` | `PageContainer`, `PageHeader`, per-page header adoption |
| gui-badge-system | `d79d513` | `ui/Badge`, `utils/badgeTone`, badge adoption across cards/detail |
| gui-button-focus | `364e0a0` | `Button`/`IconButton` focus rings, card-body→`<button>`, raw-button migration |
| gui-icons | `68a7515` | `ui/Icon` + `lucide-react`, icon audit |
| gui-modal-loading | `ce6e614` | `ui/Modal`, `ui/Skeleton`, modal/loading states |
| gui-polish | `ca21f22` | toast system, `StatTile`, `Tabs`, `Tooltip`, `ProgressBar`, `Dropdown`, touch targets |
| gui-detail-ux | `ddf639e` | `DetailShell` two-pane layout, NOW running card, compact `TreeNode`, DAG toggle |

**Root cause:** the implementor/doc agents committed against an inconsistent working tree
and *deleted prior phases' source files*. Concretely:

- `350eb06` (layout-primitives impl) **deleted** all of tokens-brand's output
  (`CronosMark.tsx`, every favicon, `site.webmanifest`, `TOKENS.md`). `4c9e272`
  ("restore gui-tokens-brand Phase 0 reverted by layout-primitives impl") names the bug.
- The four **`doc` commits** (`01d5710`, `5128ba7`, `a3fb5ed`, `26bf6d9`) are the worst
  offenders — each one *reverts source files* instead of only touching docs. `01d5710`
  re-deleted the brand mark **and** the new `PageContainer`/`PageHeader`. `a3fb5ed` deleted
  all polish primitives (`StatTile`, `Tabs`, `Toast`, …). The final `26bf6d9` deleted nearly
  every surviving artifact (`Badge`, `Icon`, `DetailShell`, `Skeleton`, `badgeTone`, all
  `ui/__tests__`), collapsing the frontend back to baseline.

### Evidence

```
git diff --stat 7476822..origin/feature/gui-refactor -- frontend/   →  (empty)
```

Zero net frontend change across the entire branch. Meanwhile the *modified* shared files
accumulated correctly up to the final doc commit — e.g. `index.css` grew monotonically
294 → 336 → 344 → 361 → 385 lines, and `Card.tsx` stabilized at 606 lines. Only the
**new files**, destroyed by mid-branch doc commits, never came back.

## Peak coherent state: `2f4144c`

`2f4144c` (gui-detail-ux fix, the commit *before* the destructive final doc `26bf6d9`)
holds the maximum surviving work: cumulative `index.css`/tailwind tokens, badge system,
button/icon primitives, modal+skeleton loading, and the `DetailShell` layout. It is missing
only the features destroyed by *earlier* doc commits and never re-added: brand identity
(`CronosMark` + favicons), layout primitives (`PageContainer`/`PageHeader`), and polish
primitives (`StatTile`/`Tabs`/`Toast`/`Tooltip`/`ProgressBar`/`Dropdown`).

## Recovery performed

`feature/gui-refactor-recovered` = `main` + `2f4144c`'s entire `frontend/` tree.
(Verified safe: `main`'s frontend is byte-identical to the branch base `aaf5e65`, so the
snapshot applies as a pure additive overlay — no `main` work is reverted.)

**Status:** `npm run build` (tsc + vite) passes clean. Adds `lucide-react` dep.

**Recovered functionality:** design tokens, badge system, icon system, Button/IconButton
primitives with focus rings, Modal + Skeleton loading, DetailShell two-pane detail layout.

**Known test gaps (intrinsic to the branch, not the recovery):**
- `main` itself is already red — 122 failing tests / 9 files (`BoardPage`, `BoardToolbar`,
  `Tree`, `useTheme`, `storage`, `format`, …) — independent of any GUI work.
- The recovery adds ~5 newly-failing test files, all from the button-focus phase
  (`src/__tests__/Card.test.tsx`, `*.buttons.test.tsx`). These tests and their `Card.tsx`
  source are byte-identical to `2f4144c`, yet the tests fail against the source — i.e. the
  **branch was already red here**. The DOM structure the tests assert
  (`[data-task-type] > div > button:last-child`) is not produced by the recovered render
  tree, a pre-existing inconsistency the original pipeline never resolved.

**Not recovered** (destroyed before `2f4144c`, would need per-feature re-grafting + consumer
re-wiring from `4c9e272` / `350eb06` / `ca21f22`): brand mark & favicons, page-header
primitives, polish primitives (toast/StatTile/Tabs/etc.).
