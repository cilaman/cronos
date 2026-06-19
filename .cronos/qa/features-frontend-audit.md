# Features Frontend UX & Wiring Audit

Date: 2026-06-07
Audit scope: frontend implementation of the Features & Fixes feature
Reference patterns audited against: `Board.tsx`, `BoardPage.tsx`, `useTasks.ts`,
`Detail.tsx`, `HarnessListPage.tsx`, `ArchivedPage.tsx`.

---

## Critical Gaps (functionality completely missing)

These are backend capabilities that have **no UI affordance at all** —
the corresponding endpoints exist and are working, but no user can reach
them from the browser.

### CG-1. Feature cards are not clickable (no detail view exists)
`frontend/src/components/FeaturesBoard.tsx:207` passes `onOpen={() => {}}` to
the `Lane`, and `frontend/src/components/FeaturesBoard.tsx:220` passes
`onClick={() => {}}` to the drag-overlay `Card`. Both are no-ops.

The Tasks board (`Board.tsx:268`) passes `onOpen={setOpenId}` which writes the
clicked task id into the URL search params and then renders `<Detail
taskId={openId} onClose={...} />` (`Board.tsx:318`).

Consequence: a user cannot read a feature's brief, see GitHub issue context,
edit the title/description, see realizing goals, see `waiting_question`, or
invoke `Process`. The board is read-only-by-accident — every card is a dead
control.

**Compare:** `Board.tsx:55-322` (entire detail-panel lifecycle).
**Recommendation:** introduce a `FeatureDetail` (or extend `Detail.tsx`) that
mounts when `?feature=<id>` is in the URL. Wire `onOpen` on the Features
board to write that param. Render it as the right-rail drawer/modal that
exists for tasks.

### CG-2. No `getFeature` API client method
`frontend/src/api.ts:402-423` exposes only:

- `features(spaceId)` → GET list
- `transitionFeatureState(taskId, state)` → PATCH state
- `createFeature(spaceId, body)` → POST create

`GET /api/features/{id}` (returns `FeatureRead` with `realizing_items`) is
implemented in `backend/app/api/features.py:180-196` but has **no client
wrapper**. There is no way to fetch a single feature with its realizing
items from anywhere in the frontend.

**Recommendation:** add `getFeature: (id: string) => request<FeatureRead>(...)`.

### CG-3. No `patchFeature` API client method
`PATCH /api/features/{id}` (edit title/brief) is implemented in
`backend/app/api/features.py:242-280` but has **no client wrapper**. Editing
a feature's title or description is impossible from the UI.

**Recommendation:** add `patchFeature: (id, {title?, brief?}) => ...`.

### CG-4. No `processFeature` API client method, no Process button
`POST /api/features/{id}/process` is implemented in
`backend/app/api/features.py:330-368`. It transitions the feature to
PROCESSING and enqueues the automated decomposition into a realizing goal —
the **core value-add of the Features arc**.

