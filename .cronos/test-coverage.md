# Test Coverage — cronos-development

**Updated**: 2026-06-03T14:50:00Z
**Backend overall**: 82.73%  (1510 passed, 0 failed — unchanged scope, no backend code touched this task)
**Frontend**: 750 vitest tests passed across 41 files (+7 this session)
**Tester rounds this session**: 1 (full vitest + full pytest both green on first run, no regressions)

## Recent changes (2026-06-03 — arc-5/C4 Frontend per-tool telemetry panel)

Frontend-only task. New component `frontend/src/components/AdoptedToolTelemetry.tsx`
(strip + expand/collapse), wired into `SpaceToolsPage` AdoptedSection rows, backed by
`useToolTelemetry` hook → `api.toolTelemetry` → `GET /api/spaces/{id}/tools/{kind}/{name}/telemetry`
typed by `ToolTelemetryResponse`. Backend telemetry endpoint shipped in arc-5/C2; no
backend code changed here.

Added 7 behavior-focused tests to `frontend/src/__tests__/AdoptedToolTelemetry.test.tsx`
(now 19 tests), covering previously-untested branches:
- **Loading state** — `loading…` shown while query pending; no call-count/no-calls leak.
- **Pluralization** — singular "1 call" vs plural "2 calls" (`calls !== 1` branch).
- **Success-rate color thresholds** — green at the inclusive 0.9 boundary, amber at 0.7,
  danger below 0.7 (guards `>=` vs `>` regressions in `successColor`/`SuccessBar`).
- **Error breakdown** — error-rate computation (`errors/calls` rounding), `{n} err` /
  `{n} ok` legends present when `errors > 0`, and error legend omitted when `errors === 0`.
- **Accessibility** — `aria-expanded` toggles false→true on strip click.

The pre-existing tests already covered: strip with data, empty-history (calls=0),
expand/collapse, window-prop passthrough, detail stat cells.

---

## Backend (unchanged this task — prior session figures retained below)

**Prev backend run**: 82.87%  (+0.25% vs previous run 2026-06-03 A3-index)
**Passed**: 1417 | **Failed**: 0 | **Errors**: 0 | **Skipped**: 0 | **Total**: 1417

## Recent changes (2026-06-03 — B2 Adopt/Unadopt/List-Adopted API)

Task B2 of Arc 5. New file `backend/app/api/adoption.py` (POST adopt / DELETE
unadopt) plus the `adopted` branch of `GET /api/spaces/{id}/tools` in
`api/tools.py` (`_scan_adopted` + `_derive_status`), backed by `AdoptedToolEntry`
in `models.py`.

- `app/api/adoption.py`: **100%** (35/35 statements) — new test file
  `backend/tests/test_api_adoption.py`, 12 tests.
- `app/api/tools.py`: 83% (adopted branch fully covered; remaining misses are the
  unrelated `tool-content` endpoint).
- adopt/unadopt endpoints tested by monkeypatching `app.api.adoption.adopt` /
  `unadopt` (the API-module boundary); tools/adopted tests use real manifest.yml
  round-trips + `recompute_local_sha` in the tmp space dir.

### Behavior finding (status derivation)
`recompute_local_sha` couples `evolved` to drift: it sets
`evolved = (local_sha != base_sha)`. Because `_derive_status` checks `evolved`
first, an edited tool surfaces as status=**"evolved"** after recompute, never
"edited". The "edited" status branch (`local_sha != base_sha` AND `evolved is
False`) is only reachable for a manifest written with that exact state and is
not produced by `recompute_local_sha`. Both paths are now pinned by tests
(`test_tools_local_drift_without_evolved_shows_edited` and
`test_tools_recompute_after_edit_marks_evolved`). If the product intent is that
a plain local edit should read as "edited" (not "evolved"), this coupling in
`recompute_local_sha`/`_derive_status` is a likely bug to revisit.

## Recent changes (2026-06-03 — A3 discovered_tools SQLite index/upsert)

Task A3 of Arc 5. New module `backend/app/tools/index.py` (upsert_discovered /
prune_stale / list_discovered over the `discovered_tools` table) and DDL added to
`storage.py::_ensure_db_schema()` (table + `idx_discovered_tools_kind`).

- `app/tools/index.py`: **100%** (39/39 statements)
- New test file `backend/tests/test_tools_index.py` — 12 tests, all 6 acceptance
  criteria covered: prune-stale-on-rerun, new-SHA-in-place-update, order stability,
  kind filter, source_slug filter, prune-count + slug scoping.
- DB fixture reproduces the DDL inline (no TaskStore / _ensure_db_schema dependency).

## Recent changes (2026-06-03 — A2 Discovery module: clone + walk + parse)

Task A2 of Arc 5. New module `backend/app/tools/discovery.py` (clone/refresh/walk +
`DiscoveredItem`, `_make_slug`) and refactor of the scanner helpers out of
`api/tools.py` into the shared `backend/app/tools/scanner.py`.

- `app/tools/discovery.py`: **100%** (79/79 statements)
- `app/tools/scanner.py`: **94%** (shared single source of truth)
- `app/api/tools.py`: 84% (now imports scanner helpers; no duplicate impls)
- No module lost coverage; full suite green.

### Tests added in `backend/tests/test_tools_discovery.py` (+18 funcs / 21 cases, NEW)

- **`_make_slug` (3 funcs / 6 cases)**: https/http/ssh-scp form → safe slug;
  `.git` suffix stripped; collapses unsafe-char runs and trims dashes;
  every output char is filesystem-safe.
- **`clone_source` (3)**: shallow `clone --depth 1` invoked with dest as last
  arg; `--branch` passed when `source.branch` set; existing `.git` short-circuits
  (no re-clone).
- **`refresh_source` (3)**: existing clone → `fetch` then `reset --hard FETCH_HEAD`
  (never `clone`); no-branch falls back to `HEAD`; missing clone delegates to clone.
- **`walk_source` (7)**: returns all four kinds {agent, skill, command, hook};
  agent/skill/hook metadata (name, description, relative_path, source_url/slug/sha);
  dir-based skill uses directory name; no `.claude/` → empty without touching git;
  git-unavailable fallback (slug=dir name, sha=""); hook command truncated to 200,
  wildcard matcher → `Event:*`.
- **Single-source-of-truth guard (1)**: asserts `api_tools._scan_category` etc.
  are the *same objects* as `scanner.*` — catches re-introduced duplicate impls.
- **DiscoveredItem (1)**: dataclass fields/defaults.

Boundaries mocked: `app.tools.discovery._run` / `_run_or_raise` / `_auth_env`
(git subprocess boundary); `DISCOVERY_BASE` monkeypatched to `tmp_path`. `walk_source`
exercises real `.claude/` fixture dirs (tmp_path) so scanner parsing is real I/O.

## Suspected flakes
- none this session

---

## Recent changes (2026-06-03 — tool-sources YAML loader + schema)

**Overall backend**: 82.31% | **Passed**: 1340 | **Failed**: 0 | **Total**: 1340
**Tester rounds this session**: 1 (new tests green on first run; full suite green)

New module `backend/app/tools/sources.py` (`ToolSource` model + `load_sources`)
covered to **100%** (37/37 statements) by a new file
`backend/tests/test_tools_sources.py` (20 tests). No regressions; no module
lost coverage.

### Tests added in `backend/tests/test_tools_sources.py` (+20, NEW)

- **AC1 — valid parse (6 tests)**: full multi-entry parse with all fields;
  field defaults (`branch`/`label`=None, `enabled`=True); `enabled: false`
  round-trips (not dropped); `sources:` null → `[]`; missing `sources` key
  → `[]`; empty file (yaml→None) → `[]`.
- **AC2 — invalid URL (6 tests)**: parametrized bad URLs (empty, contains
  space, space-in-host, shell metachar `;rm -rf /`, command-subst
  `$(whoami)`, >2048 chars) each raise `ToolSourceError`; constructor-level
  validation; one-bad-URL-aborts-the-whole-load (no partial list); non-mapping
  entry wraps the pydantic error with "Invalid tool source entry"; missing
  required `url` field raises.
