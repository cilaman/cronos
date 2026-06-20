# cronos

Kanban-style task manager for orchestrating Claude Code agents. Single-user personal platform — agents run via the Claude Code CLI bundled in the backend container, authenticated against a Claude Pro/Max subscription (no API key needed).

- **Quick-start & ops**: [README.md](README.md) (includes [§ Security posture](README.md#security-posture))
- **Testing guide**: [TESTING.md](TESTING.md)
- **VPS deployment**: [deploy/VPS_SETUP.md](deploy/VPS_SETUP.md)
- **Architecture decisions**: [docs/adr/](docs/adr/)

## Dev commands

```sh
# Local dev (Docker Compose — backend :8000 + Caddy on :8080)
export CLAUDE_CODE_OAUTH_TOKEN=$(claude setup-token)   # optional; needed for agent runs
docker compose up --build
# open http://localhost:8080

# Backend tests (60% coverage floor enforced)
cd backend && pip install -e ".[dev]"
cd backend && pytest tests/ --cov=app --cov-report=term-missing

# Frontend tests & build
cd frontend && npm test
cd frontend && npm run build

# Health check (no auth required)
curl http://localhost:8080/api/health
```

## Architecture

### Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn, SQLite (aiosqlite), Pydantic v2 |
| Frontend | React 18, Vite 5, TypeScript 5.6 strict, Tailwind 3.4, TanStack Query 5, dnd-kit |
| Agent runtime | Claude Code CLI (Node 22, bundled in backend Docker image) |
| Web server | Caddy (TLS termination, HTTP Basic Auth, reverse proxy) |
| Deployment | Docker Compose, Ubuntu 24.04 VPS |

### Task state machine

```
backlog → active → waiting → done → archived
                ↘ done ↗
```

- `storage.py` enforces strict transitions; user and worker have different allowed sets.
- Goals propagate state upward: re-enqueued when an ACTIVE child finishes; done when all children done.

### Auth

HTTP Basic Auth via Caddy on every request. `/api/health` is public (no auth). Credentials set via `BASIC_AUTH_USER` + `BASIC_AUTH_HASH` in `.env`. Inside the container the Claude Code CLI authenticates via `CLAUDE_CODE_OAUTH_TOKEN` (OAuth against Claude subscription).

### Memory store

`app/memory_store.py` — shared context per space, scope-indexed (space-scoped or global), I/O atomic writes, rebuild on space sync. Supports outcome-linked confidence updates via `nudge_confidence()`: when a task completes, retrieved memory items are nudged +0.05 on success and -0.1 on failure, clamped to [0.0, 1.0].

### Agent execution

`app/agent.py` spawns `claude code -s <space>` as a subprocess, captures stdout/stderr, tracks status. `app/worker.py` is the background executor driving goals and state transitions.

## Key modules

| Path | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app, router registration, background task startup (cron loop initialization + logging config), file watcher with event-trigger dispatch; task-state-change callback injection; metrics_router registration |
| `backend/app/storage.py` | **CORE** — TaskStore, state machine, dependency DAG validation, cycle detection (41 KB); durable queue: `task_leases` (owner, lease_expiry, heartbeat_at) and `auto_resume_counts` SQLite tables with CRUD methods (acquire_lease, heartbeat_lease, release_lease, get_expired_leases; load_auto_resume_count, upsert_auto_resume_count, delete_auto_resume_count) |
| `backend/app/logging_config.py` | JSON logging setup — `JsonFormatter` for structured logs (timestamp, level, logger, message, run_id, task_id fields), `bind_run_context()` context manager for safe contextvars binding, `configure_logging()` entry point (configurable `CRONOS_LOG_LEVEL`, default INFO) |
| `backend/app/notifier.py` | Push notification on task state transitions — `notify_state_change()` coroutine posts to `CRONOS_NOTIFY_URL` webhook (payload: task_id, task_title, status, exit_reason, summary); 5s timeout, fire-and-forget, error logging only |
| `backend/app/api/metrics.py` | Observability endpoint — `GET /api/metrics` (no auth, parity with /api/health) returns `{queue_depth, active_tasks, auto_resume_total}` integer counters for monitoring queue health and auto-resume rate |
| `backend/app/space_storage.py` | Space persistence, layouts, settings, `.cronos` subdirectory management |
| `backend/app/agent.py` | Agent spawning, stdout/stderr capture, status tracking via `parse_status()` (checks structured `cronos_status` block first, falls back to deprecated free-text `STATUS:` line with warning log); `bind_run_context()` for run_id/task_id propagation in logs |
| `backend/app/file_service.py` | File classification and listing utilities (classify_file, list_files, list_git_changed_files, resolve_safe); FileEntry model; used by space file endpoints and task file operations |
| `backend/app/worker.py` | Background task processor (goals, agent execution, state transitions); durable queue: acquires task lease before _run_task, runs async heartbeat loop (configurable LEASE_TTL, HEARTBEAT_INTERVAL), releases lease in finally block; persists auto_resume_count durably to DB on _finalize; harness run lifecycle execution, event publishing for SSE streams; post-task-completion trust-loop hook nudges retrieved memory confidence (±0.05/±0.1) based on task outcome; `_persist_cronos_remember_blocks()` captures structured CRONOS_REMEMBER sentinel blocks from agent final_text and persists them as unconfirmed MemoryItems (parallel to MEMORY: path); `bind_run_context()` for run_id/task_id propagation in logs; `notify_state_change()` fire-and-forget on terminal/WAITING transitions via webhook (if CRONOS_NOTIFY_URL set) |
| `backend/app/models.py` | Pydantic schemas: TaskState, Task, Space, View, agent modes/models; Plugin Management section (PluginComponent, PluginEntry, MarketplacePluginEntry, MarketplaceEntry, PluginsResponse) |
| `backend/app/trace_parser.py` | Parse structured `cronos_status` fenced-JSON blocks (primary) and legacy `STATUS:` fields from agent stdout, extract RunTrace (result, exit_reason, parent_run_id, memory_hit_rate, `memory_used` bare IDs, etc.); `_memory_slug()` strips `.md` suffix from memory file paths; exit_reason includes `NO_CRONOS_STATUS` when neither channel emits a marker |
| `backend/app/tools/scanner.py` | Scan .claude/ directory for markdown files and tools; extract descriptions from YAML frontmatter or first paragraph; parse settings.json for hooks and permissions |
| `backend/app/tools/plugins.py` | Claude Code plugin CLI wrapper — `list_plugins()`, `list_marketplaces()`, `plugin_components(install_path)`, mutation functions (install, uninstall, enable, disable, add_marketplace, remove_marketplace); all mutations serialized via asyncio.Lock; PluginCliError for structured error handling |
| `backend/app/api/tasks.py` | Task CRUD, state transitions, drag-drop reordering, lane overrides (29 KB) |
| `backend/app/api/spaces.py` | Space CRUD, repo linking, project settings; space file browsing endpoints (GET /{space_id}/files list and GET /{space_id}/files/{file_path} retrieve) |
| `backend/app/api/plugins.py` | Plugin management API — 7 endpoints (GET, POST /install, POST /uninstall, POST /enable, POST /disable, POST/DELETE /marketplaces) delegating to `app.tools.plugins` coroutines; ValueError→422, PluginCliError→502 error handling; marketplace mutators return full PluginsResponse |
| `backend/app/api/harnesses.py` | Harness CRUD endpoints and run lifecycle (GET/POST/PUT/DELETE, POST /run, GET /runs, POST /webhook) with concurrency contract; webhook authentication via Bearer token |
| `backend/app/api/harness_runs.py` | Harness run status and control endpoints (GET /{run_id}, POST /{run_id}/cancel, GET /{run_id}/stream SSE) |
| `backend/app/harnesses/model.py` | Pydantic models with reference integrity validation (HarnessNode, HarnessEdge, Harness); Wait and Aggregator node data conventions; trigger node kinds (`task-state-change`, `webhook`, `file-change`) and their `data` schemas |
| `backend/app/harnesses/validator.py` | DAG validation (cycle detection, self-loop rejection, reference fidelity checks, human Wait required fields R6); event-trigger validation (kind field, required/optional fields per kind, defaults application) |
| `backend/app/harnesses/store.py` | HarnessStore with atomic YAML I/O to `.cronos/harnesses/<name>.yml` per space |
| `backend/app/harnesses/executor.py` | **Harness executor** — runtime-gated BFS DAG interpreter with control-flow dispatch (decision/wait/aggregator nodes), agent invocation, fail-fast on node failure, variable scope propagation, run-state persistence, SSE event publishing (`node_transition`, `edge_chosen`, `run_status`), cancel-race guard; `bind_run_context()` for run_id propagation in logs |
| `backend/app/harnesses/decision.py` | Decision node evaluator — four-layer signal precedence (cronos_status structured block > legacy STATUS marker > exit_reason > regex > variable condition) with whitelisted variable grammar (==, !=, in) |
| `backend/app/harnesses/wait.py` | Wait node evaluators — `enter_wait()` parks human-mode harness runs with `waiting_node_id` routing key; `await_timed_wait()` sleeps timed-mode runs; on restart sleeps only the remaining duration (`wake_at` timestamp) |
| `backend/app/harnesses/aggregator.py` | Aggregator node evaluator — `mode='all'` (fires when all predecessors done; any failure fails aggregator) or `mode='any'` (fires when first predecessor done; fails only if all fail); verdict-only semantics |
| `backend/app/harnesses/interpolate.py` | Variable/data interpolation via `string.Template.safe_substitute` with precedence (root_vars < upstream_outputs) |
| `backend/app/harnesses/brief_composer.py` | Child-task brief composition for harness executor nodes (agent header, skill prefix, prompt inclusion) |
| `backend/app/harnesses/run_state.py` | RunState dataclass with lifecycle status and timing fields (`started_at`, `ended_at`, `wake_at` ISO-8601 UTC per node); atomic persistence (tempfile + os.replace); reconciliation on resume; `wake_at` persisted for timed Wait nodes to enable remaining-duration sleep on restart |
| `backend/app/harnesses/run_index.py` | Append-only per-harness run history index with concurrent-safe locking; `read_index()`, `append_run()`, `update_run_status()` |
| `backend/app/harnesses/run_trigger.py` | Shared `enqueue_harness_run` helper — task creation, run index append, worker registration; used by POST /run endpoint and cron loop |
| `backend/app/harnesses/cron.py` | Stateless cron-trigger background loop — `should_fire(expression, timezone, prev_tick, now)`, `has_active_run()`, `cron_loop()` with overlap guard and croniter integration |
| `backend/app/reaper.py` | Durable queue reaper — background coroutine that periodically scans expired/stale-heartbeat task leases and re-enqueues them via markdown-state gate; detects silent wedging (heartbeat stalls) and crashed workers; configurable REAPER_INTERVAL and HEARTBEAT_TIMEOUT; scan-first loop ensures at least one recovery pass on startup |
| `backend/app/memory_parser.py` | Parse `MEMORY:` inline markers/fenced blocks, structured `CRONOS_REMEMBER` fenced blocks, and structured `cronos_status` completion blocks from agent output; `parse_memory_blocks()` → list[MemoryBlock], `parse_cronos_remember_blocks()` → list[CronosRememberBlock], `parse_cronos_status_block()` → tuple[str \| None, str \| None]; YAML-safe parsing with silent-skip on malformed/missing-required-fields |
| `backend/app/memory_store.py` | Shared context storage (list, retrieve, prune); `nudge_confidence(scope, item_id, delta)` adjusts memory item confidence (clamped to [0.0, 1.0]) to implement outcome-linked trust updates |
| `backend/app/harnesses/triggers.py` | Event routing core — `EventBusEvent` dataclass, `EventDebouncer` in-memory dedup, `fan_out_to_harnesses()` async dispatcher with pattern matching and harness selection |
| `backend/app/git_ops.py` | `git clone/commit/push` wrappers for repo-linked spaces |
| `backend/app/goal_sync.py` | Goal state propagation |
| `frontend/src/App.tsx` | Root layout — sidebar nav + outlet (responsive mobile drawer) |
| `frontend/src/pages/BoardPage.tsx` | Kanban board — dnd-kit drag-drop, lanes by TaskState |
| `frontend/src/pages/TreePage.tsx` | Dependency DAG visualization (dagre) |
| `frontend/src/pages/HarnessRunsPage.tsx` | Harness run history list with embedded per-run detail panel; trigger button and status badges |
| `frontend/src/pages/HarnessListPage.tsx` | Harnesses landing page at `/spaces/:spaceId/harnesses` — card grid with harness overview (node/edge/var counts), create/edit/runs/delete actions, with CreateHarnessModal and delete confirmation |
| `frontend/src/pages/SpaceToolsPage.tsx` | AI Tools landing page at `/spaces/:spaceId/tools` — tabs for installed tools, available tools, and plugins (plugin management UI) |
| `frontend/src/components/HarnessRunPanel.tsx` | Per-run detail panel with node status badges, live SSE indicator, cancel button, buffer-truncated badge |
| `frontend/src/components/ToolDetailPanel.tsx` | Detail panel for tools displaying name, description, type badge (space/global/plugin), and components list |
| `frontend/src/hooks/useTasks.ts` | React Query hooks for task CRUD |
| `frontend/src/hooks/useHarnessRuns.ts` | React Query hooks for harness run queries, mutations (trigger, cancel), and SSE stream subscription |
| `frontend/src/api.ts` | HTTP client with task/space file URL helpers (taskFileUrl, spaceFileUrl), task/space file API functions (taskFiles, spaceFiles), and plugin management functions (plugins, installPlugin, uninstallPlugin, enablePlugin, disablePlugin, addMarketplace, removeMarketplace); includes harness run types (RunSummary, NodeState, HarnessRunState) and plugin types (PluginsResponse) |
| `frontend/src/pages/HarnessEditor.tsx` | Harness visual editor canvas page — React Flow v12 graph layout with 5 custom node types (Agent/Trigger/Decision/Wait/Aggregator), NodePalette drag source, VariableInspector side panel, Save button (GET-then-PUT); live-execution overlay with RunHistory (left panel), RunOverlay (canvas), and ChildTaskDrawer (right panel) |
| `frontend/src/hooks/useHarnesses.ts` | React Query hooks for harness CRUD and canvas save (`useHarnesses` list, `useHarness` single fetch, `useCreateHarness` and `useDeleteHarness` mutations, `useSaveHarness` GET-then-PUT mutation enforcing created_at preservation) |
| `frontend/src/components/harness/runStatus.ts` | Single source of truth for node run-status styling: `NodeRunStatus` union type, `RunStatusOverlayData` interface (optional fields: runStatus, startedAt, endedAt, childTaskId), and `runStatusClassName()` mapper returning Tailwind class strings per status |
| `frontend/src/components/harness/harnessMapping.ts` | Round-trip module converting between React Flow flat graph shape (nodes[], edges[]) and backend nested NodeRef payload; `toReactFlow()` and `fromReactFlow()` pure functions |
| `frontend/src/components/harness/AgentNode.tsx` | Custom React Flow node for Agent task invocation (input/output handles, label, agent_ref display); applies run status styling from `runStatusClassName()` |
| `frontend/src/components/harness/TriggerNode.tsx` | React Flow node for harness triggers (output-only handle; Trigger/Webhook/FileChange kinds determined via harness data); applies run status styling |
| `frontend/src/components/harness/DecisionNode.tsx` | React Flow node for conditional branching (input/output handles with yes/no ids); applies run status styling |
| `frontend/src/components/harness/WaitNode.tsx` | React Flow node for human-wait synchronization points (input/output handles); applies run status styling |
| `frontend/src/components/harness/AggregatorNode.tsx` | React Flow node for collecting multiple upstream branches (N input handles, single output; mode=all/any determined via harness data); applies run status styling |
| `frontend/src/components/harness/RunOverlay.tsx` | Central run-state overlay component — renders node and edge styling for live-execution runs; consumes `useRunStateOverlay()` hook; cleans up stale overlay data when `runId` changes (R4 cleanup effect) |
| `frontend/src/components/harness/RunHistory.tsx` | Left-panel component — lists harness runs newest-first with status pills and timestamps; emits `onSelectRun(runId, mode)` to trigger canvas run-state switch |
| `frontend/src/components/harness/ChildTaskDrawer.tsx` | Right-side drawer component — accepts `child_task_id` prop, fetches task via `useTask()`, renders loading skeleton, then delegates to `ConversationStream` for task detail display |
| `frontend/src/hooks/useRunStateOverlay.ts` | Central hook for run-state reduction: consumes SSE events (`useHarnessRunStream` live mode) or REST snapshots (`useHarnessRun` replay mode); coalesces events into `NodeRunStatus` and edge-coloring maps with `requestAnimationFrame` batching (R7) |
| `frontend/src/components/harness/NodePalette.tsx` | Right-side draggable palette of 5 node types with React Flow dataTransfer semantics (effectAllowed=move) |
| `frontend/src/components/harness/VariableInspector.tsx` | Right-side inspector panel — per-node-type config editing: AgentNode (agent_ref + prompt_template), WaitNode (mode + max_wait_seconds), AggregatorNode (mode all/any), TriggerNode (kind + per-kind fields), edge condition editing; harness-level variables add/remove UI |
| `frontend/src/types.ts` | Harness visual editor type definitions (NodeType, Position, NodePort, HarnessNode, NodeRef, HarnessEdge, Harness interfaces mirroring backend Pydantic v2 models); plugin management types (PluginComponent, PluginEntry, MarketplacePluginEntry, MarketplaceEntry, PluginsResponse); AiToolEntry.scope widened to include `"plugin"` |

## Directory layout

```
backend/
  app/            FastAPI source (main, storage, agent, worker, models, api/)
  tests/          Pytest suite (60% coverage floor)
  Dockerfile      Python 3.12 + Node 22, Claude Code CLI bundled
  pyproject.toml  Dependencies and pytest/coverage config

frontend/
  src/            React + TypeScript source (pages/, components/, hooks/)
  Dockerfile      Node image; served via Caddy

deploy/
  VPS_SETUP.md   End-to-end VPS provisioning checklist
  cronos.service              systemd foreground unit
  cronos-backup.{service,timer}   nightly backup (03:17 UTC, 14-day rotation)
  cronos-upgrade-webhook.service  auto-upgrade webhook
  backup.sh       Tars /opt/cronos/data → /var/backups/cronos/

data/             Per-deployment state (gitignored)
.claude/          Claude Code harness: settings, agents, skills

docs/
  adr/            Architecture Decision Records (Nygard-style)
    001-markdown-as-truth.md     Markdown files are source-of-truth; SQLite is a reconstructible index
    002-sqlite-durability.md     SQLite (not Postgres/Redis) is the durable queue substrate for G08
```

## Architecture Decision Records

Cronos documents key architectural choices via ADRs in `docs/adr/`:

| ADR | Decision |
|-----|----------|
| [001: Markdown as truth, SQLite as disposable index](docs/adr/001-markdown-as-truth.md) | `.md` files under `.cronos/` are the single source of truth for tasks, goals, and spaces. `cronos-index.db` is a reconstructible performance cache; deleting it and restarting always recovers correctly (self-healing invariant). Task leases (G08) live in SQLite because they are transient coordination data, not durable state. |
| [002: SQLite durability (over Postgres, Redis, LangGraph)](docs/adr/002-sqlite-durability.md) | Single-VPS personal system uses SQLite for the durable task queue (lease + heartbeat tables) instead of a separate database service. Worker heartbeat renewal (15 s interval) bridges long agent runs; reaper reclaims stale leases on startup. Revisit if horizontal scaling is needed. |

## Registered agents

| Name | Model | Purpose |
|------|-------|---------|
| [test-architect](.claude/agents/test-architect.md) | Opus 4.7 | Test suite owner — audits coverage gaps, writes tests, spawns tester |
| [tester](.claude/agents/tester.md) | Sonnet 4.6 | Runs pytest/vitest, parses results, posts TestReport to API |
| [security-officer](.claude/agents/security-officer.md) | Opus 4.7 | OWASP security audit of the codebase |
| [pipeline-scout](.claude/agents/pipeline-scout.md) | Haiku 4.5 | CC-v1 research agent — memory-first codebase recon, emits scout-report |
| [pipeline-analyst](.claude/agents/pipeline-analyst.md) | Sonnet 4.6 | CC-v1 analysis agent — decomposes feature request into testable requirements |
| [pipeline-architect](.claude/agents/pipeline-architect.md) | Opus 4.7 | CC-v1 design agent — produces implementation DAG with iterations[] and risks[] |
| [pipeline-implementor](.claude/agents/pipeline-implementor.md) | Sonnet 4.6 | CC-v1 implementation agent — executes one iterations[] entry, emits impl-report |
| [pipeline-reviewer](.claude/agents/pipeline-reviewer.md) | Opus 4.7 | CC-v1 review agent — audits implementor diff, emits verdict (pass/needs_fix/fail) |
| [pipeline-doc-sync](.claude/agents/pipeline-doc-sync.md) | Haiku 4.5 | CC-v1 doc agent — updates docs for changed files, emits doc-report (terminal) |
| [pipeline-retro](.claude/agents/pipeline-retro.md) | Opus 4.7 | CC-v1 retro agent — post-goal retrospective; scores 5 dimensions, emits retro-{slug}.md with fix-type-classified findings |

Test reports stored at `{space}/.cronos/test-reports/{timestamp}.json`; coverage summaries at `{space}/.cronos/test-coverage.md`.

## Registered skills

| Name | Purpose |
|------|---------|
| [goal-task-commit](.claude/skills/goal-task-commit/) | Commits task changes to goal feature branch |
| [goal-finalize](.claude/skills/goal-finalize/) | Finalizes completed goals |
| [goal-branch-setup](.claude/skills/goal-branch-setup/) | Sets up feature branches for goals |
| [frontend-design](.claude/skills/frontend-design/) | Frontend styling and UX work |
| [evaluate-run](.claude/skills/evaluate-run/) | Assesses agent run outcomes |
| [create-goal](.claude/skills/create-goal/) | Creates a goal with child tasks in the Cronos board via the backend API |
| [create-task](.claude/skills/create-task/) | Creates a single task in the Cronos board via the backend API |
| [write-memory](.claude/skills/write-memory/) | Writes memory to the correct workspace-scoped path (never the space root) |
| [task-finalize](.claude/skills/task-finalize/) | Mandatory last step of every task — verify completion, handle git, write memory, emit STATUS |
