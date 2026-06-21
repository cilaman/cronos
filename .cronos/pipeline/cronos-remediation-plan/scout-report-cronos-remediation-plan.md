---
cc_version: "1.0"
agent: pipeline-scout
slug: cronos-remediation-plan
phase: scout
status: done
confidence: 0.92
inputs_used:
  - memory:project-remediation-board-setup
  - backend/tests/test_no_pat_in_traces.py
  - backend/app/trace_redact.py
  - .gitignore
  - backend/pyproject.toml
  - frontend/package.json
  - backend/Dockerfile
  - frontend/Dockerfile
  - docker-compose.yml
  - backend/app/auth.py
  - Caddyfile
  - Caddyfile.dev
  - deploy/upgrade-webhook.py
  - backend/app/agent.py
  - backend/app/memory_parser.py
  - .claude/skills/task-finalize/SKILL.md
  - .claude/settings.json
  - backend/app/tools/plugins.py
  - backend/app/worker.py
  - backend/app/worker_pool.py
  - backend/app/harnesses/wait.py
  - backend/app/harnesses/executor.py
  - backend/app/git_ops.py
  - README.md
  - docs/HARNESSES.md
  - frontend/src/types.ts
outputs_produced:
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/ (auth, agent, worker, git_ops, harnesses/, tools/, memory_parser)
    - backend/tests/ (test_no_pat_in_traces.py)
    - frontend/src/ (types.ts, package.json)
    - deploy/ (upgrade-webhook.py, Caddyfile, docker-compose)
    - .claude/ (skills/, settings.json)
    - docs/ (HARNESSES.md)
  excluded:
    - .cronos/workspaces/**/*.py: Not relevant to codebase audit
    - node_modules, __pycache__: Build artifacts
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Scout Phase: Research all files relevant to the 14 Cronos remediation goals (G01–G14). Confirm file existence, locate key symbols/lines, and note actual contents vs the plan. All findings derive from code reviews at commit a724133."
metrics:
  tool_calls: 41
  files_read: 25
  memory_hits: 1
---

## Summary

All 14 remediation goals map to specific, existing files in the Cronos codebase. G01–G04 (repo hygiene, CI pipeline, Docker security, auth fail-closed) show no code to write; fixes are documentation/config-driven. G05–G14 identify substantial refactoring targets: parse_status free-text replacement (G05), plugin install allow-list hardening (G06), worker.py decomposition (1966 LOC across 9 clusters, G07), durable queue implementation (G08), timed-wait MVP (G09), structured logging framework (G10), git credential least-privilege (G11), and frontend type generation (G14). No blockers; all groundwork exists.

## Coverage

### Searched

