---
name: pipeline-scaffold
description: Bootstrap a CC-v1 pipeline in any Cronos space. Given a feature request, owns the goal slug, writes request.md + initial pipeline-state.json, and POSTs a goal plus the seven phase tasks (scout / analysis / design / impl / test / review / doc) with depends_on wired and the /pipeline-gate step appended to each. Cronos analogue of the Delivery Notes orchestrator's Phase 0.
license: Internal — Cronos project.
---

# Pipeline Scaffold

This skill is the **Cronos Phase 0**: it turns a free-form feature request into a wired pipeline goal on the Cronos board. After it runs, the worker can pick up the first phase task and the rest of the pipeline self-drives — each phase task spawns its CC-v1 sub-agent, then closes itself with [[pipeline-gate]] which decides PASS / BLOCK from the artifact's YAML header.

The skill is the single source of authority for the goal slug. Every downstream sub-agent receives that slug verbatim — no agent re-kebabs, suffixes, or reconstructs it (per Cronos Agent Contract v1.0 R6 in [`backend/app/pipeline/CONTRACT.md`](../../../backend/app/pipeline/CONTRACT.md)).

## When to use

Invoke this skill when:
1. You have a feature request (free text or a path to a `request.md`) AND
2. You want to run the full CC-v1 pipeline against that request in some Cronos space.

Do **NOT** invoke it to add a single ad-hoc task — for that use [[create-task]]. Do not invoke it for goals that are not running the pipeline — for that use [[create-goal]].

## What it produces

1. `{space}/.cronos/pipeline/{goal_slug}/request.md` — verbatim request text.
2. `{space}/.cronos/pipeline/{goal_slug}/pipeline-state.json` — initialized via `app.pipeline.state_writer.init_pipeline()` with `status="running"`, `cc_version="1.0"`, empty `phases`, zeroed telemetry.
3. `{space}/.cronos/pipeline/{goal_slug}/phases-log.jsonl` — empty file, ready for one-line-per-phase appends from [[pipeline-gate]].
4. **One Cronos goal** (`type=goal`) holding the request brief.
5. **Seven Cronos child tasks** (`type=task`), one per CC-v1 phase, each with:
   - The phase agent name and slug embedded in the brief.
   - `agent_model` matched to the sub-agent's model family (Haiku / Sonnet / Opus).
   - `depends_on` wired to the upstream phase(s).
   - The [[pipeline-gate]] invocation block appended to the brief (so the gate runs as the final step of the same task).

The DAG (linear except for review fan-in):

```
scout → analysis → design → impl → test ─┐
                              │          ├→ review → doc
                              └──────────┘
```

## Required inputs

