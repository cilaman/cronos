---
agent_mode: auto
agent_model: opus
claude_session_id: 2fb61c94-d564-477a-a2a5-99ebaa55dc2f
created_at: '2026-06-07T11:27:59Z'
depends_on:
- 2026-06-07-1127-analyst-feature-detail-panel
feature_key: null
feature_state: null
id: 2026-06-07-1127-architect-feature-detail-panel
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1127-sg2-featuredetail-panel-board-wiring
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: architect – feature-detail-panel
type: task
updated_at: '2026-06-15T11:30:16Z'
waiting_question: null
---

# Brief

CC-v1 architect phase for: SG2 FeatureDetail Panel + Board Wiring.

Scout report: `.cronos/pipeline/feature-detail-view/scout-report-feature-detail-view.md`

Scope:
- `frontend/src/components/FeatureDetail.tsx` (new file)
- `frontend/src/components/FeaturesBoard.tsx` — wire onOpen to write ?feature=<id> to URL
- `frontend/src/pages/FeaturesPage.tsx` — mount FeatureDetail when ?feature param present
- `frontend/src/components/Board.tsx` — fix shared-backlog card click to deep-link to ?feature=<id>

The FeatureDetail panel must use the hooks from SG1 (useFeature, usePatchFeature,
useProcessFeature, useSetRealize). Mirror the `Detail.tsx` + `Board.tsx:55-322` pattern
for panel lifecycle, URL param management, and onClose behavior.

Agent contract: `.claude/agents/pipeline-architect.md`
Artifact: `.cronos/pipeline/feature-detail-view/architect-report-feature-detail-panel.md`

Then run: /pipeline-gate

# History

```
2026-06-08T10:34:55Z [agent]
Let me check the current state of the codebase to give the architect proper context.

The SG1 impl claimed it added 4 methods to `api.ts` and `FeatureRead` to `types.ts`, but the commit only modified `useFeatures.ts`. That's important context for the architect — SG2 needs to either close that gap or stack on top of it. Now I'll spawn the architect agent.

Architect succeeded. Let me verify the artifact exists and then run the gate.

Verifier passes (PROCEED). Now I'll invoke the pipeline-gate skill to record this and emit STATUS.

I need to handle the slug carefully — the architect emitted a fan-out slug `feature-detail-view--feature-detail-panel`, but the gate skill default for `phase=design` is `SLUG=${GOAL_SLUG}`. I'll override SLUG to match the actual canonical artifact.

Verifier passed (exit 0). Now run the state writer to record the gate.

Both verify and state writer succeeded. Now I need to commit per task workflow (the goal-task-commit pattern), then finalize.

This is a goal child task (parent: `sg2-featuredetail-panel-board-wiring`). Delegating to goal-task-commit.

The feature branch never got created (SG1 tasks went straight to main). I'll follow that precedent — commit to main directly via the main worktree.

Only this task's 3 files are staged. Now commit and push.

Pushed. Now writing memory and emitting STATUS.

The workspace-specific path requires permissions I don't have. I'll write to the project-root memory path (which the system prompt says already exists and is writable).

Memory written and indexed. All steps complete: design report verified (exit 0, PROCEED), state recorded, committed and pushed to main (`184e8d6`), memory persisted.

gate PASS — design / feature-detail-view
  artifact: .cronos/pipeline/feature-detail-view/design-report-feature-detail-view--feature-detail-panel.md
  normalize: 3 fix(es) applied (dropped 3 unknown free-text strategies)

MEMORY[fact]: CC-v1 architect emitted `design-report-feature-detail-view--feature-detail-panel.md` for SG2 (5 iters, DAG: I1 → I2/I4 → I3 → I5; 5 risks, 1 high mitigated). Gate PROCEED, verify exit 0. Commit `184e8d6` on main.
MEMORY[observation]: SG1 impl-report claimed it added FeatureRead + 4 api methods to types.ts/api.ts, but commit `781d634` only touched useFeatures.ts + its test. Hooks reference api.getFeature(...) at runtime — main is broken at runtime; tests pass only via vi.mock('../api'). The design DAG closes the gap with I1 as mandatory layer-0.
MEMORY[reference]: Workspace memory writes (`/root/.claude/projects/<workspace-slug>/memory/...`) are blocked by sensitive-file permissions; only the space-root path `/root/.claude/projects/-data-spaces-cronos-development/memory/` is writable here.

STATUS: DONE
```
