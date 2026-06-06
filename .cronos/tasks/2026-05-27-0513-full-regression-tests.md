---
agent_mode: auto
agent_model: default
claude_session_id: bbff8cae-0786-4421-83eb-7c1e832eb77b
created_at: '2026-05-27T05:13:56Z'
depends_on: []
id: 2026-05-27-0513-full-regression-tests
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Full regression tests
type: task
updated_at: '2026-06-03T13:12:49Z'
waiting_question: null
---

# Brief

Please run full regression tests

# History

```
2026-05-27T05:17:34Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=tester
I'll run the full regression test suite — both backend pytest and frontend vitest.

**Full Regression Results — 1483 passed, 2 failed**

| Suite | Passed | Failed | Coverage |
|-------|--------|--------|----------|
| Backend (pytest) | 906 | 0 | 81.18% ✅ |
| Frontend (vitest) | 577 | 2 | — |

**2 Frontend failures** in `frontend/src/hooks/__tests__/useTasks.test.ts` (`useBoard` group):

1. `useBoard uses ["board", "all"] key when spaceId is null` — spy called with `[null, null]` but test expected `[null]` (extra argument)
2. `useBoard uses ["board", spaceId] key when spaceId is provided` — `data` came back `undefined` instead of the expected board object

Both failures point to `useBoard` gaining a second parameter that the tests haven't been updated to reflect. The implementation changed but the test assertions still expect the old single-argument signature.

Backend is clean and well above the 60% coverage floor.
```

```
2026-05-27T05:42:10Z [user]
Using test architect fix those 2 tests
```

```
2026-05-27T05:51:30Z [agent] run=1 model=claude-sonnet-4-6 mode=auto agents=test-architect
The API hit a temporary overload. Let me retry.

Both tests are fixed. Here's what changed:

**Root cause**: `useBoard` now takes `(spaceId, viewId)` with query key `["board", spaceId ?? "all", viewId]`. The two tests were asserting against the old single-argument shape.

**4 lines updated** in `frontend/src/hooks/__tests__/useTasks.test.ts`:
- `toHaveBeenCalledWith(null)` → `toHaveBeenCalledWith(null, null)`
- Query key `["board", "all"]` → `["board", "all", null]`
- Query key `["board", "space-1"]` → `["board", "space-1", null]`

**Result**: Frontend suite now **579/579 passing**, no regressions.

The agent also flagged a **pre-existing, unrelated issue**: 5 test files can't load due to a missing `@dagrejs/dagre` peer dependency (used by `GoalDependencyGraph.tsx` and `TreePage.tsx`). That's outside the scope of this task — fixable with `cd frontend && npm install @dagrejs/dagre` if you want to address it separately.
```

```
2026-05-27T06:32:26Z [user]
commit and push the fix to main
```

```
2026-05-27T06:33:02Z [agent] run=2 model=claude-sonnet-4-6 mode=auto
The fix is on `feature/git-workflow-skills`. I'll commit it there, then cherry-pick to main and push.

Main is checked out in another worktree. I'll apply the fix there directly.

Pushed. Commit `c4d6db5` is now on `main` — the 4-line test fix updating `useBoard` assertions to the two-arg signature.
```
