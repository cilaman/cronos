# Performance Regression Investigation & Fix Plan

**Regression introduced by:** commit `12b773a` — *Merge `feature/cronos-remediation-plan`: security hardening, durable queue, structured logging, CI pipeline, coverage floor, OpenAPI types*

**Reported symptoms**
1. Every screen takes up to seconds to show.
2. When one task (agent) creates another task, the new task is not shown in the board/todo list until an application upgrade (container restart) is triggered.
3. The user must manually refresh the browser to see run progress.

**Status:** Investigation complete. No code changed. This document is a proposal only.

---

## 1. Root Cause (high confidence)

### Synchronous SQLite on the asyncio event loop

The merge introduced a new SQLite index DB, `cronos-index.db`, for worker lease coordination ([storage.py:486](../backend/app/storage.py#L486)). **Every** database operation opens a fresh connection and commits synchronously, directly on the single FastAPI/uvicorn event loop. There is no `aiosqlite`, no `asyncio.to_thread`, and no `run_in_executor` anywhere in `storage.py`, `reaper.py`, or `run_executor.py` (verified by grep — zero hits).

Each call follows the pattern `sqlite3.connect()` → `execute` → `commit()` → `close()` ([storage.py:615-634](../backend/app/storage.py#L615-L634)). With SQLite's default journal mode (no WAL, `synchronous=FULL` — confirmed, no `PRAGMA` anywhere), **every commit forces an fsync** to the data volume. On a VPS disk that is ~5–50 ms each, and it **blocks the entire event loop** — so every concurrent HTTP request, every SSE event, and the file-watcher coroutine all stall behind it.

These blocking writes fire constantly:

| Trigger | Frequency | Call site |
|---|---|---|
| Any task create / update / state transition | every write | `_reindex_locked` → `_db_upsert` ([storage.py:832-853](../backend/app/storage.py#L832-L853), 21 call sites) |
| **File-watcher reindex on every `.md` write** | very high during a run (agents write many files) | [main.py:226](../backend/app/main.py#L226) → `reindex_path` → `_db_upsert` |
| Worker heartbeat per running task | every 15 s | [run_executor.py:527](../backend/app/run_executor.py#L527) `heartbeat_lease` |
| Reaper sweep | every 30 s | [reaper.py:23](../backend/app/reaper.py#L23) → `get_expired_leases` |

### Aggravating finding: the `tasks` table is never read

There is no `SELECT … FROM tasks` anywhere in the codebase — only `task_leases` and `auto_resume_counts` are ever queried. The board reads exclusively from the in-memory `_by_id` dict ([storage.py:858-883](../backend/app/storage.py#L858-L883)). So the per-write `_db_upsert` / `_db_delete` into `tasks` is **pure dead-weight blocking I/O writing to a table that nothing queries** — the single highest-frequency offender during active runs.

---

## 2. How the Root Cause Produces Each Symptom

| Symptom | Mechanism |
|---|---|
| **1. Screens take seconds** | Board/space GETs queue behind blocking commits from the watcher + heartbeats whenever any agent is active. The reads themselves are in-memory and fast; the event loop is simply stalled. |
| **2. New task not shown until upgrade** | The create-task POST (see `.claude/skills/create-task/SKILL.md`) hits the same backend and *does* update `_by_id`, but its handler is queued behind the stalled loop, and the watcher coroutine that would reindex is starved. A container "upgrade" restarts the backend → `reload_all()` rebuilds `_by_id` from on-disk files ([storage.py:789-826](../backend/app/storage.py#L789-L826)), so the task finally appears. The file is on disk the whole time; in-memory propagation is what's delayed. |
| **3. Must refresh to see progress** | Live progress is pushed over SSE (`useLiveStream` → `/api/tasks/{id}/stream`, `useRunning` → `/api/spaces/{id}/stream`). SSE emission runs on the same blocked loop, so the stream goes stale; a manual refresh forces a fresh in-memory read. |

---

## 3. Secondary Contributors (frontend — compound #2/#3)

Minor on their own; they make the backend stalls more visible.

- `useTask()` has **no `refetchInterval`** ([useTasks.ts:15-21](../frontend/src/hooks/useTasks.ts#L15-L21)) — the open task-detail panel never re-polls; it relies entirely on the (now-stalled) SSE stream.
- `useBoard()` polls every 5 s but lacks `refetchIntervalInBackground: true` ([useTasks.ts:7-12](../frontend/src/hooks/useTasks.ts#L7-L12)) — polling pauses when the tab is backgrounded.
- The `QueryClient` is created with no `defaultOptions` ([main.tsx:8](../frontend/src/main.tsx#L8)).

---

## 4. Fix Plan

### Phase 1 — Stop blocking the event loop *(the actual fix — do this first)*

1. **Drop the dead `tasks` mirror.** Nothing reads it, so remove the `_db_upsert` / `_db_delete` calls from `_reindex_locked` and drop the `tasks` table from `reload_all`. Eliminates the highest-frequency blocking writes with zero behavioral loss. *Precondition: repo-wide check that no external tooling queries `tasks`.*
2. **Move remaining DB ops (leases, auto-resume counts) off the loop.** Wrap each call in `await asyncio.to_thread(...)` (smaller, lower-risk) or migrate to `aiosqlite`.
3. **Enable WAL + relax fsync** on the lease DB in `_ensure_db_schema`: `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`. Lease/heartbeat state is reconstructible, so `NORMAL` durability is acceptable.

### Phase 2 — Frontend liveness hardening *(defensive)*

4. Add `refetchInterval` (3–5 s) to `useTask()` so the detail panel self-heals if SSE drops.
5. Add `refetchIntervalInBackground: true` to `useBoard()` and set sensible `QueryClient` `defaultOptions`.

### Phase 3 — Verification

6. Reproduce locally: start an agent run, measure board GET latency while a run heartbeats and writes files — expect a drop from seconds to <100 ms.
7. Confirm an agent-created child task appears within one poll interval (≤5 s) **without** a restart.
8. Confirm task-detail progress updates live without manual refresh.
9. Run `cd backend && pytest tests/` (80% floor) and `cd frontend && npm test`. Pay attention to any lease/reaper tests that assume the synchronous `tasks` mirror.

---

## 5. Risk Notes

- **Lease correctness must be preserved.** `acquire_lease`'s atomicity relies on SQLite locking. WAL is compatible; with `to_thread`, ensure each operation still uses its own short-lived connection (already the case).
- **Removing the `tasks` table touches `reload_all` and tests.** Verify no test asserts its contents before deleting.

---

## 6. Quickest High-Impact Win

**Phase 1, Step 1 alone** (deleting the never-read mirror writes) likely removes the bulk of the stalls, since the file-watcher reindex path is the highest-frequency offender during active runs. The remaining `to_thread`/WAL changes harden the lower-frequency lease/heartbeat paths.
