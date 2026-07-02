# Fix plan: delivery-workflow runner re-spawns scout and parks to `waiting` after a valid report

**Status:** plan only — not implemented.
**Trigger case:** goal `2026-07-01-1130-delivery-goal-creation-optimisations` / subgoal
SG1 `2026-07-01-1131-sg1-fix-create-goal-skills-auth-fallback`, which re-ran the
`scout` node 4× and parked to `waiting` 10× despite a valid `scout-report.md` on disk.
**Input:** the attached `trace-report.md` diagnosis, re-verified against the *current*
code (the runner has changed since the trace was written — see §0).

---

## 0. What changed since the trace was written (read this first)

The trace describes `run_executor.py::_cc_delivery_from_report` globbing the whole
space for the newest `.md`. **That function no longer exists.** The current node-outcome
path is:

- [run_executor.py:1481-1492](../../../backend/app/run_executor.py#L1481-L1492) —
  `run_delivery_child` now returns `{"trace": trace, "delivery": None}`. It *never*
  bridges a report artifact; the comment states the outcome is read from the agent's
  `node_status`/`delivery_status` fence by the adapter.
- [adapter.py:287-303](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L287-L303) —
  because `delivery` is always `None`, `dispatchAgent` always takes the **3b fallback**:
  parse a `delivery_status` fence from `trace.final_text_snippet`, else
  `_fallback_delivery_status(run_dir)`.

So the report-resolution defect moved, but did not go away — it now lives in
`_fallback_delivery_status` ([adapter.py:511-546](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L511-L546)).
The other three root causes in the trace hold as written, and §4d is actually **more
severe and more concrete** than the trace concluded (see B1 below). The four fixes below
supersede the trace's §8 suggestions.

---

## 1. Root causes (verified against current code)

| # | Defect | Evidence | Trace ref |
|---|--------|----------|-----------|
| **B1** | **Runner state is never persisted → no resume → scout re-runs every retry.** `delivery_driver` calls `workflow_runner.run(graph=graph, executor=adapter)` with **no `state_ops`**. The runner then uses in-memory state (`run_id=""`) and never writes `state.json`. The adapter builds `self.state = CronosStateOps(...)` but it is never handed to the runner. | [delivery_driver.py:198-200](../../../backend/app/delivery_driver.py#L198-L200) (no `state_ops` arg); [core.py:61-71](../../../packages/delivery-workflow/runner/core.py#L61-L71) (`state_ops is None` → in-memory); [adapter.py:219](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L219) (`self.state` built but unused) | §4d |
| **B2** | **Report resolution is unscoped and mis-ordered.** `_fallback_delivery_status` does `delivery_dir.rglob("*.md")` over the **entire** `.cronos/delivery/` tree and picks by `reversed(sorted(...))` — i.e. **lexicographic path order, not mtime** (docstring says "newest wins"; code does not). Any other goal's report can win. | [adapter.py:521-542](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L521-L542) | §4b |
| **B3** | **Gate can't derive class/slug from the `.cronos/delivery/<slug>/scout-report.md` convention.** `_class_and_slug_from_artifact` only matches `{prefix}-{slug}.md`; a bare `scout-report.md` returns `(None, None)`, so the schema check runs without `agent`/`slug` and the gate fails. | [adapter.py:496-508](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L496-L508) and its use at [adapter.py:337-352](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L337-L352) | §4c |
| **B4** | **No slug is ever handed to the agent.** The child brief is `f"# Agent: {agent_ref}\n\n{artifact_lines}\n\n{sentinel}"` — no `slug`. The workflow `scout` node has no `prompt`/`inputs.slug` either. CC-v1 agents are contractually forbidden from inventing a slug, so each retry picks a different one → 4 artifact locations for one goal. | [run_executor.py:1370-1375](../../../backend/app/run_executor.py#L1370-L1375); [delivery.workflow.yaml:14-19](../../../packages/delivery-workflow/delivery.workflow.yaml#L14-L19) | §4a |

**Why this reads as "scout wrote the report but it still fails":** B1 forces scout to
re-run every retry (cold start). B4 makes each re-run write to a different slug. B2 lets
the gate read the wrong file. B3 makes even the *right* file un-gateable. Any one of B2/B3
turns a correct scout run into a `g-scout` failure, surfaced as the generic
`"Delivery workflow failed — a node returned status=failed."`
([delivery_driver.py:217-218](../../../backend/app/delivery_driver.py#L217-L218)).

**Extra observation (B1 corollary):** since `state.json` is never bootstrapped,
`CronosStateOps.write` in `runGate` ([adapter.py:370](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L370))
calls `self._store.read()` → `json.loads(path.read_text())` on a non-existent file →
`FileNotFoundError` ([store.py:82-84](../../../packages/delivery-workflow/lib/state/store.py#L82-L84)).
So the gate's own state write can throw. **B1 must be fixed first** — it both blocks
resume and can crash the gate.

---

## 2. Fix plan

Ordered by leverage. B1 is the keystone: fixing it alone stops the re-spawn loop and lets
scout be skipped on resume. B2+B3 make the gate reliable. B4 stabilises the slug so B2/B3
have a stable target.

### Fix 1 — Persist and resume runner state (B1) — **highest priority**

**Goal:** hand the adapter's `state_ops` to the runner, bootstrap `state.json` before the
run, so (a) `state.json`/`events.jsonl` are written, (b) resume skips the already-`done`
`scout` node instead of re-dispatching, (c) the gate's state write does not crash.

1. In [delivery_driver.py:198-200](../../../backend/app/delivery_driver.py#L198-L200),
   pass `state_ops=adapter.state`:
   ```python
   final_state = await asyncio.to_thread(
       workflow_runner.run, graph=graph, executor=adapter, state_ops=adapter.state,
   )
   ```
2. **Bootstrap `state.json` before the run** (the runner's `state_ops.read()` at
   [core.py:62](../../../packages/delivery-workflow/runner/core.py#L62) assumes it exists).
   After `run_dir.mkdir(...)` and adapter construction, if `adapter.state`'s store does not
   yet exist, write an initial `WorkflowState(spec=graph.metadata["name"], run_id=<goal_id>,
   status="running", budget=BudgetState(usd_ceiling=...))`. Use `StateStore.exists()`
   ([store.py:79-80](../../../packages/delivery-workflow/lib/state/store.py#L79-L80)) to make
   this idempotent so a *resumed* run reads the existing state instead of clobbering it.
   - Prefer adding a small `bootstrap_if_absent(graph)` helper on `CronosStateOps` (or a
     free function in the driver) so both the driver and any tests share one path.
3. Set a **stable `run_id`** = the goal id (not `""`). The run dir is already keyed by
   goal id (`.cronos/delivery-runs/<goal_id>/`), so this makes a retry of the same goal
   reuse the same state and resume.
4. **Guard the gate's state write** at [adapter.py:369-381](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L369-L381)
   defensively (bootstrap-on-missing or try/except → create) so a missing `state.json` can
   never crash `runGate` even if step 2 regresses.

**Acceptance:**
- After one scout run, `.cronos/delivery-runs/<goal_id>/state.json` exists with
  `nodes.scout.status == "done"` and `events.jsonl` has a `node_transition`.
- A second `run` invocation for the same goal **does not create a new `[delivery] scout`
  child** — `resume_node_status` ([store.py:61-70](../../../packages/delivery-workflow/lib/state/store.py#L61-L70))
  returns `skip` and the work-list seeds past scout.
- New/updated test in `packages/delivery-workflow/tests/` asserting resume skips a `done`
  node when `state_ops` is provided, plus a driver-level test asserting `state.json` is
  written after a run.

> This directly explains the user's report: *"when I stopped the spawned scout, the process
> continued in the subgoal, wrote a report to git, then fell to waiting."* Without persisted
> state, stopping the child and retrying restarts the workflow cold every time.

### Fix 2 — Scope report resolution to this goal + order by mtime (B2)

**Goal:** never let another goal's report satisfy this node.

1. In `_fallback_delivery_status` ([adapter.py:511-546](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L511-L546)),
   scope the delivery-tree scan to `delivery_dir / <slug>` (the resolved goal slug from
   Fix 4) instead of `delivery_dir.rglob("*.md")` over the whole tree.
2. Fix the ordering: sort by `st_mtime` (newest first), not `reversed(sorted(paths))`
   (which is lexicographic). Align code with the docstring.
3. Preferably, make this fallback the *last* resort: the primary outcome should come from
   the agent's `delivery_status` fence (which carries the agent's own `artifact_paths`).
   The fence path already avoids the glob — keep it primary and only tighten the fallback.

**Acceptance:** unit test with two goals' reports under `.cronos/delivery/` (goal-A newer
by mtime, goal-B is "ours") asserts the scan returns goal-B's report, not goal-A's.

### Fix 3 — Accept the `.cronos/delivery/<slug>/{prefix}.md` convention in class/slug parsing (B3)

**Goal:** derive `(class, slug)` for both filename conventions.

In `_class_and_slug_from_artifact` ([adapter.py:480-508](../../../packages/delivery-workflow/adapters/cronos/adapter.py#L480-L508)):
1. Keep the existing `{prefix}-{slug}.md` match (`.cronos/pipeline/` convention).
2. **Add** a branch: if the bare filename equals `{prefix}.md` (no slug suffix), take the
   **slug from the parent directory name** — i.e. `Path(artifact_paths[0]).parent.name`.
   This matches `.cronos/delivery/<slug>/scout-report.md` introduced by `482f4ad`.
3. Return `(klass, parent_dir_name)` in that case.

**Acceptance:** parametrized test covering both
`.cronos/pipeline/my-goal/scout-report-my-goal.md → (research, my-goal)` and
`.cronos/delivery/my-goal/scout-report.md → (research, my-goal)`.

### Fix 4 — Thread a stable `goal_slug` into every child brief (B4)

**Goal:** hand CC-v1 agents the slug verbatim so they stop inventing 4 different ones.

1. Derive the slug **once** per delivery goal (e.g. from the root goal title, matching how
   the goal id/title is already slugified) and pass it down through `run_delivery_child`'s
   `inputs`.
2. In [run_executor.py:1370-1375](../../../backend/app/run_executor.py#L1370-L1375), add a
   `slug: <goal_slug>` line to the brief so agents receive it per their contract
   (*"Never derive the slug. Use the slug verbatim from your task prompt."*). Consider
   reusing [brief_composer.py::compose_brief](../../../backend/app/harnesses/brief_composer.py#L44)
   instead of the ad-hoc f-string so both execution paths share one brief format.
3. Also expose the slug to the workflow spec if any node's `prompt`/`inputs` needs it
   ([delivery.workflow.yaml](../../../packages/delivery-workflow/delivery.workflow.yaml)).
4. This slug is the *same* value Fix 2 scopes the scan to and Fix 3 reads from the dir name
   — keep them consistent (single source of truth: the goal slug).

**Acceptance:** a delivery child brief contains `slug: <goal-slug>`; an integration check
confirms repeated runs of the same goal write to a single `.cronos/delivery/<slug>/` dir.

---

## 3. Sequencing & risk

1. **Fix 1 (B1)** — stops the re-spawn loop and the gate crash. Ship first; it is the
   root of the "keeps falling to waiting" symptom.
2. **Fix 4 (B4)** — stabilises the slug so Fixes 2/3 have a fixed target.
3. **Fix 2 (B2) + Fix 3 (B3)** — make the gate reliable against the correct, scoped report.

**Non-goals / follow-ups:**
- The `2026-07-02-0536-delivery-scout` run edited the two `SKILL.md` files despite scout's
  read-only contract. That is an *agent-contract* issue (the `scout` agent ref does not
  resolve to a strict `pipeline-scout` skill — note `.claude/agents/` no longer contains
  `pipeline-scout.md`), separate from the runner bugs here. Track separately.
- Per trace §7, the SG1 skill-file fix already exists uncommitted in the main worktree
  (`M .claude/skills/create-delivery-goal/SKILL.md`, `M .claude/skills/create-goal/SKILL.md`).
  Once the runner can progress past `g-scout`, that work can flow through implement/commit
  normally. Do **not** hand-commit it as part of this runner fix.

## 4. Test coverage to add

- `tests/` (delivery-workflow): resume skips `done` node; `state.json` bootstrap idempotent.
- `tests/` adapter: `_fallback_delivery_status` scoping + mtime ordering (B2);
  `_class_and_slug_from_artifact` both conventions (B3).
- backend `tests/`: `run_delivery_child` brief includes `slug` (B4); driver passes
  `state_ops` and writes `state.json` (B1).
- Keep the 80% backend coverage floor green.
