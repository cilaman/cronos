---
cc_version: "1.0"
agent: pipeline-reviewer
slug: g03-non-root-docker--attempt1
phase: review
status: done
confidence: 0.85
inputs_used:
  - memory:project-remediation-board-setup
  - .cronos/pipeline/g03-non-root-docker/design-report-g03-non-root-docker.md
  - .cronos/pipeline/g03-non-root-docker/impl-report-g03-non-root-docker--i1.md
  - .cronos/pipeline/g03-non-root-docker/test-report-g03-non-root-docker.md
  - backend/Dockerfile
  - backend/docker-entrypoint.sh
  - docker-compose.yml
  - frontend/Dockerfile
  - deploy/EGRESS_ALLOWLIST.md
  - backend/app/worker.py
  - backend/app/git_ops.py
  - docker-compose.prod.yml
outputs_produced:
  - .cronos/pipeline/g03-non-root-docker/review-report-g03-non-root-docker--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 14
  files_read: 11
  memory_hits: 1
  diff_lines_reviewed: 206
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: high
    file: backend/docker-entrypoint.sh:27
    evidence: "Entrypoint chowns only /data: `chown -R --from=0 cronos:cronos /data`. The named volume `claude_config` mounts at /home/cronos/.claude, which the Dockerfile never creates (only `mkdir -p /data`). A fresh named volume is created root:root by Docker, and an existing claude_config (previously at /root/.claude) keeps its root ownership. cronos (1001) then cannot write CLI sessions, backups, or memory under CLAUDE_PROJECTS_DIR=/home/cronos/.claude/projects."
    blocking: true
    suggested_action: "In backend/docker-entrypoint.sh, before `exec gosu cronos`, add an idempotent `chown -R cronos:cronos /home/cronos/.claude 2>/dev/null || true` (it runs as root). Optionally also `mkdir -p /home/cronos/.claude` in backend/Dockerfile owned by cronos so fresh volumes initialise correctly. Both files are in scope (I1/I2)."
  - id: F2
    severity: high
    file: frontend/Dockerfile:24
    evidence: "`USER caddy` was never validated: docker is unavailable in the impl and test environments. The implementor's own probe `docker run --rm caddy:2-alpine id caddy` returned `docker: command not found` / `No caddy user found` (impl trace turn 24), then the `USER caddy` line was added on an unverified memory claim. The official caddy:2-alpine image runs as root and does not ship a `caddy` user; if absent, `docker build` fails with `unable to find user caddy`, breaking the frontend image entirely."
    blocking: true
    suggested_action: "Verify on a real docker host: `docker run --rm caddy:2-alpine id caddy`. If the user is absent, add `RUN addgroup -g 1000 caddy && adduser -D -u 1000 -G caddy caddy` (alpine) in frontend/Dockerfile before `USER caddy`, or switch to `USER 1000`. frontend/Dockerfile is in scope (I4)."
  - id: F3
    severity: medium
    file: backend/Dockerfile:46
    evidence: "impl-report sets `validation_command_passed: true` for I1, but its docker build+run assertions (id!=0, claude exec, /app+/data owned by cronos, cap_drop) could not have run — docker is absent from the impl/test envs (impl trace: 'I3 validation: docker compose config not available without docker, but validate content'). The tester gate ran pytest only (2697 passed, 85.18%); no infra path is exercised by pytest. Every G03 runtime acceptance criterion (UID!=0, end-to-end non-root task, egress block) is still unverified by execution."
    blocking: false
    suggested_action: "Run the I1/I3/I4 validation_commands on a docker-capable host and record the output in .cronos/qa/g03-egress-verification.md (the file deploy/EGRESS_ALLOWLIST.md already references). Treat the G03 acceptance as provisional until that smoke passes."
  - id: F4
    severity: medium
    file: deploy/EGRESS_ALLOWLIST.md:1
    evidence: "The review brief requires security-sensitive G03 changes to include a threat note (what attack this closes and what it does NOT close). No such note exists in the diff; EGRESS_ALLOWLIST.md documents mechanism + verification but not the threat model."
    blocking: false
    suggested_action: "Add a 'Threat model' section to deploy/EGRESS_ALLOWLIST.md stating closes: root code-execution blast radius from prompt injection (now constrained non-root UID 1001, cap_drop ALL, no-new-privileges, egress allowlist); does NOT close: in-container non-root RCE, data exfil over allowed hosts (api.anthropic.com/github.com), host-kernel escapes, or the manual/unenforced-until-operator-applies nature of R8. In scope (I5)."
  - id: F5
    severity: low
    file: .cronos/pipeline/g03-non-root-docker/impl-report-g03-non-root-docker--i1.md:8
    evidence: "All five design iterations (I1–I5) were collapsed into one impl report tagged `iteration_id: I1`. files_changed lists 5 files but I1.scope_files is only [backend/Dockerfile]; per-iteration `files_changed ⊆ scope_files` is bypassed. The cross-iteration union check still passes (no actual scope escape), so substance is fine — contract hygiene only."
    blocking: false
    suggested_action: "No code change required. For future multi-iteration goals, emit one impl-report per iteration (--i1..--i5) so the per-iteration scope gate is meaningful."
