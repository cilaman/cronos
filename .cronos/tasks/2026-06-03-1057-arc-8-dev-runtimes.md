---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-03T10:57:16Z'
depends_on: []
id: 2026-06-03-1057-arc-8-dev-runtimes
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: Arc 8 dev runtimes
type: goal
updated_at: '2026-06-03T10:57:16Z'
waiting_question: null
---

# Brief

# Arc 8 — Spaces as Dev Environments

Umbrella goal for Arc 8. Turns a Cronos space into a runnable product: each
space declares a `dev_runtime` in its metadata, and Cronos can Run / Stop /
Restart the space's dev server as a managed subprocess, allocate non-colliding
port ranges, stream stdout/stderr to a UI log panel, and poll a `health_url`
to surface a clickable link once the server is up. Production is out of scope —
`prod_url` is display-only.

## Subgoals (four CC-v1 pipelines, single shared branch)

- **SG1** `arc8-dev-schema`: dev_runtime space schema + port allocator (no process spawning)
- **SG2** `arc8-dev-process`: process manager + health poller
- **SG3** `arc8-dev-api`: dev-runtime REST API + SSE log stream
- **SG4** `arc8-dev-ui`: DevRuntimePanel + sidebar running indicator

All four subgoals share `feature/arc-8-dev-runtimes`. SG4's doc phase runs
`/goal-finalize` to merge the whole arc to main. SG1-SG3 doc phases commit
only (no merge).

## Dependency chain

SG1 → SG2 (SG2 scout depends_on SG1 doc)
SG2 → SG3 (SG3 scout depends_on SG2 doc)
SG3 → SG4 (SG4 scout depends_on SG3 doc)

# History
