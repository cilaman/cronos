---
cc_version: "1.0"
agent: pipeline-implementor
slug: showing-commit--i1
phase: impl
status: done
confidence: 0.95
inputs_used:
  - memory:project_pipeline_implementor_agent
  - .cronos/pipeline/showing-commit/design-report-showing-commit.md
  - deploy/VPS_SETUP.md
iteration_id: I1
files_changed:
  - deploy/upgrade.sh
  - deploy/VPS_SETUP.md
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/showing-commit/impl-report-showing-commit--i1.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 12
  files_read: 3
  memory_hits: 1
  diff_lines_added: 52
  diff_lines_removed: 0
---

## Summary

Iteration I1 (infra) creates `deploy/upgrade.sh` as a new repo-tracked file containing the six-step upgrade sequence specified in the design: `git fetch/reset`, `COMMIT_SHA=$(git rev-parse --short HEAD)`, `BUILD_TIME=$(date -u ...)`, `REPO_URL` extraction via sed, `docker compose build` with all six `--build-arg` values (`BUILD_COMMIT`, `BUILD_TIME`, `BUILD_REPO_URL`, `VITE_BUILD_COMMIT`, `VITE_BUILD_TIME`, `VITE_BUILD_REPO_URL`), and `sudo systemctl restart cronos.service`. `deploy/VPS_SETUP.md` §10.1 is updated with a note that the script is now repo-tracked and a one-line `sudo install -m 755 /opt/cronos/deploy/upgrade.sh /opt/cronos/upgrade.sh` instruction. Validation passed: `bash -n` syntax-check exits 0 and grep confirms both required patterns are present.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| deploy/upgrade.sh | created | +45 / 0 | Repo-tracked upgrade script: git reset, extract build metadata, docker compose build with all 6 BUILD_ARG values, systemctl restart |
| deploy/VPS_SETUP.md | modified | +7 / 0 | §10.1 note + sudo install line to keep host copy in sync with repo-tracked script |

## Out-of-scope findings

- None.

## Assumptions

- `upgrade.sh` is called from `/opt/cronos/` (the repo root), so relative paths `docker-compose.yml` and `docker-compose.prod.yml` resolve correctly. The script uses `SCRIPT_DIR`/`REPO_ROOT` detection via `BASH_SOURCE[0]` to be robust if called from any working directory.
- The `git remote get-url origin` returns a GitHub URL in either SSH (`git@github.com:...`) or HTTPS form; the sed expression handles both. Non-GitHub remotes will produce a malformed `REPO_URL` but the build will still succeed (REPO_URL is a display-only arg in this feature).
- The six env var names (`BUILD_COMMIT`, `BUILD_TIME`, `BUILD_REPO_URL`, `VITE_BUILD_COMMIT`, `VITE_BUILD_TIME`, `VITE_BUILD_REPO_URL`) are spelled exactly as required by the cross-iteration invariant.
- `set -euo pipefail` ensures any failure in the upgrade sequence aborts immediately — consistent with upgrade.sh being operator-facing infrastructure.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Validation command to rerun:
```
bash -n /data/spaces/cronos-development/deploy/upgrade.sh && grep -E 'git rev-parse --short HEAD|date -u' /data/spaces/cronos-development/deploy/upgrade.sh
```

Edge cases uncovered during implementation:
- The script uses `BASH_SOURCE[0]`-based directory detection so it resolves the repo root correctly regardless of the caller's working directory. This is important because `upgrade-webhook.py` (out of scope, not modified) invokes `upgrade.sh` via subprocess — the cwd may differ from `/opt/cronos`.
- The `sudo systemctl restart` requires the cronos-upgrade sudoers rule from §10.2 to exist first. The VPS_SETUP.md §10.2 already documents this; no change needed.
- `docker compose` (V2 plugin syntax) is used, not `docker-compose` (V1). The existing VPS_SETUP.md uses V2 consistently, so this is correct.

Out-of-scope findings to prioritize in next review cycle: none — I1 scope is self-contained infra files.