---

## Summary

Scope conformance: PASS — the observed changed set (backend/Dockerfile, backend/docker-entrypoint.sh, docker-compose.yml, frontend/Dockerfile, deploy/EGRESS_ALLOWLIST.md) is exactly the union of the design's `iterations[].scope_files`; no scope escape, no Python/TypeScript/Caddyfile touched, and R6 (git_ops `_auth_env()` lines 96–115) is correctly UID-agnostic so the PAT injection needs no edit. Verdict is **needs_fix** for two high blocking issues: (F1) the persisted `claude_config` volume at /home/cronos/.claude is never chowned, so the non-root cronos process cannot write CLI sessions/memory/backups — this directly defeats the "full task completes end-to-end as non-root" acceptance criterion; and (F2) `USER caddy` is unverified and likely invalid because docker was absent in both the impl and test environments (the implementor's own `id caddy` probe returned "No caddy user found") and the official caddy:2-alpine image has no caddy user — if so the frontend build breaks. The pytest gate is green (2697p/0f, 85.2%) but exercises zero infra, so all G03 runtime criteria remain unverified by execution (F3). Both blockers are repairable within the existing scope_files, so this routes back to the implementor rather than failing.

## Findings

- **F1** (high, blocking) — `backend/docker-entrypoint.sh:27`: only /data is chowned; the /home/cronos/.claude named volume stays root-owned → cronos can't write sessions/memory/backups.
- **F2** (high, blocking) — `frontend/Dockerfile:24`: `USER caddy` unverified (docker absent; probe returned "No caddy user found"); breaks build if the user doesn't exist in caddy:2-alpine.
- **F3** (medium) — `backend/Dockerfile:46`: I1 `validation_command_passed: true` not substantiated; docker build/run never executed; pytest covers no infra; runtime acceptance unverified.
- **F4** (medium) — `deploy/EGRESS_ALLOWLIST.md:1`: required threat note (closes / does-not-close) missing.
- **F5** (low) — `impl-report ...--i1.md:8`: five iterations collapsed into one I1 report; per-iteration scope gate bypassed (union still clean).

## Verdict

needs_fix. Two high-severity blockers (F1 volume ownership, F2 unverified `USER caddy`) prevent the goal's non-root acceptance criteria from being met; both are fixable inside the current scope_files, so the implementor should re-run, not escalate.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union (backend/Dockerfile, backend/docker-entrypoint.sh, docker-compose.yml, frontend/Dockerfile, deploy/EGRESS_ALLOWLIST.md).
- Docker named volumes initialise root-owned when the image lacks the mount-path directory, and a renamed mountpoint on an existing volume retains prior ownership — basis for F1.
- The official caddy:2-alpine image runs as root with no `caddy` user — basis for F2; flagged for host verification rather than asserted as certain since docker is unavailable here.
- R3 override confirmed real: `backend/app/worker.py:43` reads `os.environ.get("CLAUDE_PROJECTS_DIR", "/root/.claude/projects")`, and compose sets `CLAUDE_PROJECTS_DIR: /home/cronos/.claude/projects` — correct, but its target lives inside the F1-affected volume.

## Open questions

- Does caddy:2-alpine ship a `caddy` user on the deployed registry tag? Resolves F2 to either "already fine" or "build-breaking" once run on a docker host.

## Next consumer brief

Implementor: re-run with two in-scope fixes. (1) F1 — add an idempotent `chown -R cronos:cronos /home/cronos/.claude` in backend/docker-entrypoint.sh before `exec gosu cronos`, and/or `mkdir -p /home/cronos/.claude` owned by cronos in backend/Dockerfile. (2) F2 — verify `docker run --rm caddy:2-alpine id caddy` on a docker host; if the user is absent, create it in frontend/Dockerfile (`adduser -D -u 1000 caddy`) or use `USER 1000`. Then actually run the I1/I3/I4 validation_commands on a docker-capable host (F3) and record results in .cronos/qa/g03-egress-verification.md. Recommended while in I5 scope: add the F4 threat note.

Threat note (for the record, what G03 closes / does NOT close): **Closes** — collapses the prompt-injection blast radius from root code-execution to a constrained non-root identity (UID 1001), removes all Linux capabilities (`cap_drop: [ALL]`), blocks setuid privilege re-escalation (`no-new-privileges:true`), and constrains exfiltration to an explicit egress allowlist. **Does NOT close** — non-root RCE inside the container, data exfiltration over already-allowed hosts (api.anthropic.com, github.com), host-kernel / container-runtime escapes, or any egress at all until an operator actually applies Mechanism A/B (R8 is documentation + manual verification, not enforced by compose).