There is **no `processFeature` client method** in `api.ts`, **no
`useProcessFeature` hook** in `useFeatures.ts`, and **no UI button**
anywhere that calls it. The only way a feature can reach PROCESSING is by
the user dragging the card into the Processing lane (which is a legal
transition but does not surface the relationship to the "kick off
decomposition" semantics, and does not call the `/process` endpoint).

This is a major UX miss: dragging into Processing fires `PATCH
/feature-state` which is a pure state change; it does not enqueue
decomposition. Drag-to-Processing and `POST /process` are **silently
different code paths**.

**Recommendation:** add a "Process" button on the feature detail panel that
calls `POST /api/features/{id}/process`. Consider also intercepting the
drag-to-Processing transition to use the `/process` endpoint instead of
plain `/feature-state` so that the user expectation ("moving to Processing
should start work") matches behaviour.

### CG-5. No `setRealize` API client method, no realize-link UI
`PATCH /api/features/{featureId}/realize` (body
`{item_id, feature_id|null}`) is implemented in
`backend/app/api/features.py:283-327`. It is the only way to set
`task.realizes` from outside an agent run.

There is **no `setRealize` client method**, **no `useSetRealize` hook**, and
**no UI** anywhere that lets a user link or unlink a task/goal to a feature.
The `Card` does render the `realizes` link **read-only** (Card.tsx:542-560)
and the inverse `realized_by` list (Card.tsx:562-585), but neither is
editable.

Combined with CG-2, this means the **realizing_items array can never be
displayed** (no GET endpoint wired) and **can never be edited** (no PATCH
endpoint wired). The realize relationship is functionally invisible.

**Recommendation:** when the FeatureDetail panel is built (CG-1), include a
"Realizing goals" section that lists `realizing_items`, with a "Link a
task…" affordance that opens a task picker and calls `setRealize`.

### CG-6. No `useFeature` / `usePatchFeature` / `useProcessFeature` / `useSetRealize` hooks
`frontend/src/hooks/useFeatures.ts` exposes only `useFeatureBoard`,
`useTransitionFeatureState`, `useCreateFeature`. All four query/mutation
hooks the detail flow would need are missing — a downstream symptom of
CG-2/3/4/5.

**Recommendation:** add the four hooks alongside the existing three, all
using the established `invalidateFeatureQueries(qc, spaceId)` triple-key
invalidation helper.

---

## UX Divergencies (inconsistent with Cronos patterns)

### UX-1. Issue link tooltip says "Open issue" even when it's a GitHub issue (no GitHub-flavoured affordance)
`Card.tsx:503-514` renders an anchor with `IconFileText` and
`title="Open issue"`. The same `IconFileText` is reused for the
proposed-PR path (Card.tsx:490-502). Visually the GitHub issue link is
indistinguishable from the proposed-PR document icon. There is no
GitHub mark, no issue number, and no visible label.

A user reading the card cannot tell at a glance whether the icon is a
GitHub issue, a local proposed PR file, or "some kind of document".

**Characterised as:** unintended inconsistency. The arc explicitly mirrors
features to GitHub Issues, but the card UI hides that.

**Compare:** the PR link uses `IconGitPR` (Card.tsx:478-489) which is
clearly a Git/GitHub icon — the issue link should follow that pattern.

**Recommendation:** add an `IconGitIssue` (the GitHub issue circle/dot
icon). Optionally also render the issue_number ("#42") next to the link
when present.

### UX-2. `realized_by` displays raw task IDs, not titles
`Card.tsx:562-585` iterates `task.realized_by` and renders
`← {itemId}` — a UUID-looking string the user has no context for. There
is no title, no state, no count. The Tasks board shows linked items
(parent, depends_on) with their titles or at least summaries.

**Characterised as:** unintended inconsistency. `TaskSummary.depends_on` is
a `string[]` but `unmet_dependencies` is `Array<{id, title}>`. The same
pattern (resolve IDs to title summaries server-side) is the established
fix, but `realized_by` was added as raw IDs.

**Recommendation:** mirror the `unmet_dependencies` shape — either change
the board endpoint to return `realized_by_summaries: Array<{id, title}>`
or eagerly fetch titles client-side via a lookup. At minimum, count them
("3 goals") instead of dumping IDs.

### UX-3. `realizing_items` count is not visible on the feature card
The Tasks board card shows `children_progress` ("done / total" plus a
progress bar) for goals (Card.tsx:588-607). The Features card does not
display the inverse: how many tasks/goals realize this feature. The
backend's `realizing_items` is only queryable via the (un-wired) GET
endpoint, so even when CG-2 is fixed, the board card would still hide it.

**Characterised as:** unintended inconsistency with the goal-progress
pattern on the Tasks board.

**Recommendation:** include a `realized_by_count` (or precomputed
done/total like goals) on `TaskSummary` for feature rows, and render it on
the card the same way as goal progress.

### UX-4. `waiting_question` rendered, but only outside compact mode
`Card.tsx:613-618` renders the amber Q-box only when `!compact`. The
Features board does not pass `compact`, so it's always full-density,
which is fine. But: there is no test fixture covering this for
type=feature/fix, and the AttributeError-known-finding from the goal
memory means features may never actually populate `waiting_question`
yet. So the field is *displayed* but *cannot* be written. Verification
in QA is impossible until the backend bug is fixed.

**Characterised as:** intentional (UI is correct), but **blocked by a
backend defect** documented in the goal context.

### UX-5. Drag-and-drop intentionally drops within-lane reorder
`Board.tsx:163-180` supports two drag outcomes: lane change OR within-lane
reorder (calls `useReorderTasks`). `FeaturesBoard.tsx:162-171` only
supports lane change — drops onto another card or onto the same lane are
silently ignored.

**Characterised as:** possibly intentional (features don't currently
expose a `manual_order` mutation endpoint), but should be confirmed.
The backend `features_router` has no `/reorder` endpoint, so the UX is
consistent with the contract. However, the discoverability is poor: the
user sees a drag handle, expects to be able to reorder, and is silently
denied.

**Recommendation:** either (a) hide the drag affordance for cards inside
the same lane (no-op feedback) or (b) add a feature-reorder endpoint.
Lowest-cost fix: do nothing but document this as expected behaviour.

### UX-6. SortableContext is wrapped twice per lane
`FeaturesBoard.tsx:202-211` wraps each `Lane` in a `SortableContext`. But
`Lane.tsx:97-115` already wraps its content in a `SortableContext`. The
outer wrapper is redundant — both reference the same `taskIds`. dnd-kit
silently tolerates this, but it's dead code and a small footgun (if the
inner one were ever removed, the outer would mask the regression).

**Characterised as:** unintended inconsistency / dead code.

**Recommendation:** drop the outer `SortableContext` wrapper in
`FeaturesBoard.tsx`.

### UX-7. Shared Features Backlog on Tasks board navigates instead of opening detail
`Board.tsx:304-313` renders cards in the shared "Features Backlog"
section with `onClick={() => navigate("/features")}` and
`onOpenTask={() => navigate("/features")}`. Clicking a card takes the
user to the Features page **without selecting that specific feature** —
they land on the global Features view and must hunt for the card they
just clicked.

**Characterised as:** unintended inconsistency. The Tasks board's own
cards open the detail panel in place; the Features Backlog cards do not.

**Recommendation:** once CG-1 (feature detail panel) ships, change these
clicks to `navigate('/features?feature=' + task.id)` (or whatever URL
convention the detail picks). Until then, at minimum link to
`/spaces/${task.space_id}/features` so the user lands in the correct
space view.

### UX-8. Loading state is a single-line text only; no skeleton, no spinner
`FeaturesBoard.tsx:178-180` returns `<p>Loading features…</p>`. Other
pages use either a spinner (`HarnessListPage.tsx:217-220`,
`FeaturesPage.tsx:88-91`) or a skeleton (e.g. `ToolDetailPanel`). The
Tasks board uses the same simple `<p>` (`Board.tsx:206`), so this is
**consistent with `Board.tsx`** but inconsistent with the newer Harness
pages.

**Characterised as:** intentional (matches Tasks board pattern). Not a
defect.

### UX-9. Error state shows raw `error.message`; no 404 silencing like Tasks board
`Board.tsx:208-210` deliberately silences 404 errors:
`if (error && !error.message.startsWith("404 ")) { ... }`.
`FeaturesBoard.tsx:181-183` does not — any 404 (e.g. space deleted while
viewing) shows `Error: 404 ...` directly to the user.

**Characterised as:** unintended inconsistency.

**Recommendation:** mirror the Tasks board's 404 guard.

### UX-10. FeaturesPage space selector pattern differs from HarnessListPage but matches ArchivedPage
`FeaturesPage` supports both global (`/features`) and scoped
(`/spaces/:spaceId/features`) routes, with `SpaceFilterDropdown` for the
global variant and localStorage persistence. `HarnessListPage` is
scoped-only (requires `:spaceId` in URL). `ArchivedPage` matches the
FeaturesPage pattern.

**Characterised as:** intentional. The two-route pattern is established
for cross-cutting boards (Tasks, Archived, Features). HarnessListPage's
scoped-only pattern is for resources whose names are space-local.

### UX-11. Process / state-change drag has no visual confirmation
When a feature card is dragged to a new lane, the only feedback is the
optimistic React Query refetch ~5 s later. There is no toast, no spinner
on the card, no inline "Saving…" hint. If the transition fails (R-409),
the failure is **silently swallowed** — the card snaps back to its
original lane on next refetch with no indication of why.

**Characterised as:** unintended inconsistency (same applies to Tasks
board, so this is a system-wide gap — but it's more visible on the
Features board because the legal transition graph is sparser and users
will hit "Cannot move planned → backlog" type errors).

**Recommendation:** surface mutation errors via a toast. Optionally show
"Saving…" with optimistic update + rollback.

---

## Missing Polish / Nice-to-Have

### NP-1. FeatureComposer offers no GitHub error context
`FeaturesBoard.tsx:42-125` lets the user type a title and click Add. If
the space isn't linked to a git repo, the backend returns
HTTP 400 with `"Space is not linked to a git repository"`
(`backend/app/api/features.py:124-128`). The composer does not display
this error — `useCreateFeature` doesn't expose the error to the form, so
the user clicks Add, nothing visible happens, and they wonder why.

**Recommendation:** render `createFeature.error` inline below the form
with a remediation hint (link to space settings → "Link a GitHub repo").

### NP-2. No feature ↔ goal link affordance on the goal card
The Tasks board shows `realizes` as a small "→ realizes {id}" link on
the goal card (Card.tsx:542-560), but the destination ID is a raw uuid
with no title and no badge. Clicking it tries to open a task detail by
that ID — works only because feature IDs are also task IDs. Polish-wise,
this link should render the feature_key (e.g. "→ FEAT-007") so the user
sees the human label.

**Recommendation:** include `realizes_feature_key` on `TaskSummary` so
the card can render `→ realizes FEAT-007 (title)`.

### NP-3. No filter on Features board (type / state / search)
The Tasks board has views (`BoardToolbar`), sort modes (manual /
priority), and lane hiding. The Features board has none of these —
all features and all fixes are co-mingled in the same lanes with no
way to filter `type=feature` vs `type=fix` or to sort.

**Recommendation:** at minimum add a `feature` / `fix` filter chip pair
in the toolbar.

### NP-4. FeatureComposer hidden behind submit button (no keyboard discoverability)
Pressing Enter inside the title input submits — good. But the radio
buttons for type are visually a `<label>` with hidden checkbox; they
look like badges, not radios. Screen-reader users get the right info,
but mouse-only users may not realise "Feature" / "Fix" are toggleable.

**Recommendation:** add hover/focus rings on the unselected badge to
suggest interactivity.

### NP-5. No empty-state copy specific to Features backlog
`Lane.tsx:99` renders `<EmptyState title="No tasks" />` regardless of
context. On the Features Backlog lane this reads as "No tasks" instead
of "No features yet — add one below". Minor cosmetic.

---

## What Works Well

### WW-1. State machine mirrors backend cleanly
`types.ts:57-74` redeclares `FEATURE_USER_TRANSITIONS_SET` as a frozen
set and exposes `canFeatureTransition`. The set matches the backend
FEATURE_USER_TRANSITIONS (7 edges), and the comment explicitly warns
about divergence. The drag-end handler (`FeaturesBoard.tsx:168`) guards
with `canFeatureTransition` before calling mutate.

### WW-2. Triple-key invalidation contract documented and enforced
`useFeatures.ts:14-21` defines `invalidateFeatureQueries(qc, spaceId)`
with a clear contract comment (R4) and calls it from every mutation.
This keeps the shared Features Backlog on the Tasks board in sync.

### WW-3. `feature_key` badge on cards
`Card.tsx:515-518` renders the FEAT-NNN / FIX-NNN badge with a
distinctive emerald style. Easy to scan visually.

### WW-4. Two-route navigation pattern
`router.tsx:27,35` supports both `/features` (global with selector) and
`/spaces/:spaceId/features` (scoped). The implementation in
`FeaturesPage.tsx:119-127` cleanly switches between
`ScopedFeaturesPage` and `GlobalFeaturesPage`, including URL-param
auto-select and localStorage persistence.

### WW-5. Sidebar nav entry registered
`Sidebar.tsx:143-150` adds a "Features" NavLink with the standard
`primaryNavLinkClasses` for active-state styling.

### WW-6. Drag-end guard rejects all illegal flows
Tests at `FeaturesBoard.test.tsx:237-302` cover same-lane drop, drop on
another card, drop on null, and 2 illegal transitions. Guard logic is
solid.

### WW-7. Shared Backlog uses the same `Card` component as Tasks board
Visual consistency between the Tasks-board "Features Backlog" column
(`Board.tsx:304-313`) and the FeaturesBoard backlog lane is preserved by
sharing `Card`. Only behaviour differs (drag-disabled + navigate).

---

## Summary Table

| Issue | Severity | File:Line | Recommendation |
|-------|----------|-----------|----------------|
| **CG-1** Card click is a no-op (no detail view) | CRITICAL | `FeaturesBoard.tsx:207,220` | Add `FeatureDetail` panel; wire `onOpen` |
| **CG-2** `getFeature` API method missing | CRITICAL | `api.ts:402-423` | Add `getFeature(id)` wrapping GET `/api/features/{id}` |
| **CG-3** `patchFeature` API method missing | CRITICAL | `api.ts:402-423` | Add `patchFeature(id, {title?, brief?})` |
| **CG-4** `processFeature` + Process button missing | CRITICAL | `api.ts`, no UI | Add client, hook, and detail-panel "Process" button |
| **CG-5** `setRealize` API method + realize UI missing | CRITICAL | `api.ts`, no UI | Add client, hook, and link/unlink picker in detail panel |
| **CG-6** Four `useFeatures` hooks missing | CRITICAL | `useFeatures.ts:1-66` | Add `useFeature`, `usePatchFeature`, `useProcessFeature`, `useSetRealize` |
| **UX-1** Issue link icon indistinguishable from PR doc icon | MAJOR | `Card.tsx:503-514` | Add `IconGitIssue`; render `#issue_number` |
| **UX-2** `realized_by` renders raw UUIDs | MAJOR | `Card.tsx:562-585` | Mirror `unmet_dependencies` shape (id+title), or show count |
| **UX-3** `realizing_items` count not on card | MAJOR | `Card.tsx:587-607` | Add `realized_by_count` on `TaskSummary`, render like goal progress |
| **UX-4** `waiting_question` rendering blocked by backend AttributeError | MAJOR | `Card.tsx:613-618` (UI ok) | Wait for backend fix (`set_feature_waiting_question` defect) |
| **UX-5** Drag-to-reorder silently ignored | MINOR | `FeaturesBoard.tsx:149-172` | Hide drag handle within-lane OR add backend `/reorder` endpoint |
| **UX-6** Double-wrapped `SortableContext` | MINOR | `FeaturesBoard.tsx:202-211` | Drop outer wrapper (Lane already does it) |
| **UX-7** Shared Backlog click → /features (loses context) | MAJOR | `Board.tsx:304-313` | Once CG-1 ships, deep-link to `?feature={id}` |
| **UX-8** Bare text loading state | TRIVIAL | `FeaturesBoard.tsx:178-180` | Intentional (matches Board.tsx); no action |
| **UX-9** No 404 silencing on errors | MINOR | `FeaturesBoard.tsx:181-183` | Mirror `Board.tsx:208-210` 404 guard |
| **UX-10** Two-route space selector pattern | TRIVIAL | `FeaturesPage.tsx` | Intentional; matches ArchivedPage |
| **UX-11** State-change drag has no toast / no error feedback | MAJOR | `FeaturesBoard.tsx:171` | Surface `transition.error` via toast or inline |
| **NP-1** FeatureComposer swallows backend 400 | MINOR | `FeaturesBoard.tsx:42-125` | Render `createFeature.error` inline |
| **NP-2** `realizes` link shows raw UUID not feature_key | MINOR | `Card.tsx:542-560` | Add `realizes_feature_key` to `TaskSummary` |
| **NP-3** No filter/sort/search on Features board | MINOR | `FeaturesBoard.tsx` (whole) | Add feature/fix filter chips in toolbar |
| **NP-4** Type-radio badges have weak interactive affordance | TRIVIAL | `FeaturesBoard.tsx:64-103` | Hover/focus ring on unselected state |
| **NP-5** Generic "No tasks" empty state | TRIVIAL | `Lane.tsx:99` | Plumb optional `emptyTitle` prop |
| **WW-1** State machine mirrors backend cleanly | — | `types.ts:57-74` | Keep as gold-standard pattern |
| **WW-2** Triple-key invalidation enforced | — | `useFeatures.ts:14-21` | Keep |
| **WW-3** `feature_key` badge | — | `Card.tsx:515-518` | Keep |
| **WW-4** Two-route navigation works | — | `router.tsx:27,35` | Keep |
| **WW-5** Sidebar nav entry registered | — | `Sidebar.tsx:143-150` | Keep |
| **WW-6** Drag-end guard covered by tests | — | `FeaturesBoard.test.tsx:237-302` | Keep |
| **WW-7** Shared Backlog reuses `Card` | — | `Board.tsx:304-313` | Keep |

---

## Net assessment

The Features board is a **read-mostly drag-and-drop skeleton**: state
transitions work, but every other backend capability (read detail, edit,
process, realize-link) is silently inaccessible from the UI. The 6
critical gaps (CG-1 … CG-6) are all the same underlying problem — **the
detail view was never built** — and addressing it requires four new API
methods, four new hooks, and a new `FeatureDetail` component. After that
the UX divergencies are mostly cosmetic.
