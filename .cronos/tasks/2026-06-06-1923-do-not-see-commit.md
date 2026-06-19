---
agent_mode: auto
agent_model: default
claude_session_id: 1758deb8-dba7-41d5-be1e-6899514e1c77
created_at: '2026-06-06T19:23:37Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-06-1923-do-not-see-commit
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Do not see commit
type: task
updated_at: '2026-06-13T20:30:16Z'
waiting_question: null
---

# Brief

I cannot see commit info anywhere (
2026-05-31-1507-showing-commit)

# History

```
2026-06-06T19:30:35Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=explore
Let me investigate the commit info feature and why it might not be visible.

Let me look at the BuildInfo component and how it's rendered in the sidebar.

Let me check how the Docker build sets these environment variables.

Let me check the upgrade script and how BUILD_COMMIT is set in production.

Let me check the systemd service definition.

Found the bug. The docker-compose files set `BUILD_COMMIT: ${BUILD_COMMIT:-}` in the backend's `environment:` section. When `BUILD_COMMIT` isn't in the host shell environment (which it never is at service start time — upgrade.sh stores it as `COMMIT_SHA`, not `BUILD_COMMIT`), Docker Compose resolves that to an empty string and sets it in the container, overriding the baked-in `ENV BUILD_COMMIT=$BUILD_COMMIT` from the Dockerfile.

The fix: remove `BUILD_COMMIT`/`BUILD_TIME`/`BUILD_REPO_URL` from the runtime `environment:` sections. They're already baked into the image at build time — no need to set them again at runtime.

Now let me verify the changes look right:

The changes look correct. Now let me commit and push, then upgrade.

Clean, minimal diff. Now commit and push, then upgrade.

Wait, that committed to the wrong branch. Let me check.

My commit landed on the already-merged `feature/update-to-features-page` branch. I need to get it onto main. Let me cherry-pick it.

Good - the main worktree still has the bug. Let me apply the fix there and commit directly to main.

6 files changed is unexpected - let me verify what was included.

The commit accidentally included pre-staged changes from another task that would revert a bug fix. I need to undo this and recommit cleanly.

Now only the two compose files are staged. Commit cleanly.

Clean 2-file commit. Now push to origin/main and upgrade.

Pushed. Now upgrade.

STATUS: DONE

The fix is deployed. The root cause: `docker-compose.yml` and `docker-compose.prod.yml` both set `BUILD_COMMIT: ${BUILD_COMMIT:-}` in the backend's `environment:` section. At service start time `BUILD_COMMIT` isn't in the host shell, so this resolved to an empty string and overrode the value baked into the image by the Dockerfile `ENV` instruction. The `/api/info` endpoint returned an empty string for `commit_sha`, which `BuildInfo.tsx` treated as falsy and rendered nothing.

Fix: removed `BUILD_COMMIT`, `BUILD_TIME`, and `BUILD_REPO_URL` from the runtime `environment:` in both compose files. They're already baked into the image by `upgrade.sh`'s `--build-arg` flags, so the baked values now take effect correctly after next upgrade.
```
