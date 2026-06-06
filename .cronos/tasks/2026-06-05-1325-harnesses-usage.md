---
agent_mode: auto
agent_model: opus-4-8
claude_session_id: feb51bf6-cacf-4199-a2b6-d722870c123b
created_at: '2026-06-05T13:25:53Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-05-1325-harnesses-usage
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
state: active
title: Harnesses usage
type: task
updated_at: '2026-06-05T23:35:31Z'
waiting_question: null
---

# Brief

I am very very confused from the implementation of Harness functionality. Currently I am not able to use it in Cronos, because I can edit a graph, but I cannot connect it to real agents, I cannot use variables, add values to the harness graph, nothing. 

Please prepare me a thorough full MD documentation to How to use Harnesses in Cronos on Real life example.

# History

```
2026-06-05T15:15:37Z [agent] run=0 model=<synthetic> mode=auto
API Error: 529 Overloaded. This is a server-side issue, usually temporary — try again in a moment. If it persists, check status.claude.com.

(exit code 1; stderr tail: )
```

```
2026-06-05T16:44:20Z [user]
Try again
```

```
2026-06-05T16:50:02Z [agent] run=1 model=claude-opus-4-8 mode=auto
I'll research the harness implementation thoroughly so the documentation reflects how it actually works, not how it's supposed to work. Let me start by reading the core modules.

Now the executor and the frontend editor pieces, since the user's confusion is about the UI flow for connecting agents and using variables.

This is revealing — the UI writes `config.agent_ref`/`config.prompt` but the backend reads `data["agent_ref"]`/`data["prompt_template"]`. Let me check the mapping layer to see if/how these reconcile.

Critical contract mismatches are emerging (frontend `config`/`label`/`ports[]` vs backend `data`/`condition`/`ports{}`). I need to confirm whether `api.ts` translates these before I document anything. Let me read the API client, router, store, and editor.

I've confirmed several frontend/backend contract mismatches. Let me verify the most critical one empirically — whether the frontend node shape (`config`, `ports: []`) even survives Pydantic deserialization — and read the remaining pieces (store YAML shape, node handle ids, API client).

Confirmed: the frontend sends `ports` as a list but the backend requires a dict — newly dragged nodes will 422 on save. Let me verify the empty-list case and produce a known-good YAML, plus read the validator/decision/wait rules so my examples are accurate.

Let me read the decision grammar, the run trigger/worker wiring, and the API client to confirm no field translation happens client-side.

Let me confirm how the worker actually links a triggered run task back to the HarnessExecutor — the run task only stores the harness name in its title, which looks suspicious.

Let me read the worker's harness-run resolution logic to document how a triggered run finds its harness.

The worker's `_tools_resolver` is hardcoded to return `None` (line 470-471) — another key gap. Let me confirm how the initial run resolves its harness, and check the node components' handle IDs so my YAML port examples match what the canvas draws.

I now have full ground truth. Let me check where to place the doc.

No `docs/` dir yet. I'll create `docs/HARNESSES.md`. Writing the comprehensive, ground-truth-accurate documentation now.

Let me validate the headline YAML example against the real models so the doc doesn't ship a broken example.

The example validates cleanly. The documentation is complete and accurate to the actual implementation.

## Summary

I wrote `docs/HARNESSES.md` — a thorough, end-to-end guide to using harnesses, grounded in a full read of the actual implementation (model, validator, executor, decision/wait/aggregator, interpolation, brief composer, the API router, worker, and the frontend editor).

The most important finding: **your confusion is justified — the visual editor genuinely cannot produce a runnable harness today.** I verified six concrete frontend↔backend contract mismatches, including:

- **New nodes can't be saved** — the editor sends `ports` as a list, the backend requires a dict → 422 (verified empirically).
- **agent_ref / prompt never persist** — the UI writes a `config` field and a `prompt` key; the backend reads `data` and `prompt_template`.
- **Variables can't be added or edited** — the inspector only renders existing vars and the change handler is a no-op `() => {}`.
- **Decision conditions can't be set** — UI uses edge `label`, backend uses `condition`.
- **Skill nodes don't auto-fire** — the worker passes a stub tool resolver that always returns `None`.

The backend executor itself is sound. So the doc teaches the **reliable authoring path (YAML file or REST API)**, with a fully worked, validated real-life example (manual trigger → scout agent → human review wait → implementor agent), plus complete coverage of variables/interpolation, agent wiring, decision/wait/aggregator semantics, all five trigger kinds, running/cancelling, the run lifecycle, a prominent "Known limitations" table explaining exactly why the UI fails, troubleshooting, and a cheat sheet. The headline example is verified to pass the real Pydantic models and R5/R6/R7 validators.

If you'd like, I can scope a follow-up goal to **fix the editor** (align `config`→`data`, `prompt`→`prompt_template`, `ports` list→dict, edge `label`→`condition`, add a variable editor, and implement the worker's `tools_resolver`) so harnesses become fully usable from the UI. Want me to do that next?
```

