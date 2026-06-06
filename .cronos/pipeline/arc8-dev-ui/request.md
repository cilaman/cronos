Build the dev-runtime UI. Use the `frontend-design` skill
aesthetic; mobile-first.

**DevRuntimePanel** — new
`frontend/src/components/DevRuntimePanel.tsx` on the space header:
state-aware **Run / Stop / Restart** buttons (Run when stopped;
Stop + Restart when running), a log side panel, and a **clickable
health link** shown only when `healthy`. Reuse the
`ConversationStream` shell: `StatusPill`
([ConversationStream.tsx:43-75](frontend/src/components/ConversationStream.tsx#L43-L75))
for the state dot+label, the scroll container + sticky header
([ConversationStream.tsx:252-365](frontend/src/components/ConversationStream.tsx#L252-L365)),
and the IntersectionObserver autoscroll + "new activity" pill
([ConversationStream.tsx:207-248](frontend/src/components/ConversationStream.tsx#L207-L248)).
Skip the tool-call bucketing — render raw stdout/stderr lines.

**Log stream.** New hook `frontend/src/hooks/useDevLog.ts` cloning
the `EventSource` lifecycle in
[useLiveStream.ts:147-227](frontend/src/hooks/useLiveStream.ts#L147-L227)
against `/api/spaces/{id}/dev/stream`.

**Sidebar dot.** In `SpaceRow`
([Sidebar.tsx:26-92](frontend/src/components/Sidebar.tsx#L26-L92))
add a running-indicator dot by copying the autopilot-dot block
([Sidebar.tsx:54-60](frontend/src/components/Sidebar.tsx#L54-L60))
(e.g. `bg-accent-bright` when running). Drive it from a
`useDevRunning()` hook modeled on
[useRunning.ts:21-75](frontend/src/hooks/useRunning.ts#L21-L75).

**Types + client + hooks.** Add `DevRuntime` + `DevRuntimeStatus`
to [types.ts](frontend/src/types.ts) and extend `Space`
([types.ts:163-176](frontend/src/types.ts#L163-L176)) +
`SpaceSummary`
([types.ts:146-154](frontend/src/types.ts#L146-L154)). Add
`startDev/stopDev/restartDev/getDevStatus` to
[api.ts](frontend/src/api.ts) in the spaces group
([api.ts:126-176](frontend/src/api.ts#L126-L176)) via the
`request<T>` wrapper. New `frontend/src/hooks/useDevRuntime.ts`
with a status query (`refetchInterval` poll) + start/stop/restart
mutations modeled on
[useSpaces.ts:45-77](frontend/src/hooks/useSpaces.ts#L45-L77)
(invalidate `["space",id]` + `["dev-status",id]` on success).

**Acceptance** (vitest, EventSource + fetch mocked): the panel
renders state-appropriate buttons; Run triggers the start
mutation; `healthy` state shows a clickable link; `stopped` shows
an empty-log state; the sidebar dot reflects running state.