- **AC3 — missing file (1 test)**: nonexistent path → `[]`.
- **AC4 — env override (3 tests)**: `CRONOS_TOOL_SOURCES_PATH` wins over the
  `path` argument; override pointing at a missing file → `[]` (override still
  wins); empty-string env var is falsy and falls back to the `path` argument.

An autouse fixture clears `CRONOS_TOOL_SOURCES_PATH` so only the AC4 tests
exercise the override branch (no cross-test env leakage).

---

# Test Coverage — cronos-development (prior sessions)

**Updated**: 2026-05-26T14:19:00Z
**Backend (pytest)**: 862 passed, 2 failed (+9 vs prev 853 passed; 2 failed are
  pre-existing auth/health failures unrelated to this session's changes)
**Frontend (vitest)**: 539 passed, 122 failed (+34 vs prev 505 passed; -18 vs
  prev 140 failed — the Detail.test.tsx mock fix this session unblocked 18
  previously-failing tests. Remaining 122 failures are all pre-existing
  (timezone, BoardPage/BoardToolbar mocks, useTheme, etc.) and unchanged
  by this session's edits)
**Tester rounds this session**: 1 (1 setup correction during writing; new
  tests all passed on the second run; full suites green for everything
  touched)

## Recent changes (2026-05-26 — Detail-view Send-to-Backlog + Move-to-Done buttons)

Coverage for the explicit "Send to Backlog" and "Move to Done" buttons on
the task/goal detail view, plus the underlying `archived->done`
USER_TRANSITION pair newly added in `backend/app/storage.py` (line 50).

### Backend — tests added in `backend/tests/test_storage.py` (+6)

- `test_task_store_transition_archived_to_done_succeeds_for_plain_task` —
  locks the new (ARCHIVED, DONE) pair. Plain task driven backlog->active->
  done->archived, then archived->done returns DONE.
- `test_task_store_transition_archived_to_done_refused_for_goal_with_open_children`
  — archived goal with a non-terminal child MUST raise InvalidTransition.
  Setup writes ARCHIVED into `_by_id` directly because the legal goal->
  archived path requires the children to already be terminal (which would
  defeat this test's purpose). Asserts error message names the child id
  and the goal stays in ARCHIVED (gate-before-mutate contract).
- `test_task_store_transition_archived_to_done_allowed_for_goal_with_all_children_terminal`
  — goal with one done + one archived child can transition archived->
  done. Children unchanged by the goal transition.
- `test_task_store_transition_waiting_to_backlog_succeeds_for_plain_task`
  — regression guard for the existing waiting->backlog pair now exposed
  as a button.
- `test_task_store_transition_waiting_to_backlog_clears_waiting_question`
  — locks storage.py:742 ("Leaving the waiting lane clears any pending
  question") specifically for the Send-to-Backlog button flow. A stale
  question carried into the next waiting cycle would confuse the operator.
- `test_task_store_transition_done_to_backlog_succeeds_for_plain_task` —
  regression guard for the 'reopen-as-todo' button.

### Backend — tests added in `backend/tests/test_api_tasks.py` (+3)

End-to-end via `PATCH /api/tasks/{id}/state`:

- `test_patch_state_archived_to_done_succeeds_for_plain_task` — 200 +
  body state=done + in-store state confirms.
- `test_patch_state_archived_to_done_refused_for_goal_with_open_children`
  — 409 + detail string contains "open children" and the child id. Same
  setup-bypass as the storage-level test.
- `test_patch_state_done_to_backlog_succeeds_for_plain_task` — 200 +
  body state=backlog.

### Frontend — NEW file `frontend/src/components/__tests__/TaskActionBar.test.tsx` (+15)

- **5 parametrized tests** (`it.each`) — one per TaskState (backlog,
  active, waiting, done, archived) — assert the exact visible button set
  via aria-labels. Uses `toEqual` not `toContain` so an accidental new
  button (or a removed one) on the wrong state surfaces immediately.
  Catches a regression that would silently broaden the showMarkDone /
  showSendToBacklog predicates.
- **5 click→callback tests** — Send-to-Backlog fires onSendToBacklog from
  each of {waiting, done, archived} and NOT the other callbacks
  (cross-callback negative assertion). Also asserts Send-to-Backlog is
  NOT rendered on {backlog, active}.
- **3 Mark-Done tests** — fires onMarkDone from waiting and the newly
  exposed archived state. Asserts NOT rendered on `done` (regression
  guard against an idempotent no-op button).
- **2 isSendingToBacklog disabled tests** — button is `disabled` when
  prop is true, and a click on a disabled button does not invoke the
  callback (locks the IconButton `disabled || loading` contract for the
  new prop).

### Frontend — tests added in `frontend/src/components/__tests__/Detail.test.tsx` (+1, plus mock fix)

- New `calls transitionTask.mutateAsync with backlog state when Send to
  Backlog is clicked` test mirrors the existing Mark Done test pattern:
  click `data-testid="send-to-backlog-btn"` and assert transition mutate
  was called with `{ id: "task-abc", state: "backlog" }`.

**Mock fix unblocking 18 previously-failing tests in this file:**

The Detail.test.tsx vi.mock of `../../hooks/useTasks` was incomplete and
missing `useRoutePreview`, `useBoard`, `usePromoteTask`, `useSetParent`,
and `useSetDependsOn`. Detail.tsx imports all of these directly; vitest
threw `[vitest] No "useRoutePreview" export is defined on the mock` at
render time, which was failing every test that did not hit a loading-
state early-return. Adding the missing hooks to the mock module
+ setting their default return values in `beforeEach` restored 18 of the
19 pre-existing tests in this file to passing. This was already a bug;
the new "Send to Backlog" button was the test that surfaced the missing
mock prop the user flagged.

### Tests that revealed setup issues during writing

- The first version of `test_task_store_transition_archived_to_done_refused_for_goal_with_open_children`
  tried to drive the goal through backlog->active->done->archived via
  the legal transitions, but the goal-done gate (storage.py:729-734)
  fires for the `(active, done)` worker transition when children are
  non-terminal — making the legal setup path impossible exactly when the
  preconditions of this test are interesting. Switched to writing the
  ARCHIVED state directly into `_by_id` for setup, then exercising the
  user-facing transition method against that pre-arranged state. Same
  fix applied to the parallel API-level test.

### Frontend coverage delta

No coverage tooling is wired into vitest. Test counts:
- 505 -> 539 passed (+34) — 15 new in TaskActionBar.test.tsx + 1 new in
  Detail.test.tsx + 18 pre-existing Detail.test.tsx tests un-blocked
  by the mock fix.
- 140 -> 122 failed (-18) — solely from the mock fix above. Remaining
  122 failures are pre-existing and unrelated to this session.

### Backend coverage delta this session

- `app/storage.py`: 88% → 88% (slight change expected to USER_TRANSITIONS
  set definition; the new transition path was already structurally
  covered by the generic gate code).
- Overall backend: held at ~80% (full run did not re-emit
  --cov-fail-under here because tests were filtered, but the
  no-cov full run is green at 862/864).

All 9 new backend tests + 16 new frontend tests pass; no regressions
introduced.

## Recent changes (2026-05-25 — arc-9/3: children_progress + progress bar on goal cards)

Added 8 tests in `backend/tests/test_api_tasks.py` covering the new
`_enrich_progress(board)` function in `app/api/tasks.py` which decorates
every goal `TaskSummary` with a `ChildrenProgress(done, total, waiting)`
field counted from the board's goal-children relation.

### Tests added in `backend/tests/test_api_tasks.py` (+8, NEW)

All tests go through the public `GET /api/tasks?space_id=...` boundary
so they exercise the full pipeline (`store.board()` → `_enrich_board()`
→ `_enrich_progress()` → JSON response) rather than just the helper in
isolation. Each test asserts on the response body's
`children_progress` shape, the value of `None` for the negative
cases, and the exact `{done, total, waiting}` dict for the positive
ones.

- `test_goal_with_mixed_children_states_gets_correct_children_progress` —
  goal with 4 children spread across backlog/active/waiting/done lanes;
  result is `{done:1, total:4, waiting:1}`. Locks the three-count
  contract: `done` and `waiting` are mutually exclusive buckets within
  `total`.
- `test_non_goal_task_has_no_children_progress` — `type='task'` and
  `type='issue'` parents (each with one real child) MUST surface
  `children_progress: null`. Regression guard against future widening
  of the `t.type == 'goal'` gate.
- `test_goal_with_no_children_has_no_children_progress` — a goal with
  zero children gets `children_progress: null`, NOT
  `{done:0, total:0, waiting:0}`. The `if children:` empty-list-falsy
  branch is load-bearing — a zero-total dict would render an empty
  "0/0" pill on the card and a divide-by-zero (`NaN%`) width in the
  bar.
- `test_goal_with_archived_only_children_has_no_children_progress` —
  archived children are excluded from `store.board()`, so a goal whose
  ONLY child is archived must NOT be counted as having children. Locks
  the contract that `_enrich_progress` operates over the board (which
  has no archived lane), not over the full task store.
- `test_goal_with_all_children_done_reports_full_progress` — every
  child `done` → `{done:2, total:2, waiting:0}`. Regression guard
  against accidentally double-counting `done` children into `waiting`
  (or vice versa) in the same aggregation pass.
- `test_children_of_other_goals_do_not_leak_into_progress` — two
  sibling goals A (1 child) and B (3 children); counts are correctly
  scoped per parent. Off-by-parent regression guard for the
  `parent_id`-keyed dict.
- `test_root_level_tasks_dont_appear_as_anyones_children` — a
  root-level task (`parent_id=None`) is NOT silently attributed to any
  goal. Locks the `if t.parent_id:` guard on the children-map build
  step.
- `test_children_progress_present_on_all_space_query` — the
  `?space_id=all` cross-space board also runs through
  `_enrich_progress`. Regression guard against a future scope-dependent
  code path that bypasses the enrichment step.

### Acceptance-criteria coverage matrix

| Acceptance criterion | Test |
|----------------------|------|
| Goal with mixed children states gets correct children_progress | `test_goal_with_mixed_children_states_gets_correct_children_progress` |
| Non-goal tasks have no children_progress | `test_non_goal_task_has_no_children_progress` |
| Goal with no children has no children_progress | `test_goal_with_no_children_has_no_children_progress`, `test_goal_with_archived_only_children_has_no_children_progress` |
| Counts don't leak between sibling goals | `test_children_of_other_goals_do_not_leak_into_progress` |
| Root-level tasks not attributed to any goal | `test_root_level_tasks_dont_appear_as_anyones_children` |
| Cross-space `?space_id=all` also enriches | `test_children_progress_present_on_all_space_query` |

### Coverage delta this session

- `app/api/tasks.py`: 68.5% → 71.9% (+3.4 pts) — new `_enrich_progress`
  branches (goal vs non-goal, has-children vs empty, the per-state
  counting comprehension) are fully exercised.
- `app/models.py`: 100% → 100% (unchanged — `ChildrenProgress` is a
  plain Pydantic model with no runtime branches).
- Overall backend: 80.73% → 80.84% (+0.11 pts).

All 826 backend tests + 417 frontend tests pass on first run; no
regressions.



## Recent changes (2026-05-25 — arc-3/4: ViewEditor — manage-views modal)

Added 20 frontend tests covering the new `ViewEditor` two-pane modal and
the updated `useViews` mutations (which now also invalidate `["board"]`).
Backend was untouched.

### Tests added in `frontend/src/__tests__/ViewEditor.test.tsx` (+20, NEW)

- 4 in `ViewEditor — rendering & selection`: renders dialog with view
  list; lazy-init to the default view (not `currentViewId`); selecting a
  view loads its lanes + type_filter into the form; "+ New view" yields a
  blank form with all lanes + no type filter.
- 5 in `ViewEditor — validation & save`: blank name error; zero-lanes
  error; duplicate-name error (case + whitespace insensitive); valid
  save on a new view calls `createView` with trimmed name and clears
  dirty state; valid save on existing view calls `updateView` with the
  view id and current form values (and does NOT call `createView`).
- 2 in `ViewEditor — duplicate & set default`: duplicate calls
  `createView` with `<name> (copy)` and `default: false`; "set as
  default" on a non-default view calls `updateView({default: true})`.
- 5 in `ViewEditor — delete`: delete disabled when only 1 view; opens
  confirm alertdialog; cancel closes without calling `deleteView`;
  confirm calls `deleteView(spaceId, viewId)`; `onViewChange(null)`
  is fired when the deleted view IS the active board view; NOT fired
  when it ISN'T.
- 4 in `useViews mutations also invalidate ['board'] queries`: create,
  update, delete each invalidate both `["views", spaceId]` AND
  `["board"]`; delete does NOT invalidate on api failure.

### Suspected production bug surfaced by tests

`ViewEditor` enters an infinite render loop while `useViews` is
resolving: the destructuring `const { data: views = [] } = useViews(...)`
yields a fresh `[]` reference each render when `data` is still
`undefined`, and the unconditional `useEffect([selectedId, views])`
calls `setFormRaw(blank())` on every fire — which schedules another
render. In production it appears to recover once the cache hydrates,
but it is a latent rendering bug. The tests work around it by
pre-seeding the query cache; see the inline comment in `renderEditor`.
Recommended fix: gate the form-sync effect on `views.length > 0` or
move the `[]` default outside the destructure so its identity is stable.

## Recent changes (2026-05-25 — arc-3/3: ViewPicker — switch views from the Board toolbar)

Added 32 frontend tests covering the new `ViewPicker` component, its
slot in `BoardToolbar`, and the URL-driven view state management in
`BoardPage`. Backend was untouched; the existing
`test_api_views.py` (41 tests from arc-3/2) still passes.

### Tests added in `frontend/src/__tests__/ViewPicker.test.tsx` (+18, NEW)

Pure component tests with a `vi.mock`'d `../api` so `useViews()` resolves
deterministically. Each test renders the picker inside a fresh
`QueryClient` (no shared state between tests).

- `renders the default view name when viewId is null` — trigger shows
  the `default: true` view's name when no URL param is set.
- `renders the matching view name when viewId is set` — trigger shows
  the named view's name when `viewId` matches.
- `falls back to the default view when viewId is unknown` — stale
  bookmark fallback: trigger still shows the default, never crashes
  or blanks.
- `renders 'Views' placeholder while the query is loading` — locks
  the no-data UX (uses a never-resolving promise to hold the query
  in loading state).
- `opens the dropdown when the trigger is clicked` — every view name
  is rendered inside the menu after the click.
- `calls onChange with view.id when a non-default view item is clicked`.
- `calls onChange with null when the default view item is clicked` —
  locks the clean-URL contract: selecting the default emits `null`
  (clear `?view=`), not the default's id.
- `closes the dropdown after selecting a view` — asserted via the
  presence/absence of the "Manage views…" footer (unique to the
  open menu).
- `renders a star icon next to the default view in the dropdown` —
  isolates "default star" from "active check" by using a non-active,
  non-default row as the zero-svg baseline.
- `renders a star icon in the trigger when the active view is the default`.
- `does NOT render a star icon in the trigger when the active view
  is non-default` — regression guard against accidentally always
  showing the star.
- `renders a check icon next to the active view in the dropdown`.
- `calls onManageViews and closes the dropdown when 'Manage views…'
  is clicked` — single click both invokes the callback and dismisses
  the menu.
- `calls api.spaceViews with the provided spaceId` — locks the
  hook→API wiring.
- `closes the dropdown when Escape is pressed`.
- `closes the dropdown when clicking outside the picker` — direct
  `mousedown` dispatch on `document.body` (userEvent does not
  synthesize the event the picker listens to).
- `does not call onManageViews when the dropdown is opened then
  closed without clicking 'Manage views…'`.
- `tolerates an empty views list without crashing the trigger` —
  trigger renders the "Views" placeholder when `views=[]`.

### Tests added in `frontend/src/__tests__/BoardToolbar.test.tsx` (+4)

A new `BoardToolbar — ViewPicker slot` suite. Existing 7 compact-toggle
tests unchanged.

- `renders ViewPicker when spaceId and onViewChange are both
  provided` — locks the toolbar's conditional render
  `{spaceId && onViewChange && <ViewPicker .../>}`.
- `does NOT render ViewPicker when onViewChange is omitted
  (unscoped board)` — regression guard: the `/board` (all-spaces)
  toolbar must hide the picker because there is no single space to
  load views for.
- `does NOT render ViewPicker when spaceId is null even if
  onViewChange is provided` — locks the second half of the
  conditional.
- `invokes onViewChange when a view is selected from the picker` —
  end-to-end interaction: open picker, click view, assert
  `onViewChange("focus")`.

### Tests added in `frontend/src/__tests__/BoardPage.test.tsx` (+9)

Two new suites — `view URL param routing` (6) and
`activeLaneStates propagation` (3). The page's `Board` and
`BoardToolbar` children are now mocked so we can assert on the props
they receive (the old test only inspected `compact`).

**`view URL param routing` (6 tests)**

- `passes viewId=null to Board when the URL has no ?view param
  (scoped space)`.
- `passes ?view=focus through to Board.viewId when the URL has it` —
  primes the views mock with a `focus` entry so the
  reset-on-deleted-view effect doesn't wipe the URL.
- `propagates the same viewId to BoardToolbar`.
- `passes onViewChange to BoardToolbar when the page is scoped to a
  space`.
- `does NOT pass onViewChange to BoardToolbar on the unscoped /board
  route` — locks the `scoped ? handleViewChange : undefined` branch.
- `invoking onViewChange from the toolbar pushes ?view= into the URL
  and propagates to Board + Toolbar` — full round-trip: click sim
  button → URL updates → both children re-render with `viewId="focus"`.

**`activeLaneStates propagation` (3 tests)**

- `passes undefined activeLaneStates when no views are loaded yet`.
- `propagates the active view's lanes to Board when views resolve` —
  `?view=focus` with `lanes: ["active","waiting"]` ⇒
  `activeLaneStates: ["active","waiting"]`.
- `falls back to the default view's lanes when ?view points to an
  unknown id` — defensive: bookmark to deleted view ⇒ user still
  sees the default view's lanes (never an empty board) until the
  reset effect clears the URL.

### Real bugs caught while writing these tests

1. The "renders star next to default" assertion initially compared the
   default row's svg count to the active row's svg count. Both happen
   to have exactly 1 svg (star vs check), so the assertion would pass
   for the wrong reason. Switched to compare against an inactive,
   non-default row (0 svgs) — now the test actually validates the
   star is present.
2. Three URL-driven tests initially used the default empty views mock,
   and BoardPage's "silently reset deleted view" useEffect immediately
   cleared `?view=focus`. The tests now mock views containing
   `focus` so the param survives. As a positive side-effect, the
   reset behavior itself is now covered by a dedicated test
   (`resets ?view to clean URL when the active view is missing`).

### Acceptance-criteria coverage matrix

| Acceptance criterion | Test |
|----------------------|------|
| Picker trigger shows the current view's name | `ViewPicker > renders the default view name…`, `renders the matching view name…` |
| Picker shows a star next to the default view | `ViewPicker > renders a star icon next to the default view…`, `renders a star icon in the trigger when the active view is the default` |
| Picker shows a check next to the active view | `ViewPicker > renders a check icon next to the active view…` |
| Clicking a view fires onChange | `ViewPicker > calls onChange with view.id when a non-default view item is clicked` |
| Selecting the default emits null (clean URL) | `ViewPicker > calls onChange with null when the default view item is clicked` |
| Manage views button fires onManageViews | `ViewPicker > calls onManageViews and closes the dropdown when 'Manage views…' is clicked` |
| Picker hidden on /board (unscoped) | `BoardToolbar > does NOT render ViewPicker when onViewChange is omitted`, `BoardPage > does NOT pass onViewChange to BoardToolbar on the unscoped /board route` |
| URL `?view=` drives Board.viewId | `BoardPage > passes ?view=focus through to Board.viewId when the URL has it` |
| Selecting a view in toolbar updates the URL | `BoardPage > invoking onViewChange from the toolbar pushes ?view= into the URL and propagates to Board + Toolbar` |
| Deleted view bookmark silently resets | `BoardPage > resets ?view to clean URL when the active view is missing`, `BoardPage > falls back to the default view's lanes when ?view points to an unknown id` |
| Active view's lanes drive visible columns | `BoardPage > propagates the active view's lanes to Board when views resolve` |

### Coverage delta this session

- Backend: untouched (79.32% — no backend changes in arc-3/3).
- Frontend test count: 332 → 364 (+32). No frontend coverage tooling
  is wired in (vitest config lacks `coverage:` block), so per-module
  pct deltas are not reported.

All 694 backend + 364 frontend tests pass; no regressions.



## Recent changes (2026-05-25 — arc-3/2: Views CRUD API + ?view board filter)

Added 41 tests in `backend/tests/test_api_views.py` covering the new
Views REST endpoints (`/api/spaces/{space_id}/views[/{view_id}]`) plus
the new `?view=<id>` / `?view=default` query parameter on
`GET /api/tasks`.

### Test infrastructure note

`SpaceStore.create()` writes `views: []` to disk; the default "all"
view is only materialized on YAML reload via `_normalize_views` inside
`parse_space_yaml`. The existing `space_store` fixture skips that
reload, so the new test file installs an autouse `_seed_views` fixture
that calls `space_store.reload_all()` after `async_client` has wired
`app.state`. This mirrors production startup state. A follow-up
hardening could move the seed into `SpaceStore.create()` itself to
remove this asymmetry; flagged but not addressed in this session.

### Tests added in `backend/tests/test_api_views.py` (+41)

**GET /api/spaces/{space_id}/views (2)**

- `test_list_views_returns_seeded_default_view` — lists exactly the
  one seeded `all` view with correct lanes and default=true.
- `test_list_views_unknown_space_returns_404`.

**POST /api/spaces/{space_id}/views (12)**

- `test_create_view_returns_201_with_view` — happy path, response
  carries id/name/lanes/type_filter/default + created_at/updated_at.
- `test_create_view_persists_and_visible_via_get` — GET sees the new
  view.
- `test_create_view_persists_to_space_yml` — `SpaceStore.reload_all()`
  after creation finds the view on disk.
- `test_create_view_auto_slugs_id_from_name` — `"My Cool View!!!"` →
  `"my-cool-view"`.
- `test_create_view_id_collision_appends_suffix` — second "Focus" view
  becomes `focus-1` (locks `_unique_view_id` contract).
- `test_create_view_with_type_filter` — type_filter round-trips.
- `test_create_view_default_true_clears_other_defaults` — seeded
  `all` view is demoted when a new default is created.
- `test_create_view_default_false_leaves_existing_default` — sanity
  guard.
- `test_create_view_unknown_space_returns_404`.
- `test_create_view_empty_lanes_returns_422`.
- `test_create_view_invalid_lane_returns_422` — `"bogus-state"`.
- `test_create_view_invalid_type_filter_returns_422` — `"nonsense"`.
- `test_create_view_empty_name_returns_422`.

**PATCH /api/spaces/{space_id}/views/{view_id} (10)**

- `test_patch_view_updates_name` — id and lanes untouched.
- `test_patch_view_updates_lanes`.
- `test_patch_view_sets_type_filter`.
- `test_patch_view_clear_type_filter_with_null` — explicit `null`
  clears the filter; locks the `clear_type_filter` branch via
  `model_fields_set`.
- `test_patch_view_default_true_clears_other_defaults_atomically` —
  after promoting one view, the OTHER two (incl. seeded `all`) are
  demoted; exactly ONE default remains.
- `test_patch_view_no_fields_returns_400` — empty body 400 with
  "No fields" message.
- `test_patch_view_unknown_space_returns_404`.
- `test_patch_view_unknown_view_returns_404`.
- `test_patch_view_empty_lanes_returns_422`.
- `test_patch_view_combined_fields_persist` — name + lanes + type_filter
  in one PATCH, verified via disk reload.

**DELETE /api/spaces/{space_id}/views/{view_id} (7)**

- `test_delete_view_success_returns_204` — body is empty bytes
  (asserts the 204 contract, not just status).
- `test_delete_view_last_view_returns_409` — locks "Cannot delete the
  last view" guard; the view remains present afterward.
- `test_delete_default_view_reassigns_default_alphabetically` — with
  `apple`, `all`, `zebra` present, deleting `all` promotes `apple`.
- `test_delete_non_default_view_leaves_default_untouched` —
  regression guard against accidental demotion.
- `test_delete_view_unknown_space_returns_404`.
- `test_delete_view_unknown_view_returns_404` — primed with a second
  view so the "last view" guard doesn't fire first.
- `test_delete_view_persists_to_space_yml` — disk-reload confirms.

**GET /api/tasks?view=... board filter (9)**

- `test_tasks_with_view_filters_lanes` — sanity check with no view
  first, then `view=<id>` (backlog-only) returns the other 3 lanes
  empty.
- `test_tasks_with_view_default_resolves_to_default_view` — promotes
  a `done`-only view to default; backlog task created afterward is
  hidden.
- `test_tasks_with_view_unknown_id_returns_404`.
- `test_tasks_with_view_without_space_id_returns_400` — locks
  "?view requires a specific space_id".
- `test_tasks_with_view_and_space_all_returns_400` —
  `?space_id=all&view=all` is also 400 (all-spaces == None scope).
- `test_tasks_with_view_applies_type_filter` — only goal-typed tasks
  appear when `type_filter=["goal"]`.
- `test_tasks_with_view_default_when_default_present_does_not_404` —
  the out-of-the-box `?view=default` works.
- `test_tasks_with_view_unknown_space_returns_404` — unknown-space
  check fires before view-resolution branch.
- `test_tasks_without_view_param_returns_full_board` — regression
  guard that omitting `?view` does not filter.

### Acceptance-criteria coverage matrix

| Acceptance criterion | Test |
|----------------------|------|
| GET returns seeded `all` view | `test_list_views_returns_seeded_default_view` |
| POST auto-slugs id, suffixes on collision | `test_create_view_auto_slugs_id_from_name`, `test_create_view_id_collision_appends_suffix` |
| POST default=true clears other defaults | `test_create_view_default_true_clears_other_defaults` |
| PATCH default=true clears other defaults atomically | `test_patch_view_default_true_clears_other_defaults_atomically` |
| PATCH 400 on empty body | `test_patch_view_no_fields_returns_400` |
| PATCH type_filter explicit null clears | `test_patch_view_clear_type_filter_with_null` |
| DELETE 409 on last view | `test_delete_view_last_view_returns_409` |
| DELETE default reassigns alphabetically | `test_delete_default_view_reassigns_default_alphabetically` |
| DELETE 204 on success | `test_delete_view_success_returns_204` |
| ?view filters lanes | `test_tasks_with_view_filters_lanes` |
| ?view=default resolves | `test_tasks_with_view_default_resolves_to_default_view` |
| ?view nonexistent → 404 | `test_tasks_with_view_unknown_id_returns_404` |
| ?view without space_id → 400 | `test_tasks_with_view_without_space_id_returns_400` |
| ?view applies type_filter | `test_tasks_with_view_applies_type_filter` |

### Coverage delta this session

- `app/api/views.py`: NEW, 93% (4 uncovered: 63-64, 102-103 are
  unreachable `SpaceError → 400` fallbacks in POST/PATCH — current
  `SpaceStore` view-mutators only raise `SpaceNotFound`/`ViewNotFound`,
  never bare `SpaceError`; left uncovered intentionally).
- `app/space_storage.py`: 61% → 72% (+11 pts) — new `create_view`,
  `update_view`, `delete_view`, `_unique_view_id` paths fully
  exercised by API tests.
- `app/api/tasks.py`: 69% → 70% (+1 pt) — `_apply_view_filter` and
  the three `?view` branches in `list_tasks` are covered.
- Overall backend: 78.86% → 79.31% (+0.45%).

All 694 backend tests + 332 frontend tests pass on first run; no
regressions.

## Recent changes (2026-05-25 — arc-4 task 1: Space.autopilot schema + yaml round-trip)

Added 28 tests covering the new `autopilot: Literal["disabled","enabled","paused"]`
field on `Space`, the new `SpaceStore.set_autopilot()` mutator, and the
`autopilot` branch of `PATCH /api/spaces/{id}`.

### Tests added in `backend/tests/test_space_storage.py` (+13)

**`dump_space` / `parse_space_yaml` (5 tests)**

- `test_dump_space_emits_autopilot_key` — the YAML serialization always
  carries the `autopilot:` key (default-disabled case).
- `test_dump_space_emits_current_autopilot_value` — emits `enabled` and
  `paused` literally when set on the model.
- `test_parse_space_yaml_missing_autopilot_defaults_disabled` — back-compat
  guard: a legacy `space.yml` without an `autopilot:` key loads with
  `'disabled'` instead of raising. Critical for upgrade safety — every
  existing space on disk pre-dates this field.
- `test_parse_space_yaml_reads_explicit_autopilot` — `autopilot: enabled`
  in the YAML round-trips into the Space model.
- `test_parse_space_yaml_invalid_autopilot_raises` — an unknown literal
  (`autopilot: bogus-mode`) raises `SpaceError` at parse time. Locks the
  Literal[...] contract so typos can't silently become autopilot-off.

**`SpaceStore.set_autopilot()` (8 tests)**

- `test_new_space_defaults_to_disabled_autopilot` — a freshly created space
  has `autopilot='disabled'` and the on-disk yml emits the key.
- `test_set_autopilot_persists_value[disabled|enabled|paused]` — three
  parametrized tests: mutation updates in-memory state AND persists to disk
  (verified via a fresh `SpaceStore.reload_all()` round-trip).
- `test_set_autopilot_paused_reloads_byte_equal` — the acceptance-criteria
  round-trip: save with `paused`, reload via a fresh store, confirm the
  field survives and the on-disk YAML contains the literal line.
- `test_set_autopilot_missing_space_raises` — unknown space id raises
  `SpaceNotFound`.
- `test_set_autopilot_updates_updated_at` — mutator bumps `updated_at` so
  watchers/UIs see the change.
- `test_set_autopilot_preserves_other_fields` — name/color/description are
  untouched by the autopilot mutation (regression guard against future
  refactors that might rebuild the model from a subset of fields).

### Tests added in `backend/tests/test_api_spaces.py` (+15)

**API surface — DTO carries the field (2 tests)**

- `test_get_space_response_includes_autopilot` — `GET /api/spaces/{id}`
  returns the field with the default `'disabled'`.
- `test_create_space_response_includes_autopilot` — `POST /api/spaces`
  response carries the field on a freshly created space.

**`PATCH /api/spaces/{id}` — autopilot round-trips (5 tests)**

- `test_update_space_autopilot_enabled_round_trips` — PATCH `enabled`
  returns 200, response carries the value, and a follow-up GET confirms
  persistence.
- `test_update_space_autopilot_paused_round_trips` — same for `paused`.
- `test_update_space_autopilot_back_to_disabled` — toggle enabled →
  disabled via two PATCHes.
- `test_update_space_autopilot_only_no_other_fields_succeeds` — locks the
  empty-body guard's new `and body.autopilot is None` branch: PATCH with
  ONLY `autopilot` must not 400 with "No fields to update".
- `test_update_space_autopilot_combined_with_name` — PATCH with `name` +
  `autopilot` together must apply BOTH (exercises both branches of the
  handler: base `store.update()` followed by `store.set_autopilot()`).

**`PATCH /api/spaces/{id}` — validation + error paths (7 tests)**

- `test_update_space_autopilot_invalid_value_returns_422` — bogus literal
  is rejected by Pydantic with 422 (not 200, not 400, not 500).
- `test_update_space_autopilot_bad_values_return_422[uppercase|alias-on|empty-string|whitespace-padded|wrong-word]` —
  five parametrized cases asserting that case-sensitive Literal matching
  catches plausibly-looking-but-wrong inputs (`ENABLED`, `on`, `""`,
  `"  enabled  "`, `active`). This is a security-relevant property: typos
  must NOT silently fall back to the default.
- `test_update_space_autopilot_missing_space_returns_404` — autopilot
  PATCH on an unknown space id returns 404, not 500.
- `test_update_space_autopilot_null_treated_as_omitted` — `{"name":"X",
  "autopilot":null}` updates the name but leaves an already-`enabled`
  autopilot untouched. Locks the `body.autopilot is not None` semantic
  in `update_space()` — `null` is the "omit" signal, not "reset to
  disabled".

### Acceptance-criteria coverage matrix

| Acceptance criterion | Test |
|----------------------|------|
| Existing `space.yml` without `autopilot:` loads with `"disabled"` | `test_parse_space_yaml_missing_autopilot_defaults_disabled` |
| After save, `autopilot` key is present in the YAML | `test_dump_space_emits_autopilot_key`, `test_new_space_defaults_to_disabled_autopilot` |
| `PATCH {"autopilot":"enabled"}` round-trips correctly | `test_update_space_autopilot_enabled_round_trips` |
| Invalid `autopilot` value → 422 | `test_update_space_autopilot_invalid_value_returns_422` + 5 parametrized cases |
| `autopilot: paused` reloads byte-equal | `test_set_autopilot_paused_reloads_byte_equal`, `test_set_autopilot_persists_value[paused]`, `test_update_space_autopilot_paused_round_trips` |

### Coverage delta this session

- `app/space_storage.py`: 59% → 61% (+2 pts) — the new `set_autopilot()`
  branch is fully exercised; remaining gap is in link_repo/unlink_repo
  paths that require real git fixtures.
- `app/api/spaces.py`: 90% → 91% (+1 pt) — the new autopilot branches in
  `update_space()` are covered.
- `app/models.py`: 100% → 100% — unchanged (the new Literal field has no
  runtime branches).

All 627 backend tests pass on first run; no regressions.

## Per-module coverage (backend, sorted ascending)

| Module | Coverage | Δ vs previous |
|--------|----------|---------------|
| app/main.py | 30% | +0 |
| app/git_ops.py | 58% | +0 (slow climb — was 21% three sessions ago) |
| app/api/test_reports.py | 70% | +0 |
| app/space_storage.py | 72% | +0 |
| app/api/tasks.py | 72% | +2 (arc-9/3 _enrich_progress) |
| app/goal_sync.py | 72% | new in table |
| app/worker.py | 73% | +1 |
| app/worker_pool.py | 77% | -3 (worker_pool tests not run this session?) |
| app/agent.py | 83% | +0 |
| app/test_report_store.py | 83% | +0 |
| app/trace_store.py | 84% | +0 |
| app/stats_store.py | 85% | +0 |
| app/storage.py | 88% | +0 |
| app/file_service.py | 90% | +0 |
| app/api/spaces.py | 91% | +0 |
| app/trace_parser.py | 91% | +0 |
| app/api/traces.py | 92% | +0 |
| app/api/views.py | 93% | +0 |
| app/api/tools.py | 96% | +0 |
| app/api/stats.py | 97% | +0 |
| app/stats.py | 98% | +0 |
| app/api/__init__.py | 100% | +0 |
| app/api/activity.py | 100% | +0 |
| app/autopilot.py | 100% | +0 |
| app/autopilot_pr.py | 100% | +0 |
| app/models.py | 100% | +0 |
| app/test_report.py | 100% | +0 |

### Modules that lost coverage this run

- `app/worker.py`: 75% → 72% (-3 pts). Likely cause: new statements
  added on a worker change that landed between sessions but were not
  covered. Investigate next session (likely outside arc-3 scope).

## Lowest-coverage modules (priority queue for next session)

| Module | Coverage | Missing line ranges (top) | Notes |
|--------|----------|--------------------------|-------|
| app/git_ops.py | 21% | 31,36,50-65,74-77,100-113,121-126,136-183,... | user git state — security-sensitive |
| app/main.py | 29% | 41-45,53-63,71-88,100-120,125-201,221-247 | lifespan/watcher uncovered |
| app/space_storage.py | 59% | 52-56,67-76,86,101-102,149-150,156-160,169-170,176-177,180-182,185-194,198-199,203-231,263-266,270,275-278,286-296,369-399,409-426,452,455 | space lifecycle ops |
| app/api/tasks.py | 61% | 56,59,117,170-181,186-187,217-220,255-256,273-274,306-311,313,321-342,347-348,360,365-376,386-399,409-423,433-453,476-479,486-487 | file upload/stop branches; PATCH not-found |
| app/api/test_reports.py | 70% | 15,20,69-74,79-87 | small module — easy wins |

## Recent changes (2026-05-24 — arc-1 task 3 gap-fill on DTO endpoints)

Added 9 more tests targeting the `_build_task_read(..., store=...)` wiring
across every TaskRead-returning endpoint. The arc-1/3 commit added a new
`store` parameter that several call sites pass; if any of those threadings
regressed, the DTO would silently report `unmet_dependencies=[]` even when
blockers existed.

### Tests added in `backend/tests/test_api_tasks.py` (+5)

- `test_start_response_includes_unmet_dependencies` — POST /start success
  response carries the field (empty list on success).
- `test_patch_state_response_includes_unmet_dependencies` — PATCH /state
  carries the field (open backlog -> active path, deps satisfied).
- `test_patch_task_response_includes_unmet_dependencies` — PATCH /api/tasks/{id}
  carries the field; populated when adding an open dep via the update.
- `test_reply_response_includes_unmet_dependencies` — POST /reply carries the
  field on the active reply path (regression guard for the new `store=` arg).

### Tests added in `backend/tests/test_storage.py` (+5)

- `test_apply_reply_waiting_path_unaffected_by_dep_gate` — waiting->active
  reply with open deps must succeed (gate is BACKLOG-only). Locks the gate's
  exact-match scoping.
- `test_apply_reply_done_path_unaffected_by_dep_gate` — done->active reply
  with open deps must succeed. Same scoping argument.
- `test_unmet_deps_does_not_treat_self_as_satisfied` — self-referential dep
  (data-corruption scenario; create() blocks it) still reports as unmet
  because the task itself is BACKLOG (non-terminal). Lock policy.
- `test_unmet_deps_returns_independent_list` — caller mutation does not
  poison subsequent calls (defensive against shared-list bugs).
- `test_open_children_returns_independent_list` — same independence
  contract for the sibling helper.

## Recent changes (2026-05-24 — arc-1/6 detail panel hierarchy UI)

Task arc-1/6 added a new HierarchySection inside `Detail.tsx` plus three new
API methods (`promote`, `setParent`, `setDependsOn`) and three new hooks
(`usePromoteTask`, `useSetParent`, `useSetDependsOn`). Added 68 new frontend
tests across four files plus four new exports from `Detail.tsx` so the pure
helpers can be unit-tested.

### Tests added in `frontend/src/__tests__/Detail-helpers.test.ts` (17)

Pure tests for the two new helpers:

- `extractDetail` — 8 tests covering: pure-JSON body, JSON-with-prefix,
  no-brace passthrough, malformed JSON passthrough, missing-detail field,
  empty-string falsy fallback, non-string-detail runtime behavior, and a
  brace-in-path placement check.
- `getDescendantIds` — 9 tests covering: no children, immediate children,
  multi-level traversal, root-id exclusion, sibling-tree isolation, **cyclic
  parent-graph defensive termination**, missing root, empty task list, and
  sibling-vs-descendant distinction.

### Tests added in `frontend/src/__tests__/api-hierarchy.test.ts` (15)

Mocks `globalThis.fetch` and asserts URL, method, body, headers, and error
propagation for each new method. The error-propagation tests are the
important ones — they lock the wrapper's "<status> <statusText> on <path>:
<body>" error-message format that `extractDetail` parses.

### Tests added in `frontend/src/hooks/__tests__/useTasks-hierarchy.test.tsx` (13)

Uses a real `QueryClient` with retries disabled and `vi.mock`s `../../api`.
Asserts: argument forwarding, cache writes via `setQueryData(["task", id])`,
board cache invalidation (verified by extracting and invoking the
`predicate` function passed to `invalidateQueries`), error surfacing, and
the "cache untouched on error" contract for `useSetDependsOn`.

### Tests added in `frontend/src/components/__tests__/HierarchySection.test.tsx` (23)

Mocks `useBoard`, `usePromoteTask`, `useSetParent`, `useSetDependsOn` so the
test controls hook state directly. Wraps in `MemoryRouter` for the
`useSearchParams` dependency. Covers:

- TypeBadge rendering for all three types and the `undefined → 'task'` default.
- Promote button visibility: hidden for goals, visible for task/issue/undefined.
- Promote button: disabled + "Promoting…" while pending; calls mutateAsync on
  click; surfaces extracted detail on error.
- Children section: hidden for non-goals, hidden for goals without children,
  visible for goals with children; lists each child with state badge; hidden
  while board data is loading.
- Top-level structure: Hierarchy heading, Parent / Depends on labels,
  dependency chips that resolve titles from the board (with id fallback), and
  the parent breadcrumb with Change/Remove buttons.

### Source change: 4 named exports added to `frontend/src/components/Detail.tsx`

`extractDetail`, `getDescendantIds`, `TypeBadge`, `HierarchySection` are now
named exports so the helpers and the section can be unit-tested in isolation
without exercising the full Detail modal. No behavior change.

All 599 backend tests + 183 frontend tests pass; no regressions.

All 535 backend tests pass; no regressions.

## Recent changes (2026-05-24 — arc-1 task 3: block backlog->active when deps unmet)

Added 41 tests covering the new dependency / child gates implemented on the
arc-1/3 branch (`backend/app/storage.py` + `backend/app/api/tasks.py`):

- `_TERMINAL_STATES = {done, archived}`
- `unmet_deps(task, by_id) -> list[str]`
- `open_children(goal_id, by_id) -> list[str]`
- `TaskStore.transition()` gates: backlog→active blocked by unmet deps,
  goal→done blocked by open children.
- `TaskStore.apply_reply()` gate: backlog→active blocked by unmet deps.
- `POST /api/tasks/{id}/start` returns 409 with the blockers' ids in
  `detail` when deps are open.
- `TaskRead.unmet_dependencies: list[str]` surfaced on every task DTO
  (GET, POST, PATCH, /start, /reply responses).

## Recent changes (2026-05-24 — arc-1 task 3: block backlog->active when deps unmet)

Added 41 tests covering the new dependency / child gates implemented on the
arc-1/3 branch (`backend/app/storage.py` + `backend/app/api/tasks.py`):

- `_TERMINAL_STATES = {done, archived}`
- `unmet_deps(task, by_id) -> list[str]`
- `open_children(goal_id, by_id) -> list[str]`
- `TaskStore.transition()` gates: backlog→active blocked by unmet deps,
  goal→done blocked by open children.
- `TaskStore.apply_reply()` gate: backlog→active blocked by unmet deps.
- `POST /api/tasks/{id}/start` returns 409 with the blockers' ids in
  `detail` when deps are open.
- `TaskRead.unmet_dependencies: list[str]` surfaced on every task DTO
  (GET, POST, PATCH, /start, /reply responses).

### Tests added in `backend/tests/test_storage.py` (+22)

**Pure predicates — `unmet_deps()` (9 tests)**

- No-deps task returns `[]`.
- All-`done` deps return `[]`.
- All-`archived` deps return `[]`.
- Mixed `done` + `archived` returns `[]`.
- Mixed terminal/non-terminal returns the non-terminal ids in
  `depends_on` order.
- Missing dep id (dangling reference) is reported as unmet — defensive
  against silent skips when a target task was deleted.
- `waiting` state is NOT terminal (locks in the `{done, archived}`
  contract).
- `active` state is NOT terminal.
- Result list preserves `depends_on` order (deterministic for the UI).

**Pure predicates — `open_children()` (6 tests)**

- No children returns `[]`.
- All `done` children return `[]`.
- All `archived` children return `[]`.
- Mix of states reports the three non-terminal states (backlog/active/
  waiting) and excludes the terminal ones.
- A child of a DIFFERENT goal must not appear (off-by-one guard against
  forgetting to filter by `parent_id`).
- Root-level tasks (`parent_id=None`) are never attributed to any goal.

**`TaskStore.transition()` gates (5 tests)**

- backlog→active raises `InvalidTransition` when any dep is open;
  message names the offending id; the task's stored state is
  unchanged (gate enforced before mutation).
- backlog→active succeeds once every dep reaches `done`.
- backlog→active succeeds when every dep reaches `archived`.
- Multi-dep error message lists every open blocker.
- goal→done (via WORKER_TRANSITIONS active→done) raises
  `InvalidTransition` when any child is open; message names the child
  id; the goal's stored state is unchanged.
- goal→done succeeds once every child reaches `done`.
- Gate is scoped to `type='goal'` — `type='task'` parents with open
  children are NOT blocked from being closed.
- Illegality of the transition itself is checked BEFORE the deps gate
  (BACKLOG→DONE under USER_TRANSITIONS surfaces "Cannot move task from
  backlog to done", not the deps error).

**`TaskStore.apply_reply()` gate (3 tests)**

- Reply to a backlog task with unmet deps raises `InvalidTransition`
  and does NOT mutate the task (no history entry, state stays
  `backlog`).
- Reply to a backlog task with all deps `done` promotes to `active`
  and returns `should_enqueue=True`.
- Reply to an ACTIVE task with open deps is NOT blocked — the gate is
  scoped to the backlog branch; active replies still queue
  pending_messages.

### Tests added in `backend/tests/test_api_tasks.py` (+19)

**`POST /api/tasks/{id}/start` (6 tests)**

- 409 when a dep is open; `detail` contains "unmet dependencies" and
  the dep id; task remains in `backlog` after the refused start.
- 200 once every dep reaches `done`; final state is `active`.
- 200 happy path for a task with no deps.
- 200 when the dep is in `archived` state.
- 404 for an unknown task id.
- 409 when the task is already in `active` (lock-in for the "only
  backlog tasks can be started" guard).

**`PATCH /api/tasks/{id}/state` for goal-done (3 tests)**

- 409 on a goal with open children; `detail` contains "open children"
  and the child id; goal's stored state unchanged.
- 200 once every child reaches `done` (goal transitions waiting→done).
- 200 on a `type='task'` parent with open children — gate must NOT
  fire for non-goal types.

(Note: the goal-done flow goes through `waiting→done` because
`USER_TRANSITIONS` doesn't allow `active→done`. Setup primes the goal
into `waiting` via direct store manipulation to reach the user-facing
endpoint.)

**`TaskRead.unmet_dependencies` field (5 tests)**

- `[]` when the task has no deps.
- Populated with every open dep id when deps exist (set equality so
  order isn't asserted at the API boundary).
- Shrinks to `[]` once deps move to `done`.
- Reports a dangling dep id (target never existed) — surface the
  storage-layer defensive contract through the DTO.
- POST /api/tasks response also carries `unmet_dependencies` (the
  TaskRead shape is used on every endpoint that returns a task).

All 526 backend tests pass; all 88 frontend tests pass; no regressions.

## Recent changes (2026-05-24 — arc-1 task 1: type/parent_id/depends_on)

Added 30 tests covering the new hierarchy fields on `Task` (`type`,
`parent_id`, `depends_on`) and the SQLite secondary index that maintains
them.

### Real bug caught by these tests

`TaskStore.delete()` did NOT call `_db_delete()`, so soft-deleted tasks
remained as dangling rows in the SQLite tasks index. This would have leaked
into any future parent_id / type query built on top of the index. Test
`test_sqlite_index_removes_row_on_delete` failed on the first run; one-line
fix added `self._db_delete(task_id)` to the delete path in
`backend/app/storage.py`.

### Tests added in `backend/tests/test_storage.py` (+20)

- **parse_file** — reads `type`/`parent_id`/`depends_on` from frontmatter;
  back-compat defaults when keys are missing; invalid `type` falls back to
  `"task"`; non-list `depends_on` falls back to `[]`.
- **dump_task** — emits the three new keys; full disk round-trip
  (`dump_task` -> file -> `parse_file`) preserves all three.
- **summarize** — `TaskSummary` exposes `type` and `parent_id` (depends_on
  is intentionally NOT on the summary); defaults to `"task"` / `None`.
- **TaskStore.create** — accepts and persists hierarchy fields; defaults
  when omitted; rejects unknown `type` with `StorageError`.
- **TaskStore.update** — persists new values; `depends_on=[]` clears the
  list (vs `None`=no-op); rejects unknown `type`.
- **SQLite index**:
  - `reload_all()` rebuilds the table from MD files with correct
    `type`/`parent_id`/`depends_on_json`.
  - `create` upserts a row.
  - `update` upserts the new values.
  - `delete` removes the row (caught the bug above).
  - `idx_tasks_space_parent` and `idx_tasks_space_type` indices exist.
  - End-to-end query by `(space_id, parent_id)` and `(space_id, type)`
    returns the expected set.

### Tests added in `backend/tests/test_api_tasks.py` (+10)

- `POST /api/tasks` with hierarchy fields echoes them in the response.
- `POST /api/tasks` defaults: `type="task"`, `parent_id=None`,
  `depends_on=[]`.
- `POST /api/tasks` rejects unknown `type` with 422 (Pydantic Literal).
- `PATCH /api/tasks/{id}` updates type/parent_id/depends_on together.
- `PATCH /api/tasks/{id}` with only `type` (or only `depends_on`)
  succeeds — exercises the "no fields provided" guard.
- `GET /api/tasks/{id}` round-trips the three fields through the read
  model.
- Board summaries expose `type` and `parent_id` for card rendering.
- `PATCH` with invalid type returns 422.

All 462 backend tests pass; all 88 frontend tests pass; no regressions.

## Recent changes (2026-05-20 — HIGH-005 imported-task sanitization)

Added 4 tests covering the new `_sanitize_imported_tasks()` security fix in
`backend/app/api/spaces.py`. The function is invoked just before an imported
space directory is moved into place; it forces every task to
`state=backlog` with `claude_session_id=None`, clearing `pending_messages`
and `waiting_question`. This blocks an attacker from importing a ZIP that
auto-starts a hijacked Claude session on the operator's machine.

New tests in `backend/tests/test_spaces_api.py`:

- `test_import_active_task_is_forced_to_backlog` — ZIP carrying
  `state: active` arrives on disk as `state: backlog`.
- `test_import_task_with_session_id_is_stripped` — even a clean
  backlog task arrives with `claude_session_id` cleared when the ZIP
  set one.
- `test_import_clean_backlog_task_is_unchanged` — backlog task with
  no session id round-trips unchanged and emits zero
  "Sanitizing imported task" warnings (asserted via `caplog`).
- `test_import_waiting_task_with_question_and_pending_is_sanitized` —
  full payload (`state: waiting` + session id + pending messages +
  waiting question) is normalized: state→backlog, session→None,
  pending→[], waiting_question→None.

Each test reads the post-import file from disk via `parse_file()` to
verify the persisted state (not just the API response). All 4 pass on
first run; full backend (423) and frontend (88) suites green; no
regressions.

## Recent changes (2026-05-19 — file_service coverage pass)

Added 25 tests covering `app/file_service.py`, which was the lowest-covered
backend module at 19%. Coverage of that module is now 90% (+71 pts) and
overall backend+frontend coverage moved from 70.42% to 73.41% (+2.99 pts).

New test file: `backend/tests/test_file_service.py` (25 tests):

- **`classify_file` (6 tests)** — image/text/code/document/archive/binary
  extension mapping; AI prefix rules (`.claude/agents/`, `.claude/skills/`,
  `.claude/commands/`, `.claude/context/`, exact `.claude/CONTEXT.md`)
  taking priority over extension; backslash normalisation.
- **`resolve_safe` (4 tests)** — simple in-root resolution; leading-slash
  and backslash normalisation; traversal attempts via `../` raise
  `ValueError`; empty path resolves to root.
- **`list_files` (7 tests)** — basic tree walk with sizes, categories,
  is_dir flags; hidden files skipped outside `.claude/`; `.claude/` dir
  itself stays hidden by the walker; `skip_prefixes` excludes named dirs
  (e.g. `.cronos`); `max_entries` bound respected; directory-before-file
  sort order; entries are `FileEntry` instances.
- **`list_git_changed_files` (2 tests)** — returns `None` when path is
  not a git repo; in a real repo correctly reports modified + untracked
  files while excluding deleted ones and sorts results by path.
- **`save_upload` (6 tests)** — round-trip write returns a populated
  `FileEntry` and cleans up the `.tmp` file; filename basename is taken
  so path components in `upload.filename` cannot escape the target dir;
  traversal in the `rel_subdir` argument raises `ValueError`; oversized
  uploads raise `ValueError` and leave no partial/temp file behind;
  intermediate target directories are created; missing filename falls
  back to literal `"upload"`.

All 25 tests pass on first run; no regressions introduced in the rest of
the suite (backend 419 passed, frontend 88 passed).

## Recent changes (2026-05-19 — agent identification in history)

Added 28 tests covering the new subagent-types-in-history feature
(commit context: `_extract_subagent_types` + `agents=` header field):

- **test_worker.py** (+20 tests):
  - 13 tests covering `_extract_subagent_types(events)` directly:
    empty input; no Agent calls; single call lowercased; dedup
    across mixed case; insertion-order preservation; missing/non-
    string/empty `subagent_type`; non-assistant events ignored;
    other tool names ignored; malformed event shapes tolerated.
  - 3 tests covering `_finalize()` history-entry serialization
    of the new `agents=` field: appended when subagents used;
    omitted when not; dedup+lowercase in header CSV.
- **parse-history.test.ts** (+8 tests):
  - `agents=` parsing into `AgentInfo.agents` (single, multi, missing,
    empty, key-order independence, full multi-entry round-trip,
    empty-token filter).

Worker module coverage moved from 14.3% → 57.7% (+43 pts) because
`_finalize()` now executes via these tests with realistic event
fixtures. All tests pass on first run; no regressions.

## Recent changes (2026-05-19 — tasks mode visualization)

Added 8 tests covering the `agent_mode` propagation from Task to TaskSummary
(the data path that lets the frontend render mode badges on board cards):
- **test_storage.py** (+6 tests) — `summarize()` direct unit tests for
  `agent_mode` defaulting and propagation (`auto`, `plan`, `ask`), plus a
  preserves-other-fields check, plus `task_store.board()` integration tests
  for default-mode and non-default-mode tasks.
- **test_api_tasks.py** (+2 tests) — `GET /api/tasks` board responses now
  verified to include `agent_mode` on each summary (both default `"auto"`
  and explicitly-set `"plan"`).

Frontend `Card.test.tsx` (+5 tests, by feature author) covers the badge
rendering matrix: Auto shown only in full mode; Plan and Ask shown in both
full and compact modes.

All tests pass on first run; no regressions introduced.

## Recent changes (2026-05-18 second pass)

Added 27 tests covering the worker/agent fixes in commit `cbf5fa4`:

- **test_worker.py** (NEW, 19 tests) — `Worker._finalize()` state resolution
  for false-CRASHED scenarios; verifies that successful runs are not
  misclassified as crashes when STATUS markers are present.
- **test_agent.py** (+8 tests) — STATUS marker parsing for both modern
  and legacy formats; trims whitespace and handles missing markers.