```
2026-06-05T23:10:59Z [user]
Prepare to followup goal. Pleae for realization of particular subgoals use the cc v1 pipeline
```

```
2026-06-05T23:11:23Z [agent] run=2 model=opus-4-8 mode=auto
(no assistant text)

(stopped by user)
```

```
2026-06-05T23:13:42Z [agent] run=3 model=claude-opus-4-8 mode=auto
Before creating anything on the board, let me read the goal-creation and pipeline-scaffold skills to use the exact mechanism this project expects.

I've confirmed the exact mechanism (`create-goal` / `pipeline-scaffold` patterns, CC-v1 feature-goal structure: shared scout + per-slice analyst→architect→impl→test→review→doc, all on a shared `feature/<slug>` branch).

Here's the follow-up goal I'd create, derived from the six gaps I found in the prior analysis. Before I POST ~20 tasks to the board, let me confirm how you want it sliced.

**Proposed root goal:** *"Make harnesses usable from the visual editor"*

The six gaps group into independent work units:
- **Frontend editor fixes** (tightly coupled — all touch `harnessMapping.ts`, `types.ts`, `VariableInspector.tsx`, `HarnessEditor.tsx`): node contract alignment (`config`→`data`, `prompt`→`prompt_template`, `ports` list↔dict), edge `label`→`condition`, and a real variable add/edit/remove UI.
- **Backend fix** (independent — `worker.py`): implement a real `tools_resolver` so agent/skill nodes resolve and skills emit the `/skill` prefix.

It looks like the question prompt didn't go through. Let me lay out the concrete plan in text instead, so you can approve or adjust before I create anything on the board.

## Proposed follow-up goal

**Root goal:** `Make harnesses usable from the visual editor` (a real dev goal → shared `feature/make-harnesses-usable-...` branch; doc phase merges to main)

**Structure** (CC-v1 feature-goal pattern — shared scout + per-slice pipelines):

```
Goal: Make harnesses usable from the visual editor
├── scout  (shared, haiku)  — recon of harness editor ↔ backend contract
│
├── Sub-Goal A: Frontend editor contract + variables
│   ├── analyst   (sonnet)  depends_on: scout
│   ├── architect (opus)    depends_on: analyst
│   ├── impl      (sonnet)  depends_on: architect
│   ├── test      (sonnet)  depends_on: impl
│   ├── review    (opus)    depends_on: impl, test
│   └── doc       (haiku)   depends_on: review
│       Scope: harnessMapping.ts, types.ts, VariableInspector.tsx,
│              HarnessEditor.tsx (+ vitest). Fixes: config→data,
│              prompt→prompt_template, ports list↔dict, edge label→condition,
│              variable add/edit/remove UI wired through fromReactFlow.
│
└── Sub-Goal B: Backend worker tools_resolver
    ├── analyst   (sonnet)  depends_on: A.doc   (sequential — avoids board churn)
    ├── architect (opus)    → impl → test → review → doc (haiku)
        Scope: backend/app/worker.py (_tools_resolver), wiring to the
               space tools index so agent/skill nodes resolve and skills
               emit the /skill prefix. (+ pytest)
```

That's **2 slices** (recommended — the frontend fixes share files, the backend fix is independent), **14 phase tasks** + 1 scout + 3 goals = ~18 board items, each phase brief ending in `/pipeline-gate`.

Two decisions I need from you:

1. **Slicing** — 2 slices as above (recommended), or 3 (split contract vs variable-editor), or 1 (everything in one pipeline)?
2. **Action** — should I **create it now** in `cronos-development`, or do you want **plan-only** (I draft the full briefs first for your review)?

Tell me your picks (e.g. "2 slices, create now") and I'll execute via the API exactly as the `create-goal`/`pipeline-scaffold` skills prescribe.
```

