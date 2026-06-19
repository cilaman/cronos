---
agent_mode: auto
agent_model: opus-4-8
claude_session_id: 1bcda427-836f-4b92-be2a-2db218452df2
created_at: '2026-06-06T12:49:44Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-06-1249-update-to-features-page
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
title: Update to Features page
type: task
updated_at: '2026-06-13T13:30:16Z'
waiting_question: null
---

# Brief

Prepare a cronos goal, that will redesign the features page so it will be more like tasks page. 
- adding of feature /fix through + on backlog lane rather than as is.
- possibility to hide lanes just as on Taskss page
- propose further optimizations
- use frontend-design skilll
- use ccv1 pipeline for subgoals
- after overall tests merge changes to main and push

# History

```
2026-06-06T12:55:18Z [agent] run=0 model=claude-opus-4-8 mode=auto agents=explore
I'll start by understanding the current Features page and Tasks page, plus how to set up a CC-v1 pipeline goal. Let me read the relevant memory and skills first.

Let me explore the current Features/Tasks pages and read the scaffold skill in parallel.

Let me read the actual current Features page and the Tasks lane-hiding implementation to ground the redesign spec.

I now have a clear picture of the gap. Current state:

- **Add flow**: an always-visible inline `FeatureComposer` form (radio Feature/Fix toggle + text input + Add) embedded under the Backlog lane (`FeaturesBoard.tsx:212`); all lanes pass `showAdd={false}`.
- **No lane hiding**: `onHideLane` is never wired (the Tasks board persists a `laneOverride` to localStorage and shows "Hidden:" restore chips).
- **Cards are inert**: `onOpen={() => {}}` — clicking a feature card does nothing.

Before I scaffold the goal, two structural decisions materially change the board layout. Let me get your call.

The question UI was dismissed without an answer, so I'll proceed with the recommended defaults: **one CC-v1 pipeline subgoal** under a root goal, including all four proposed optimizations. I'll note this clearly so you can redirect.

Let me set up task tracking and confirm the space/backend before scaffolding.

Space confirmed (`cronos-development`), and the root-goal branch resolution works for a root→subgoal structure. Now I'll write the scaffold script that creates the root goal, the CC-v1 pipeline subgoal, and its 7 phase tasks.

Now let me run the scaffold.

Scaffold succeeded. Let me verify the board structure and pipeline state.

The goal is fully wired. Verification confirms:

- **Root goal** `2026-06-06-1253-update-to-features-page` → **pipeline subgoal** `2026-06-06-1253-features-board-redesign` (correct parent) → 7 phase tasks in a clean DAG (scout→analysis→design→impl→test→{review←impl,test}→doc).
- `pipeline-state.json` initialized (`cc_version=1.0`, `status=running`, empty phases) alongside `request.md` and empty `phases-log.jsonl`.

Now the mandatory finalize step.

This is a **standalone planning/scaffold task** — it created board + pipeline state via the Cronos API (which persists itself). The git working tree shows only unrelated runtime churn (memory/traces/stats/other tasks), not source-code deliverables of mine. Per the skill's case C, there's nothing to commit.

Let me record a project memory for the board setup.

I've prepared the Cronos goal. The board now holds a root goal **"Update to Features page"** (`2026-06-06-1253-update-to-features-page`) with one CC-v1 pipeline subgoal **`features-board-redesign`** and its 7 phase tasks (scout→analysis→design→impl→test→review→doc), all dependency-wired, with `pipeline-state.json`/`request.md` initialized.

The request spec captures both required changes (R1 add feature/fix via the Backlog "+" replacing the always-on inline form; R2 hide/restore lanes like the Tasks board) plus the four optimizations (R3 clickable cards, R4 toolbar parity + reset + "No features" copy, R5 per-space persisted layout). The design and impl phases are instructed to use `/frontend-design`, and the terminal doc phase runs `/goal-finalize` to merge to main after the test phase passes.

I went with **one** pipeline subgoal (my recommended default, since the question UI was dismissed) because every change touches the same files (`FeaturesBoard.tsx`, `Lane.tsx`, `FeaturesPage.tsx`, `storage.ts`) and parallel pipelines would collide. If you'd prefer it split into multiple pipelines or want optimizations dropped, tell me and I'll restructure.

MEMORY[fact]: "Update to Features page" goal set up 2026-06-06 in cronos-development — root goal `2026-06-06-1253-update-to-features-page` + one CC-v1 pipeline subgoal `2026-06-06-1253-features-board-redesign` (slug features-board-redesign, 7 phase tasks). Redesigns Features board like Tasks board (R1 add via Backlog "+", R2 hide/restore lanes, R3 clickable cards, R4 toolbar parity/reset/"No features" copy, R5 per-space persisted layout). Branch root-driven feature/update-to-features-page; doc phase runs /goal-finalize. Setup script at workspace scaffold_features_redesign.py.

STATUS: DONE
```
