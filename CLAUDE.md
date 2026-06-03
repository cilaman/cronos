# cronos

Kanban-style task manager for orchestrating Claude Code agents. Single-user personal platform — agents run via the Claude Code CLI bundled in the backend container, authenticated against a Claude Pro/Max subscription (no API key needed).

- **Quick-start & ops**: [README.md](README.md)
- **Testing guide**: [TESTING.md](TESTING.md)
- **VPS deployment**: [deploy/VPS_SETUP.md](deploy/VPS_SETUP.md)

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

`app/memory_store.py` — shared context per space, scope-indexed, I/O atomic writes, rebuild on space sync.

### Agent execution

`app/agent.py` spawns `claude code -s <space>` as a subprocess, captures stdout/stderr, tracks status. `app/worker.py` is the background executor driving goals and state transitions.

## Key modules

| Path | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app, router registration, background task startup, file watcher |
| `backend/app/storage.py` | **CORE** — TaskStore, state machine, dependency DAG validation, cycle detection (41 KB) |
| `backend/app/space_storage.py` | Space persistence, layouts, settings, `.cronos` subdirectory management |
| `backend/app/agent.py` | Agent spawning, stdout/stderr capture, status tracking |
| `backend/app/worker.py` | Background task processor (goals, agent execution, state transitions) |
| `backend/app/models.py` | Pydantic schemas: TaskState, Task, Space, View, agent modes/models |
| `backend/app/trace_parser.py` | Parse `STATUS:` fields from agent stdout, extract RunTrace (result, exit_reason, parent_run_id, memory_hit_rate, etc.) |
| `backend/app/api/tasks.py` | Task CRUD, state transitions, drag-drop reordering, lane overrides (29 KB) |
| `backend/app/api/spaces.py` | Space CRUD, repo linking, project settings |
| `backend/app/api/harnesses.py` | Harness CRUD REST endpoints (GET/POST/PUT/DELETE) with concurrency contract |
| `backend/app/harnesses/model.py` | Pydantic models with reference integrity validation (HarnessNode, HarnessEdge, Harness) |
| `backend/app/harnesses/validator.py` | DAG validation (cycle detection, self-loop rejection, reference fidelity checks) |
| `backend/app/harnesses/store.py` | HarnessStore with atomic YAML I/O to `.cronos/harnesses/<name>.yml` per space |
| `backend/app/harnesses/executor.py` | **Harness executor** — DAG interpreter, Kahn topo-sort, sequential agent invocation, fail-fast on node failure, variable scope propagation, run-state persistence |
| `backend/app/harnesses/interpolate.py` | Variable/data interpolation via `string.Template.safe_substitute` with precedence (root_vars < upstream_outputs) |
| `backend/app/harnesses/brief_composer.py` | Child-task brief composition for harness executor nodes (agent header, skill prefix, prompt inclusion) |
| `backend/app/harnesses/run_state.py` | RunState dataclass and atomic persistence (tempfile + os.replace) for harness DAG execution, reconciliation on resume |
| `backend/app/memory_store.py` | Shared context storage |
| `backend/app/git_ops.py` | `git clone/commit/push` wrappers for repo-linked spaces |
| `backend/app/goal_sync.py` | Goal state propagation |
| `frontend/src/App.tsx` | Root layout — sidebar nav + outlet (responsive mobile drawer) |
| `frontend/src/pages/BoardPage.tsx` | Kanban board — dnd-kit drag-drop, lanes by TaskState |
| `frontend/src/pages/TreePage.tsx` | Dependency DAG visualization (dagre) |
| `frontend/src/hooks/useTasks.ts` | React Query hooks for task CRUD |
| `frontend/src/api.ts` | HTTP client |

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
```

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