```
2026-06-05T23:17:25Z [user]
2 slices, you can create the goal directly, but make sure, it will cover everything needed
```

```
2026-06-05T23:22:11Z [agent] run=4 model=claude-opus-4-8 mode=auto
Good. Before I create it, let me make the briefs precise and complete — I'll quickly confirm where the space tools index lives (so the backend slice brief points the pipeline at the right resolver) and double-check the node components' handle IDs that slice A must fix.

Slices confirmed as frontend-editor (disjoint files) and backend-resolver. I've now also confirmed the backend resolver should reuse `file_service._scan_category/_scan_skills` (used by `api/tools.py`), and that the node `Handle` components lack matching `id`s — so slice A's scope must include them. Let me make the scope airtight, then create it.

I'll follow this project's established pattern (umbrella root goal + N full CC-v1 pipeline sub-goals on a shared feature branch + a final finalize task). Writing the creation script:

(stopped by user)
```

```
2026-06-05T23:28:05Z [agent] run=5 model=claude-opus-4-8 mode=auto
Let me review the creation script before running it.

The script was in `/tmp` and didn't survive the session restart. Let me verify the key ground-truth facts before recreating it, so the briefs are accurate.

Confirmed the backend stub at `worker.py:470-471`. Let me check how the resolver is consumed and what scanner functions exist to reuse.

I have the ground-truth facts confirmed. Let me verify the `state_writer` API before recreating the script.

Let me verify the exact prompt field name the backend reads, to make the Slice A brief accurate.

Backend reads `node.data["prompt_template"]` and `node.data["agent_ref"]`. Let me confirm the frontend field names that diverge.

All divergences confirmed against ground truth. Now I'll recreate the goal-creation script with accurate, coverage-complete briefs and run it.

Now let me run it.

Goal created. Let me verify the structure and dependencies via the API.

The follow-up goal is fully created and verified — 18 nodes with correct CC-v1 pipeline wiring. Let me check the state of the documentation deliverable to finalize the original task.

Both deliverables are complete. Let me commit the documentation to the workspace branch as the task output.

Both deliverables are done.

## 1. Documentation — `docs/HARNESSES.md` (committed)
A 680-line how-to covering: mental model, where harnesses live, the backend data model (the source of truth), a validated end-to-end example, variables/interpolation, agent/skill wiring, decision/wait/aggregator nodes, all trigger kinds, the run lifecycle, troubleshooting, a cheat sheet — and a prominent **"Known limitations"** table that names the exact editor↔runtime contract mismatches behind your confusion (why you can't connect nodes to real agents or use variables today).

## 2. Follow-up goal — created on the board
Root goal **`harness-editor-usability`**, two CC-v1 pipeline slices (Slice B sequential after Slice A), plus a finalize task — 18 nodes total, dependencies verified:

- **Slice A — Frontend harness editor** (`scout→analysis→design→impl→test→review→doc`): aligns the editor to the backend model. Covers all 7 frontend gaps — `config`↔`data` round-trip, `prompt`→`prompt_template`, `ports` as dict + default ports + Handle ids (the 422 on new-node save), edge `label`→`condition`, editable config for *all* node types, working variable add/edit/remove, and surfacing 422s. Backend models are explicitly off-limits.
- **Slice B — Backend harness tools resolver** (full pipeline, starts after Slice A's doc): replaces the `_tools_resolver` stub at `worker.py:470-471` with a real implementation reusing the existing `scanner.py`/`tools.py` scanners, so agent/skill nodes resolve and skill briefs get the `/<name>` prefix.
- **`integrate-harness-editor-usability`** → runs `/goal-finalize` on the shared `feature/harness-editor-usability` branch after both slices.

The 6 root-cause mismatches from the docs map 1:1 onto the two slices' acceptance criteria, so the fix covers everything the guide flags as broken.

One open question: I committed the docs to the **workspace branch** (`cronos/2026-06-05-1325-harnesses-usage`), not main. Want me to push it / merge to main, or leave it on the workspace branch?
```

```
2026-06-05T23:35:31Z [user]
Push it to main
```
