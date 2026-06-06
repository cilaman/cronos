---
agent_mode: auto
agent_model: default
claude_session_id: 8ca2e17f-bcbe-41f5-8b0b-7a12d8c572b8
created_at: '2026-05-27T12:26:45Z'
depends_on: []
id: 2026-05-27-1226-frontend-timeframeselector-component
manual_order: 0
parent_id: 2026-05-27-1225-statistics-time-frame-filtering
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'Frontend: TimeFrameSelector component'
type: task
updated_at: '2026-06-03T14:12:49Z'
waiting_question: null
---

# Brief

## Task

Build a reusable `TimeFrameSelector` React component that lets users pick a statistics time window.

## Component location

`frontend/src/components/TimeFrameSelector.tsx`

## UX spec

**Pill toggle group** (one selected at a time):
| Label | Value |
|-------|-------|
| 6 h   | `6h`  |
| 24 h  | `24h` |
| 7 d   | `7d`  |
| 30 d  | `30d` |
| 90 d  | `90d` |
| All   | `all` (default) |
| Custom | `custom` |

When `custom` is selected:
- Show two compact date inputs: **From** and **To** (date-only, `<input type="date">`)
- Validate: both required, from ≤ to; show inline error otherwise
- Only call `onChange` once both dates are valid

## TypeScript API

```ts
export type Preset = '6h' | '24h' | '7d' | '30d' | '90d' | 'all' | 'custom';

export interface TimeFrame {
  preset: Preset;
  from?: string;  // ISO date string, only when preset === 'custom'
  to?: string;    // ISO date string, only when preset === 'custom'
}

interface Props {
  value: TimeFrame;
  onChange: (tf: TimeFrame) => void;
  className?: string;
}
```

## Notes

- Default export the component; also export the `TimeFrame` type and `Preset` type
- Use Tailwind for styling; match the existing pill/badge style used elsewhere in the app (look at how tabs are styled in StatsPage or DashboardPage)
- Keep it compact — it lives above a data table, not as a hero element

# History

```
2026-05-27T13:52:46Z [agent]
I'll explore the existing styling patterns before building the component.

Good, I have the styling patterns. Now let me check a couple of existing files directly to confirm the patterns before writing the component.

Now I have everything I need. Let me write the component.

Now let me verify it type-checks cleanly.

Node modules aren't installed in the workspace (they live in the Docker image). Let me manually review the component to make sure the TypeScript is sound, then check if there are existing frontend tests I should look at.

There are tests for other components. Let me look at a simple component test to match the pattern, then write one for `TimeFrameSelector`.

Now I'll write the test file.

Now let me commit the work using the goal-task-commit skill.

I'm on a `cronos/*` branch, not the goal's feature branch. Let me set that up first.

The feature branch `feature/statistics-time-frame-filtering` already exists. Let me run the test suite first, then commit.

All 12 TimeFrameSelector tests pass with 100% coverage. Now let me commit and push to the feature branch.

The feature branch is checked out in another worktree. I'll copy the new files there and commit.

Pushed. The commit sits on `feature/statistics-time-frame-filtering` right after the backend task's commit. 

**Summary:** `TimeFrameSelector.tsx` is built and tested — 7-pill toggle group matching the app's existing style, custom date pickers that only fire `onChange` when both dates are valid, and 12 passing tests at 100% coverage. Committed and pushed to the goal's feature branch.

STATUS: DONE
```
