---
agent_mode: auto
agent_model: sonnet
claude_session_id: 870ffbc1-2372-4366-90d5-46dfc07b376f
created_at: '2026-06-02T07:18:50Z'
depends_on: []
id: 2026-06-02-0718-frontend-tool-detail-panel
manual_order: 0
parent_id: 2026-06-02-0718-ai-tools-detail-screens
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: Frontend – Tool detail panel
type: goal
updated_at: '2026-06-02T08:16:34Z'
waiting_question: null
---

# Brief

Create a slide-over drawer component that shows full structured detail for a selected AI tool, and wire it into the existing ToolCard components.

## New component

File: `frontend/src/components/ToolDetailPanel.tsx`

Props:
```typescript
interface ToolDetailPanelProps {
  tool: AiToolEntry & { category: "agent" | "command" | "skill" | "context" };
  spaceId: string;
  onClose: () => void;
}
```

### Panel layout

- **Header**: large category icon + tool name (h2) + scope badge ("space" / "global") + X close button
- **Metadata row**: path (monospace), modified_at (human-readable), scope
- **Description**: show full description text (not truncated)
- **Content section**: fetches `/api/spaces/{spaceId}/tool-content?path={tool.path}&scope={tool.scope}` and renders the raw markdown content in a `<pre>` / `<code>` block with Tailwind prose styling. Show a spinner while loading.
- Slide in from the right — fixed overlay with a semi-transparent backdrop.
- Keyboard: pressing Escape closes the panel.

### Wire ToolCard

In `frontend/src/pages/SpaceToolsPage.tsx`:
- Add `selectedTool` state (`AiToolEntry & { category }` | null).
- Each `ToolCard` receives an `onClick` prop that sets `selectedTool`.
- When `selectedTool` is non-null, render `<ToolDetailPanel>` overlaid on the page.

### API call

Add to `frontend/src/api.ts`:
```typescript
toolContent: (spaceId: string, path: string, scope: string) =>
  request<AiToolDetail>(`/api/spaces/${spaceId}/tool-content?path=${encodeURIComponent(path)}&scope=${scope}`)
```

Add `AiToolDetail` type to `frontend/src/types.ts`:
```typescript
export interface AiToolDetail extends AiToolEntry {
  category: "agent" | "command" | "skill" | "context";
  content: string;
}
```

Add a query hook in `frontend/src/hooks/useSpaces.ts`:
```typescript
export function useToolContent(spaceId: string | null, path: string | null, scope: string | null) {
  return useQuery({
    queryKey: ["tool-content", spaceId, path, scope],
    queryFn: () => api.toolContent(spaceId!, path!, scope!),
    enabled: !!spaceId && !!path && !!scope,
    staleTime: 60_000,
  });
}
```

## Acceptance

- Clicking any ToolCard opens the detail panel on the right.
- Panel shows name, description, path, scope, modified_at, and the file's raw content.
- Pressing Escape or clicking the backdrop closes the panel.
- Content area shows a loading spinner until the fetch resolves.
- Panel is visually distinct (not generic): use the category icon and color accents matching the existing category palette in SpaceToolsPage.

# History

```
2026-06-02T08:16:34Z [agent]
I'll start by reading the key files that need to be modified.

Let me check the Tailwind config for the custom color tokens.

Now I have everything I need. Let me implement all four changes in parallel.

Now I'll implement all the changes. Starting with the types, API, hook, component, and page updates.

Now create the `ToolDetailPanel` component:

Now update `SpaceToolsPage.tsx` to add state, wire `onClick` through `ToolCard`/`ToolGrid`, and render the panel:

Now add state and panel rendering in the `SpaceToolsPage` component:

Now update the four `ToolGrid` calls to pass `onToolClick`, and add the panel render at the end:

Now add the panel at the bottom of the page JSX, just before the closing `</div>`:

Let me verify the final state of the page file looks correct:

The page structure looks good. Let me run the TypeScript check to verify everything compiles cleanly:

Those TypeScript errors are in `BuildInfo.tsx` - let me verify they're pre-existing and not caused by my changes:

Good - the BuildInfo.tsx errors are pre-existing. My changes need to be restored:

My changes are restored. Now let me run the TypeScript check again to confirm only the pre-existing BuildInfo.tsx errors remain:

Only the pre-existing `BuildInfo.tsx` errors remain — no new TypeScript errors from my changes. Now let me finalize this task:

This is a goal child task — delegating git to goal-task-commit:

The feature branch exists. I need to switch to it and apply my changes there.

The changes are unstaged on `main`. I'll switch to the feature branch (which already has the backend changes) and commit the frontend changes there:

The feature branch is checked out in another worktree. I'll copy my changes there and commit:

Committed and pushed. Now writing memory and emitting STATUS:

MEMORY[fact]: Created `frontend/src/components/ToolDetailPanel.tsx` — slide-over drawer component showing full tool details (category icon, name, scope badge, metadata row, description, raw file content via `useToolContent` hook). Wired into `SpaceToolsPage.tsx` via `selectedTool` state; each `ToolCard` now has `onClick`. Added `AiToolDetail` type to `types.ts`, `toolContent` method to `api.ts`, and `useToolContent` hook to `useSpaces.ts`.

MEMORY[observation]: Feature branch `feature/ai-tools-detail-screens` was checked out in the backend task's worktree (`2026-06-02-0718-backend-tool-content-endpoint`), not accessible from main worktree. Resolved by copying files to that worktree and committing via `git -C`.

STATUS: DONE
```