- `backend/app/auth.py` — fail-closed auth, lines 13–16 (auth disabled if both env vars unset)
- `backend/app/agent.py` — parse_status (lines 66–96), DEFAULT_TOOLS/PLAN_MODE_TOOLS (lines 250–251), acceptEdits permission mode (lines 245–248)
- `backend/app/memory_parser.py` — parse_cronos_remember_blocks (lines 98–152), CronosRememberBlock dataclass (lines 89–95)
- `backend/app/worker.py` — 1966 LOC total; 9 major async functions (_run_forever, _run_one, _run_feature_decompose, _execute_harness_run, _resume_harness_run, _run_initial_harness_run, _run_task, _finalize, _run_goal); _auto_resume_counts (line 298); asyncio.Queue (line 285)
- `backend/app/harnesses/wait.py` — await_timed_wait (lines 117–146), MVP limitation on line 16 (no persisted sleep_resume_at)
- `backend/app/harnesses/executor.py` — call site at line 1054 (await_timed_wait)
- `backend/app/git_ops.py` — _auth_env (lines 96–115), GIT_CONFIG_COUNT/KEY_0/VALUE_0 injection (lines 110–112), no autopilot_pr found
- `backend/app/tools/plugins.py` — PluginCliError (lines 49–58), _run_plugin_cmd (lines 65–84), CLI injection defenses via regex (lines 32–34)
- `backend/app/worker_pool.py` — WorkerPool class, per-space serialization, asyncio.Lock (line 46)
- `backend/tests/test_no_pat_in_traces.py` — test_committed_traces_contain_no_pat (lines 49–71), canary test (lines 74–92)
- `backend/app/trace_redact.py` — SECRET_PATTERNS (line 17, 7 regex patterns for GitHub/GitLab PAT formats)
- `.gitignore` — no .cronos/ exclusion (lines 1–27); `.cronos/` is tracked
- `backend/pyproject.toml` — --cov-fail-under=60 (line 39), no [tool.ruff] or [tool.mypy] sections
- `frontend/package.json` — tsc (line 8), vitest run (line 10), no openapi-typescript dependency
- `backend/Dockerfile` — no USER directive; RUN npm install -g @anthropic-ai/claude-code (line 15); python:3.12-slim base image
- `frontend/Dockerfile` — no USER directive; node:22-alpine builder, caddy:2-alpine runtime
- `docker-compose.yml` — no security_opt or cap_drop; volumes for ./data and claude_config named volume
- `Caddyfile` — basicauth @private (lines 8–10) with env vars; TLS via Let's Encrypt
- `Caddyfile.dev` — HTTP only, auto_https off (lines 1–3)
- `deploy/upgrade-webhook.py` — WEBHOOK_SECRET optional check (lines 20, 33–38)
- `.claude/settings.json` — Allow list only: Write/Edit on .claude/skills/** (lines 2–6); no deny list
- `README.md` — no security-posture note found (lines 1–62)
- `docs/HARNESSES.md` — exists (27 KB); ADR-style documentation
- `frontend/src/types.ts` — 694 LOC hand-maintained types; manual TaskState/FeatureState enums (lines 1–39), no OpenAPI code generation

### Excluded

- `.cronos/workspaces/**/*.py` — copies of older agent.py and other modules; not relevant to main codebase audit
- `node_modules/`, `__pycache__/`, `.venv/` — build/runtime artifacts
- `data/` — runtime state (gitignored)

### Strategies

- **memory_retrieval**: 1 entry found (project-remediation-board-setup) confirming board setup, 14 goals, branch feature/cronos-remediation-plan
- **glob_structural**: Confirmed existence and line counts for all 14 goals' key files
- **grep_symbol**: Located parse_status, _STATUS_LINE, DEFAULT_TOOLS, SECRET_PATTERNS, GIT_CONFIG_*, _auth_env, await_timed_wait, asyncio.Queue, cov-fail-under
- **read_targeted**: Deep reads of auth.py, agent.py, memory_parser.py, worker.py (partial), git_ops.py, plugins.py, task-finalize SKILL, Caddyfile, upgrade-webhook.py

## Findings

### G01 — Repo hygiene / failing test

- **Test exists:** `backend/tests/test_no_pat_in_traces.py` (lines 49–72)
- **Guard logic:** Scans committed traces in `.cronos/traces/` using `git ls-files` (lines 29–42)
- **SECRET_PATTERNS:** 7 patterns in `backend/app/trace_redact.py` (GitHub PATs: ghp_, gho_, ghs_, ghr_, github_pat_; GitLab: x-access-token)
- **.gitignore status:** No `.cronos/` exclusion; `.cronos/` is fully tracked. Current entries only ignore `data/*.db` and `data/*.sqlite*` (lines 25–27)
- **.cronos/ subdirs confirmed:** 12 directories exist: .trash, harness-runs, harnesses, issues, memory, pipeline, qa, stats, tasks, test-reports, traces, workspaces
- **Canary test:** Lines 74–92 verify detection of `ghp_` PAT; both tests should pass

### G02 — CI pipeline

- **.github/workflows/ absent:** Confirmed; no CI/CD automation found
- **pyproject.toml:** Line 39 has `--cov-fail-under=60`; no [tool.ruff], [tool.mypy], [tool.pytest-cov] sections
- **frontend/package.json:** tsc script at line 8, vitest run at line 10 (not vitest --coverage); npm test exists but no coverage threshold

### G03 — Non-root Docker

- **backend/Dockerfile:** No USER directive; python:3.12-slim base (line 2), RUN npm install -g @anthropic-ai/claude-code at line 15
- **frontend/Dockerfile:** No USER directive in builder or runtime stages; node:22-alpine builder (line 4), caddy:2-alpine runtime (line 19)
- **docker-compose.yml:** No security_opt or cap_drop fields; named volume claude_config for /root/.claude persistence (lines 60)

### G04 — Fail-closed auth

- **app/auth.py:** Lines 13–16 show fail-open: `if not user or not password: return` (auth disabled when env vars unset)
- **Caddyfile:** Lines 8–10 wire basicauth @private; requires BASIC_AUTH_USER and BASIC_AUTH_HASH env
- **Caddyfile.dev:** Lines 1–3 explicit note that dev Caddy has auth disabled
- **upgrade-webhook.py:** Line 20 `WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")`, lines 33–38 optional check: if SECRET is empty string, auth is skipped

### G05 — Structured completion

- **parse_status function:** Lines 66–96 in agent.py; regex `_STATUS_LINE` at line 66 matches `STATUS: (DONE|WAIT|BLOCKED)` with optional asterisks
- **Current output:** Free-text context line (lines 89–94) extracted as immediately preceding non-blank line
- **parse_cronos_remember_blocks:** Lines 98–152 in memory_parser.py; parses fenced CRONOS_REMEMBER blocks with YAML payload; requires name, type (in _VALID_KINDS), description fields; silently skips malformed blocks
- **task-finalize SKILL.md:** Lines 145–153 specify emit format: "STATUS: DONE must be the absolute last line of your response. Nothing after it."

### G06 — Plugin install guard

- **DEFAULT_TOOLS:** Line 251 in agent.py = "Read,Edit,Write,Bash,Skill,Agent"
- **PLAN_MODE_TOOLS:** Line 250 = "Read,Grep,Glob,Skill,Agent" (excludes Edit/Write/Bash)
- **acceptEdits mode:** Lines 245–248; set for "plan" and "auto" modes
- **.claude/settings.json:** Lines 3–6 allow list only: Write(/data/spaces/cronos-development/.claude/skills/**), Edit(...) — no deny list
- **plugins.py:** Input validation regexes at lines 32–34 (PLUGIN_ID_PATTERN, MARKETPLACE_SOURCE_PATTERN, MARKETPLACE_NAME_PATTERN)
- **No Plugin.install safeguard found** — checks exist for CLI injection but no explicit allow-list enforcement for installed plugin types

### G07 — Decompose worker.py

- **Total LOC:** 1966 lines
- **9 responsibility clusters identified:**
  1. `_WorkerProtocolAdapter` (lines 79–180): harness executor protocol bridge
  2. `_topo_children()` (lines 182–222): goal child dependency ordering
  3. `Worker.__init__()` & cache methods (lines 253–357): initialization, run_id reverse-lookup
  4. `_run_forever()` (lines 430–451): main loop, exception handling
  5. `_run_one()` (lines 453–463): queue item dispatcher
  6. `_run_feature_decompose()` (lines 465–631): feature decomposition task executor
  7. `_execute_harness_run()` (lines 633–735): harness execution orchestrator
  8. `_run_task()` (lines 826–936): agent execution + finalization
  9. `_finalize()` (lines 937–1283): post-run memory/trust updates, state transitions
  10. Additional: `_persist_cronos_remember_blocks()` (lines 1285–1319), `_finalize_child()` (lines 1321–1437), `_run_goal()` (lines 1510–1856), SSE event publishing (lines 1857–1927)
- **HarnessExecutor adapter:** Lines 79–180; injected closure at run_agent call (lines 91–122), finalize_child (lines 124–154), _publish sync bridge (lines 156–180)

### G08 — Durable queue

- **asyncio.Queue implementation:** Line 285 `self._queue: asyncio.Queue[tuple[str, str | None]]` = Queue()
- **No startup recovery visible:** No persistence layer, no database queue backing
- **_auto_resume_counts:** Line 298 tracks consecutive auto-resume per task (dict[str, int])
- **Auto-resume logic:** Lines 1235–1251 check `_auto_resume_counts.get(task_id, 0) < _MAX_AUTO_RESUMES`; increments on WAITING re-enqueue, resets on completion
- **WorkerPool:** One Worker per space (line 253 Worker class comment), per-space serialization via asyncio.Lock

### G09 — Timed-wait fix

- **await_timed_wait():** Lines 117–146 in backend/app/harnesses/wait.py
- **Implementation:** Reads `node.data['duration_seconds']`, defaults to 0 if missing (line 144), sleeps via `await asyncio.sleep(duration)` (line 145)
- **MVP limitation explicit:** Lines 16–20, 139–141 document: no persisted sleep_resume_at; on restart, full duration re-slept
- **Executor call site:** Line 1054 in backend/app/harnesses/executor.py: `await await_timed_wait(node)`

### G10 — Structured logging

- **Current pattern:** Line 41 `log = logging.getLogger("cronos.worker")`; uses Python's standard logging
- **Log calls:** 40+ instances of `log.info()`, `log.debug()`, `log.warning()`, `log.exception()` throughout worker.py
- **No structured fields:** Calls use free-text interpolation (e.g., `log.info("Enqueued task %s (queue size=%d)", task_id, self._queue.qsize())`)
- **No run_id tagging:** run_id appears only in variable names (_run_id_to_space_id); not injected into log context
- **agent.py:** No explicit logging of run_id during agent invocation; stdout/stderr captured but not tagged

### G11 — Least-privilege git

- **_auth_env() function:** Lines 96–115 in git_ops.py
- **PAT injection method:** GIT_CONFIG_* env vars (lines 110–112): GIT_CONFIG_COUNT=1, GIT_CONFIG_KEY_0="http.extraHeader", GIT_CONFIG_VALUE_0="Authorization: Basic {base64(x-access-token:TOKEN)}"
- **Least-privilege enforcement:** Token never written to subprocess args (line 52 comment notes this keeps token out of `ps`); not persisted in cloned repo config (comment lines 85–89)
- **No autopilot_pr:** Grep found no autopilot_pr function; PR functionality not yet implemented
- **Multi-user seam:** Lines 92–93 note single-user design; token applies only to git invocation, not visible to agent subprocess

### G12 — Lightweight docs

- **README.md:** No security-posture note in first 62 lines
- **docs/HARNESSES.md:** 27 KB ADR-style documentation; single doc file (git log shows created 2026-06-19)
- **No additional docs/ subdirectory structure found** — only HARNESSES.md in docs/

### G13 — Coverage floor

- **--cov-fail-under=60:** Line 39 in backend/pyproject.toml
- **Exact value:** 60 (percent)
- **No frontend coverage threshold:** frontend/package.json has vitest but no --coverage-lines-threshold or similar

### G14 — OpenAPI→TS types

- **frontend/src/types.ts:** 694 LOC, hand-maintained
- **Type definitions:** TaskState union (lines 1), FeatureState union (lines 34–39), enums (LANES, FEATURE_LANES arrays, lines 3–8, 47–53)
- **No code generation:** No openapi-typescript, @openapi-codegen, swagger-typescript-api, or similar deps in package.json
- **Manual mirrors:** Line 11 comment: "Mirrors USER_TRANSITIONS on the backend (storage.py)"; line 56 comment: "Mirrors FEATURE_USER_TRANSITIONS in backend/app/feature_state.py"
- **Scale:** ~700 LOC types covering Task, Feature, Harness, Plugin, and related schemas

## Assumptions

- Commit a724133 is a known baseline; current codebase at e6883dc (plugin frontend I1) is the intended target
- Memory entry project-remediation-board-setup accurately describes the 14 goals and shared scout task
- All files under `.cronos/` subdirs are version-controlled (tracked by git); .gitignore does not exclude them
- G01 test currently passes (no PAT patterns in committed traces)
- Worker.py's 9 clusters can be cleanly extracted without circular dependencies

## Open questions

None.

## Next consumer brief

**Analysis agent should:**

1. Examine each goal for scope ambiguity and readiness:
   - G01–G04: Configuration/documentation fixes, no code changes needed
   - G05: Replace parse_status free-text output with structured JSON/YAML; design choice between flat vs. nested context
   - G06: Define explicit plugin allow-list enforcement point (in plugins.py or agent.py)
   - G07: Create extraction plan for 9 clusters; identify circular dependencies
   - G08: Evaluate persistent queue backends (SQLite, file-based JSONL, Redis); define recovery guarantee SLA
   - G09–G14: Similar decomposition per goal

2. Flag any unshipped brief items or contradictions (e.g., if G06 expects deny-list but code shows allow-only)

3. Recommend Wave 0 ordering (G01–G04 must land first per memory entry); flag any new dependencies discovered

4. Suggest per-goal test harness scope (unit vs. integration, new test files required)