The invoker (the calling task's brief, or the user) must provide:

| Field | Required | Example | Notes |
|---|---|---|---|
| `space_id` | yes | `cronos-development` | Cronos space id where the goal + tasks will be created. Verify via `GET /api/spaces`. |
| `title` | yes | `Add CSV export to dashboard` | Short imperative title (max 80 chars). Drives the goal slug. |
| `request_text` | yes | (free-form markdown) | The verbatim feature request. Stored as `request.md` and quoted into the goal brief. |
| `slug_hint` | no | `dashboard-csv-export` | Optional kebab-case override. Must match `^[a-z0-9]+(-[a-z0-9]+)*$` and be ≤ 40 chars. If absent the slug is derived from `title`. |
| `space_dir` | no | `/data/spaces/cronos-development` | Absolute path to the space root. Defaults to `/data/spaces/{space_id}`. |
| `priority` | no | `2` | Cronos priority for every created task (1=highest, 5=lowest). Defaults to 2 for pipeline work. |

If `space_id` is missing or the space does not exist on the backend, stop with `STATUS: BLOCKED` and a one-line reason. **Never default the space_id** — getting it wrong creates orphan tasks on the wrong board.

## Slug ownership rule

The goal slug is the single identifier that binds every pipeline artifact, every gate-task brief, and every state-file path. Cronos already kebab-slugifies titles inside `backend/app/storage.py::slugify` (lowercase, `[^a-z0-9]+` → `-`, max 40 chars). The scaffold trusts that derivation:

1. Cronos POST `/api/tasks` with `type=goal` returns a task id of the form `YYYY-MM-DD-HHMM-{slug}`.
2. Strip the 16-character `YYYY-MM-DD-HHMM-` prefix → that is the canonical `goal_slug` written everywhere downstream.

The slug is **immutable** once the goal exists. Every sub-agent and every gate-task brief receives the same `goal_slug` verbatim.

For fan-out runs (impl iterations, review attempts) the suffix is composed by the gate/agent — `goal_slug--i1`, `goal_slug--attempt2` — and the goal_slug itself never changes (R6 in `backend/app/pipeline/CONTRACT.md`).

## Phase plan (the table this skill writes into Cronos)

| # | Phase | CC-v1 class | Sub-agent | `agent_model` | `depends_on` (intra-goal) |
|---|---|---|---|---|---|
| 1 | scout    | `research`        | `pipeline-scout`       | `haiku`  | — |
| 2 | analysis | `analysis`        | `pipeline-analyst`     | `sonnet` | scout |
| 3 | design   | `design`          | `pipeline-architect`   | `opus`   | analysis |
| 4 | impl     | `implementation`  | `pipeline-implementor` | `sonnet` | design |
| 5 | test     | `test`            | `tester`               | `sonnet` | impl |
| 6 | review   | `review`          | `pipeline-reviewer`    | `opus`   | impl, test |
| 7 | doc      | `doc`             | `pipeline-doc-sync`    | `haiku`  | review |

`agent_mode` is `auto` for every phase. The phase task's top-level LLM is the one that spawns the CC-v1 sub-agent via the `Agent` tool — picking `agent_model` to match the sub-agent's own model family keeps the wrapper-LLM cheap (Haiku/Sonnet/Opus on the wrapper mirrors the sub-agent's budget).

The skill does **not** create a "Phase 0" task — Phase 0 is this skill itself.

## Procedure (single Python block)

Run the whole scaffold as one Python script. It performs slug derivation, request.md + pipeline-state.json initialization, the goal POST, the seven child-task POSTs, and a final summary print. Inputs come from environment variables so the same script works from a Cronos task brief, a shell, or another agent.

```bash
# Required: space_id, title, request_text (or request_path).
export SPACE_ID=cronos-development
export TITLE="Add CSV export to dashboard"
export REQUEST_TEXT="Users on the dashboard need a 'Download CSV' button..."
# Optional:
# export SLUG_HINT=dashboard-csv-export
# export SPACE_DIR=/data/spaces/cronos-development
# export PRIORITY=2

python3 <<'__PY__'
import json, os, re, sys, urllib.request
from pathlib import Path

# ---- 1. Read + validate inputs ----------------------------------------
SPACE_ID     = os.environ["SPACE_ID"]
TITLE        = os.environ["TITLE"].strip()
REQUEST_TEXT = os.environ.get("REQUEST_TEXT", "").strip()
REQUEST_PATH = os.environ.get("REQUEST_PATH", "").strip()
SLUG_HINT    = os.environ.get("SLUG_HINT", "").strip()
SPACE_DIR    = Path(os.environ.get("SPACE_DIR", f"/data/spaces/{SPACE_ID}"))
PRIORITY     = int(os.environ.get("PRIORITY", "2"))

if not SPACE_ID or not TITLE:
    print("ERROR: SPACE_ID and TITLE are required"); sys.exit(2)
if not REQUEST_TEXT and REQUEST_PATH:
    REQUEST_TEXT = Path(REQUEST_PATH).read_text(encoding="utf-8").strip()
if not REQUEST_TEXT:
    print("ERROR: provide REQUEST_TEXT or REQUEST_PATH"); sys.exit(2)
if not SPACE_DIR.is_dir():
    print(f"ERROR: space dir does not exist: {SPACE_DIR}"); sys.exit(2)

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
if SLUG_HINT and not (SLUG_RE.match(SLUG_HINT) and len(SLUG_HINT) <= 40):
    print(f"ERROR: slug_hint {SLUG_HINT!r} must match {SLUG_RE.pattern} and be <= 40 chars")
    sys.exit(2)

# ---- 2. POST the goal so Cronos assigns the canonical id --------------
def api_post(path, payload):
    req = urllib.request.Request(
        f"http://backend:8000{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# Use slug_hint as the goal title when supplied so Cronos slugify yields it
# verbatim; otherwise let Cronos derive the slug from the natural title.
goal_title_for_post = SLUG_HINT.replace("-", " ") if SLUG_HINT else TITLE

goal_brief = f"""# Pipeline goal: {TITLE}

Pipeline run scaffolded by `/pipeline-scaffold`. Verbatim request is at
`.cronos/pipeline/{{goal_slug}}/request.md`; live state at
`.cronos/pipeline/{{goal_slug}}/pipeline-state.json`.

## Request

{REQUEST_TEXT}

## Child tasks (one per CC-v1 phase)

1. scout    — pipeline-scout    (research)
2. analysis — pipeline-analyst  (analysis)
3. design   — pipeline-architect(design)
4. impl     — pipeline-implementor (implementation; may fan out per iteration)
5. test     — tester            (test)
6. review   — pipeline-reviewer (review; may loop on verdict=needs_fix)
7. doc      — pipeline-doc-sync (doc; terminal)

Each phase task ends by invoking `/pipeline-gate` which closes the gate from
the artifact's YAML header — no prose parsing.
"""

goal = api_post("/api/tasks", {
    "space_id": SPACE_ID,
    "title": goal_title_for_post,
    "brief": goal_brief,
    "type": "goal",
    "priority": PRIORITY,
    "agent_mode": "auto",
    "agent_model": "default",
})
GOAL_ID = goal["id"]
# Strip the 16-char "YYYY-MM-DD-HHMM-" prefix to get the canonical slug.
GOAL_SLUG = GOAL_ID[16:]
assert SLUG_RE.match(GOAL_SLUG), f"unexpected slug from Cronos: {GOAL_SLUG!r}"
print(f"goal:  {GOAL_ID}  slug={GOAL_SLUG}")

# ---- 3. Write request.md + initialize pipeline-state.json -------------
# Locate the Cronos backend so init_pipeline writes the exact schema the
# verifier expects. The target space may not bundle backend/ (e.g. personal,
# delivery-notes), so fall back to the cronos-development source then the
# worker container path.
for _cand in (SPACE_DIR / "backend",
              Path("/data/spaces/cronos-development/backend"),
              Path("/app")):
    if (_cand / "app" / "pipeline" / "state_writer.py").is_file():
        sys.path.insert(0, str(_cand))
        break
else:
    print("ERROR: cannot locate app.pipeline.state_writer; install Cronos backend"); sys.exit(2)
from app.pipeline.state_writer import init_pipeline, pipeline_dir  # type: ignore

pdir = pipeline_dir(SPACE_DIR, GOAL_SLUG)
pdir.mkdir(parents=True, exist_ok=True)
(pdir / "request.md").write_text(REQUEST_TEXT + "\n", encoding="utf-8")
init_pipeline(SPACE_DIR, GOAL_SLUG, status="running", request_text=REQUEST_TEXT)
print(f"state: {pdir}/pipeline-state.json")

# ---- 4. Build phase briefs (each brief embeds the /pipeline-gate call) --
PIPELINE_REL = f".cronos/pipeline/{GOAL_SLUG}"

def gate_block(phase_class, agent_name, extra_exports=""):
    # The gate runs as the LAST step of the same task; upstream_task_id is
    # this task's own id (the agent ran as a sub-agent inside this task).
    return f"""## Step 2 — close the gate

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact, records phase metrics into `pipeline-state.json`, and emits the final
`STATUS:` line for this task.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG={GOAL_SLUG}
export PHASE={phase_class}
export AGENT_NAME={agent_name}
export UPSTREAM_TASK_ID="$TASK_ID"
{extra_exports}```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.
"""

def phase_brief(idx, phase_class, agent_name, summary, inputs_md, slug_expr, gate_extra=""):
    return f"""# Phase {idx} — {phase_class}: {TITLE}

Goal slug: `{GOAL_SLUG}` · Pipeline dir: `{PIPELINE_REL}/` · Sub-agent: `{agent_name}`.

{summary}

## Step 1 — spawn the sub-agent

Use the `Agent` tool with `subagent_type="{agent_name}"` and the brief below.
The sub-agent writes its CC-v1 artifact under `{PIPELINE_REL}/` and returns a
short conversational summary; do not paraphrase or post-process its output here.

```text
slug   = {slug_expr}
space  = $SPACE_DIR    (resolved from $PWD as in Step 2)
{inputs_md}
```

Wait for the sub-agent to return. Do not read the artifact body yourself — the
gate (Step 2) verifies it mechanically.

{gate_block(phase_class, agent_name, gate_extra)}
"""

briefs = {}

briefs["scout"] = phase_brief(
    1, "research", "pipeline-scout",
    "Memory-first reconnaissance of the codebase around the feature request. Emits `scout-report-{slug}.md` (class=research).",
    f"brief  = (research question derived from the request — defer to the agent)\n"
    f"request_text = (verbatim from {PIPELINE_REL}/request.md)",
    GOAL_SLUG,
)

briefs["analysis"] = phase_brief(
    2, "analysis", "pipeline-analyst",
    "Decompose the verbatim request into atomic, testable requirements `R<N>`. Determines `has_ui`, scope, traceability. Emits `analysis-report-{slug}.md` (class=analysis).",
    f"request = (verbatim text of {PIPELINE_REL}/request.md — do not paraphrase)\n"
    f"scout_report_path = {PIPELINE_REL}/scout-report-{GOAL_SLUG}.md",
    GOAL_SLUG,
)

briefs["design"] = phase_brief(
    3, "design", "pipeline-architect",
    "Map every requirement to an iteration. Emits `design-report-{slug}.md` (class=design) with topologically-ordered `iterations[]` and a `risks[]` register.",
    f"analysis_report_path = {PIPELINE_REL}/analysis-report-{GOAL_SLUG}.md\n"
    f"scout_report_path    = {PIPELINE_REL}/scout-report-{GOAL_SLUG}.md",
    GOAL_SLUG,
)

# Implementation phase: fan out per iteration. The sub-agent expects a
# compound slug `goal_slug--{iter_id_lower}`. The brief drives the task LLM
# to read the design's iterations[] from the YAML header and loop.
briefs["impl"] = f"""# Phase 4 — implementation: {TITLE}

Goal slug: `{GOAL_SLUG}` · Pipeline dir: `{PIPELINE_REL}/` · Sub-agent: `pipeline-implementor`.

Execute every entry of the design's `iterations[]` array. Each iteration gets
its own implementor invocation AND its own [[pipeline-gate]] call — fan-out
slugs are `{GOAL_SLUG}--<iter_id_lower>` (e.g. `{GOAL_SLUG}--i1`).

## Step 1 — set up the feature branch (once)

If this is the first code-changing task in the goal, invoke `/goal-branch-setup`
first so all implementor edits land on `feature/{GOAL_SLUG}` rather than the
per-task worktree branch. Later tasks in the same goal find the branch already
set up.

## Step 2 — read the design report and topologically order iterations

Read `{PIPELINE_REL}/design-report-{GOAL_SLUG}.md`'s YAML header. Extract
`iterations[]` and group by `depends_on` into topological layers (Kahn's
algorithm). Pick the lowest layer that has not been executed yet.

## Step 3 — for EACH iteration in the chosen layer

For each iteration `iter`:

1. **Spawn the implementor** via the `Agent` tool, `subagent_type="pipeline-implementor"`:

   ```text
   slug                 = {GOAL_SLUG}--<iter.id.lower()>
   space                = $SPACE_DIR
   design_report_path   = {PIPELINE_REL}/design-report-{GOAL_SLUG}.md
   iteration_id         = <iter.id>
   prior_iteration_results = [<paths to impl-report-{GOAL_SLUG}--*.md for satisfied deps>]
   ```

2. **Close the per-iteration gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG={GOAL_SLUG}
   export PHASE=implementation
   export AGENT_NAME=pipeline-implementor
   export UPSTREAM_TASK_ID="$TASK_ID"
   export ITERATION_ID=<iter.id>
   ```

   Then invoke `/pipeline-gate`. If it sets `STATUS: BLOCKED`, **halt the loop**
   and emit `STATUS: BLOCKED` for the whole task — do not advance to the next
   iteration with a known-bad upstream.

## Step 4 — commit + final status

If every iteration's gate passed:
1. Invoke `/goal-task-commit` to push all implementor changes to `feature/{GOAL_SLUG}`.
2. Write a one-line summary listing the iteration ids that ran and emit `STATUS: DONE`.

Otherwise the BLOCKED status from Step 3 is already the task's final status — do not overwrite it.
"""

briefs["test"] = f"""# Phase 5 — test: {TITLE}

Goal slug: `{GOAL_SLUG}` · Pipeline dir: `{PIPELINE_REL}/` · Sub-agent: `tester`.

## Step 1 — spawn the tester sub-agent

Use the `Agent` tool with `subagent_type="tester"`. Pass:

```text
space_id  = {SPACE_ID}
scope     = full-space
slug      = {GOAL_SLUG}     # makes the tester emit test-report-{{slug}}.md too
```

The tester runs pytest + vitest, parses coverage, POSTs a TestReport to
`{{backend}}/api/test-reports`, and (because slug is set) ALSO emits a
CC-v1 `test-report-{GOAL_SLUG}.md` artifact under `{PIPELINE_REL}/`.

{gate_block("test", "tester")}
"""

briefs["review"] = f"""# Phase 6 — review: {TITLE}

Goal slug: `{GOAL_SLUG}` · Pipeline dir: `{PIPELINE_REL}/` · Sub-agent: `pipeline-reviewer`.

The review phase is **bounded** by `max_review_attempts` (default 3). Each
attempt uses a compound slug `{GOAL_SLUG}--attempt<k>`. Loop:

1. **Determine the attempt number.** Read `{PIPELINE_REL}/pipeline-state.json`;
   if `phases.review.verify_result.gate_decision in {{fail, retry}}`, increment
   the last attempt; otherwise start at `1`. Cap at `3`.

2. **Spawn the reviewer** via the `Agent` tool, `subagent_type="pipeline-reviewer"`:

   ```text
   slug              = {GOAL_SLUG}--attempt<k>
   space             = $SPACE_DIR
   design_report_path = {PIPELINE_REL}/design-report-{GOAL_SLUG}.md
   impl_report_paths = [<paths to every impl-report-{GOAL_SLUG}--*.md>]
   test_report_path  = {PIPELINE_REL}/test-report-{GOAL_SLUG}.md
   attempt           = <k>
   prior_review_path = {PIPELINE_REL}/review-report-{GOAL_SLUG}--attempt<k-1>.md   # only when k > 1
   ```

3. **Close the gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG={GOAL_SLUG}
   export PHASE=review
   export AGENT_NAME=pipeline-reviewer
   export UPSTREAM_TASK_ID="$TASK_ID"
   export ATTEMPT=<k>
   ```

   Invoke `/pipeline-gate`. On `STATUS: DONE`, inspect the reviewer artifact's
   YAML `verdict`:
   - `verdict=pass` → emit `STATUS: DONE`, end the task.
   - `verdict=needs_fix` AND `k < 3` → re-enqueue Phase 4 (impl) by emitting
     `STATUS: BLOCKED` with the reviewer's findings; an operator (or a future
     auto-retry task) re-runs impl + test + review.
   - `verdict=needs_fix` AND `k == 3` → `STATUS: BLOCKED`, attempt cap hit.
   - `verdict=fail` → `STATUS: BLOCKED`, terminal.

   On `STATUS: BLOCKED` from the gate itself (artifact missing / schema
   failure), the gate's status is final — do not overwrite it.
"""

briefs["doc"] = f"""# Phase 7 — doc: {TITLE}

Goal slug: `{GOAL_SLUG}` · Pipeline dir: `{PIPELINE_REL}/` · Sub-agent: `pipeline-doc-sync`.

Update documentation for the implementation diff. Emits `doc-report-{{slug}}.md` (class=doc)
with `intentionally_not_updated[]` always present. Terminal phase — merges the feature branch
to main via `/goal-finalize` after the gate passes.

## Step 1 — spawn the sub-agent

Use the `Agent` tool with `subagent_type="pipeline-doc-sync"` and the brief below.
The sub-agent writes its CC-v1 artifact under `{PIPELINE_REL}/` and returns a
short conversational summary; do not paraphrase or post-process its output here.

```text
slug   = {GOAL_SLUG}
space  = $SPACE_DIR    (resolved from $PWD as in Step 2)
review_report_path = {PIPELINE_REL}/review-report-{GOAL_SLUG}--attempt<final_k>.md
impl_report_paths  = [<paths to every impl-report-{GOAL_SLUG}--*.md>]
```

Wait for the sub-agent to return. Do not read the artifact body yourself — the
gate (Step 2) verifies it mechanically.

## Step 2 — close the gate (on PASS continue to Step 3)

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact and records phase metrics into `pipeline-state.json`.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||'  )
export GOAL_SLUG={GOAL_SLUG}
export PHASE=doc
export AGENT_NAME=pipeline-doc-sync
export UPSTREAM_TASK_ID="$TASK_ID"
```

Invoke `/pipeline-gate`. Check the outcome:
- **Exit 0 (pass)**: gate records state — do NOT emit STATUS yet, continue to Step 3.
- **Any other exit**: gate emits `STATUS: BLOCKED` — this is the final status; stop.

## Step 3 — merge the feature branch to main (`/goal-finalize`)

The doc phase is the terminal pipeline phase. All code changes are already
committed to `feature/{GOAL_SLUG}` by the impl phase (via `/goal-task-commit`).

Invoke `/goal-finalize`. That skill runs the full test suite, rebases
`feature/{GOAL_SLUG}` onto `origin/main`, merges `--no-ff`, and pushes. It
emits the final `STATUS: DONE` (merge succeeded) or `STATUS: BLOCKED` (test
failures or rebase conflicts). That is the final status for this task.
"""

# ---- 5. POST the seven phase tasks in dependency order ---------------
phase_plan = [
    ("scout",    "pipeline-scout: " + TITLE,         "haiku",  []),
    ("analysis", "pipeline-analyst: " + TITLE,       "sonnet", ["scout"]),
    ("design",   "pipeline-architect: " + TITLE,     "opus",   ["analysis"]),
    ("impl",     "pipeline-implementor: " + TITLE,   "sonnet", ["design"]),
    ("test",     "tester: " + TITLE,                 "sonnet", ["impl"]),
    ("review",   "pipeline-reviewer: " + TITLE,      "opus",   ["impl", "test"]),
    ("doc",      "pipeline-doc-sync: " + TITLE,      "haiku",  ["review"]),
]

created_ids: dict[str, str] = {}
for key, task_title, model, deps in phase_plan:
    payload = {
        "space_id": SPACE_ID,
        "title": task_title,
        "brief": briefs[key],
        "type": "task",
        "parent_id": GOAL_ID,
        "priority": PRIORITY,
        "agent_mode": "auto",
        "agent_model": model,
        "depends_on": [created_ids[d] for d in deps],
    }
    t = api_post("/api/tasks", payload)
    created_ids[key] = t["id"]
    dep_str = ", ".join(deps) or "—"
    print(f"  {key:<8} {t['id']}  model={model:<7} depends_on=[{dep_str}]")

print()
print(f"OK — pipeline goal scaffolded.")
print(f"  goal_slug     : {GOAL_SLUG}")
print(f"  goal_id       : {GOAL_ID}")
print(f"  pipeline_dir  : {pdir}")
print(f"  request.md    : {pdir / 'request.md'}")
print(f"  state file    : {pdir / 'pipeline-state.json'}")
__PY__
```

## Multi-SG arc usage (calling this skill multiple times)

When a feature arc has multiple sequential pipeline subgoals (e.g. `data-model` → `api` → `board-ui`), call this skill once per subgoal — each call produces one goal + 7 phase tasks. After all subgoals are created, **wire sibling `depends_on`** between the subgoal goals so `_topo_children` runs them in the correct order.

```bash
python3 -c "
import urllib.request, json

def patch_deps(tid, deps):
    data = json.dumps({'depends_on': deps}).encode()
    req = urllib.request.Request(
        'http://backend:8000/api/tasks/' + tid + '/depends_on',
        data=data, method='PATCH',
        headers={'Content-Type': 'application/json'},
    )
    return json.loads(urllib.request.urlopen(req).read())

# Example: S1 → S2 → S3 (replace with actual goal ids returned by each scaffold call)
patch_deps('<s2_goal_id>', ['<s1_goal_id>'])
patch_deps('<s3_goal_id>', ['<s2_goal_id>'])
print('Sibling deps wired.')
"
```

**Why this is required:** `_topo_children` sorts sibling children by `(manual_order, id)`. With `manual_order=0` for all subgoals and no sibling `depends_on`, they sort **alphabetically by id** — which almost certainly produces the wrong execution order (e.g. `featurefix-api` before `featurefix-data-model`). Deps on tasks *inside* another subgoal (cross-boundary task deps) are not visible to `_topo_children` and do not fix the ordering. Only sibling `depends_on` on the subgoal goals themselves works.

## What this skill does NOT do

- **Run any sub-agent.** Phase tasks run when the Cronos worker activates them; the scaffold only wires the DAG.
- **Choose the slug arbitrarily.** It always defers to `backend/app/storage.py::slugify` (via the goal POST), then derives `goal_slug` by stripping the timestamp prefix. The `slug_hint` is only an upstream input to that derivation, not a bypass.
- **Run the feature-branch workflow directly.** The workflow is wired into the task briefs: [[goal-branch-setup]] in the impl task (Step 1), [[goal-task-commit]] in the impl task (Step 4 after all iterations pass), and [[goal-finalize]] in the doc task (Step 3, terminal). The skills execute when those tasks run, not when the scaffold POSTs the tasks.
- **Read or interpret sub-agent artifacts.** Every routing decision downstream comes from YAML headers via [[pipeline-gate]] → `app.pipeline.verify` (CC-v1 R-rules).
- **Touch the worker / agent / DB.** The skill only POSTs over the public Cronos API and writes to the pipeline directory.
- **Re-init pipeline-state.json if the goal already exists.** Re-running the scaffold against a duplicate title creates a new Cronos goal with a fresh slug; if you need to resume an interrupted run, edit `pipeline-state.json` directly or re-spawn the failed phase task.

## Verify

```bash
# 1. The Cronos board shows the goal + seven child tasks in backlog
curl -s "http://backend:8000/api/tasks?space_id=${SPACE_ID}" \
  | python3 -c "
import sys, json
b = json.load(sys.stdin).get('backlog', [])
for t in b:
    pad = '  ' if t.get('parent_id') else ''
    dep = ','.join(t.get('depends_on', []))
    print(f\"{pad}[{t['type']}] {t['id']}  {t['title']}  deps=[{dep}]\")
"

# 2. Pipeline state + request mirror look correct
ls "${SPACE_DIR:-/data/spaces/${SPACE_ID}}/.cronos/pipeline/${GOAL_SLUG}/"
python3 -c "
import json, pathlib, os
p = pathlib.Path(os.environ['SPACE_DIR']) / '.cronos/pipeline' / os.environ['GOAL_SLUG'] / 'pipeline-state.json'
d = json.loads(p.read_text())
print('cc_version =', d['cc_version'])
print('status     =', d['status'])
print('phases     =', list(d['phases']))
print('telemetry  =', d['telemetry'])
"
```

A correctly-wired pipeline goal shows:
- One `[goal]` row, exactly seven `[task]` children with `parent_id` = goal id.
- `depends_on` matching the table in §"Phase plan" (each row's deps are present in the prior rows).
- `pipeline-state.json` with `cc_version="1.0"`, `status="running"`, empty `phases`, telemetry zeroed.
- `request.md` containing the verbatim request text.
- `phases-log.jsonl` exists and is empty.

## Quick reference

```text
goal_slug rule  : Cronos task_id == "YYYY-MM-DD-HHMM-<goal_slug>"; strip prefix
pipeline dir    : {space}/.cronos/pipeline/{goal_slug}/
state writer    : app.pipeline.state_writer.init_pipeline(space, goal_slug, status="running", request_text=...)
gate skill      : .claude/skills/pipeline-gate/SKILL.md (per-phase verifier + state recorder)
phase agents    : pipeline-{scout,analyst,architect,implementor,reviewer,doc-sync} + tester
class IDs       : research | analysis | design | implementation | test | review | doc
fan-out slugs   : {goal_slug}                       — scout/analysis/design/test/doc
                  {goal_slug}--{iter_id_lower}       — implementation
                  {goal_slug}--attempt{N}            — review
DAG             : scout → analysis → design → impl → test → review → doc
                                                  └────────────┘
```
