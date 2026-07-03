---
name: retro
description: Method for retrospecting on a delivery/v1 pipeline run — how to read run state (state.json, events.jsonl, per-node artifacts, traces), the five-dimension scoring rubric, the tier/fix_type decision tree, the severity ladder, always-blocking categories, the finding format, the artifact structure, and carry-forward discipline. Loaded by the retro agent.
---

# retro

How to retrospect on one delivery/v1 run. The `retro` agent owns the role and the hard rules;
this skill owns the method. You read the run's execution record, score it, and emit findings the
`improve` applier and a human can act on. You change nothing.

## 1. Memory-first preflight
Before reading run state, scan the injected memory context. Treat prior retro findings, recorded
known-issues, and pipeline conventions as **binding context**: if a prior memory recorded a
recurring failure, check whether *this run* tripped it again — if so, file the finding with
`known_issue_ref` set, and treat recurrence as an escalator (a tier-1 issue seen three runs
running is evidence the cheap fix isn't working; say so).

## 2. Read the run record (the delivery/v1 ledger)
delivery/v1 uses `state.json` and `events.jsonl` as its authoritative run ledger. Read:

- **`state.json`** (a `WorkflowState`): `spec`, `run_id`, terminal `status`
  (`done|failed|blocked|escalated`), `budget{usd_ceiling, usd_spent}`, and `nodes{}` — a map of
  `node_id → NodeState{status, attempt, gate, artifact_paths, telemetry}`. `attempt > 1` on a
  node means a loop re-entry; `gate` holds that gate's `GateResult{decision, errors, evidence}`.
- **`events.jsonl`**: append-only `node_transition` records `{node_id, status, type}` giving the
  **temporal order** (the `nodes{}` map is unordered) and the full re-entry history of every loop.
- **per-node artifacts**: each `nodes[*].artifact_paths[]`. Read **only the YAML frontmatter and
  section headings** for routing facts (verdicts, finding classes, scope sets, validation flags);
  body prose informs your `evidence`, never your machine fields.
- **per-node traces**: via the runtime-supplied index. Read the structured fields below.

If `state.json` is missing or malformed → `status: blocked`, one `critical` blocker
("cannot retrospect without the run ledger"), stop. If some artifacts or traces are missing →
continue; each absence is itself a finding (the node finished but left no record), and score
`communication`/`completion` down accordingly.

## 3. The trace fields you score on (already structured by `trace_parser`)
Per node trace (`RunTrace`): `exit_reason` (DONE|WAIT|BLOCKED|STOPPED|CRASHED), `duration_seconds`,
`total_tool_calls`, `unique_tools`, `error_tool_calls`, `exploration_ratio` (>0.6 = thorough),
`error_recovery_count`, `backtrack_count` (write→re-read = second-guessing), `final_text_snippet`,
`had_crash`; per turn: `has_thinking`, `text_snippet`, token counts. Read them; never recompute.

## 4. Score the run on five dimensions (1–5 integers, all five required)
Score the **run as a whole**, weighting per-node signals; when torn, let the weakest load-bearing
node set the floor.

- **planning** — did agents explore before acting? `exploration_ratio` and the first few tool
  calls per node; did the implementor read the architect's `scope_files` before editing? 5 = read
  relevant context before first edit, plan visible in `text_snippet`. 1 = wrote before reading;
  implementor ranged outside the design's scope.
- **error_handling** — did failures recover cleanly? Gate `needs_fix`/`retry` followed by a
  `proceed` next attempt; review/security loops converging in ≤ 2 re-entries; `error_recovery_count`
  near `error_tool_calls`. 5 = every failure recovered. 1 = identical errors repeated across
  attempts, a `had_crash`, or a loop that hit its `max`.
- **efficiency** — was work tight? Low `backtrack_count`, `total_tool_calls` near the minimum,
  `usd_spent` reasonable against `usd_ceiling`. 5 = no backtracking, no redundant reads. 1 = heavy
  backtracking or many redundant calls.
- **completion** — did it finish correctly? `state.json.status == done`, every gate
  `decision == proceed`, doc reached. 5 = clean `done`. 3 = finished but with re-entries or an
  escalation. 1 = `failed`/`blocked`, or doc never reached.
- **communication** — were the handoffs and reasoning clear? Per-node handoff sections specific;
  `has_thinking` present in reasoning-tier turns; final snippets summarise with caveats. 5 = clear,
  actionable. 1 = tool dumps, no thinking.

## 5. Identify findings — assign tier and fix_type together
A finding is a place the run did not go ideally. Each finding has: `id` (`F<N>`, unique, stable
across runs), `severity`, `tier`, `fix_type`, `target` (the concrete artifact the fix touches),
`evidence` (≤ 500 chars — a trace excerpt, a gate error line, an artifact snippet; never vague
prose), `suggested_action` (a one-line, act-without-re-reading-the-repo instruction), optional
`recipe` (tier-0 only), optional `known_issue_ref`.

### tier / fix_type decision tree (delivery/v1-native — the adaptation of CC-v1's fix_type enum)
Ask in order; first match wins. This preserves the spec §3.2 tier mapping: tier 0 auto-applies
under an eval gate, tier 1 becomes a human-merged PR, tier 2 escalates.

| # | Question | `fix_type` | `tier` | `target` form |
|---|---|---|---|---|
| 1 | Would a new/adjusted **eval fixture** (golden or negative) have caught or would prevent this? | `fixture` | **0** | `fixture:<rel_path>` |
| 2 | Is it a **numeric gate threshold** that should move within a bounded range (timeout, loop `max`, a count)? | `threshold` | **0** | `threshold:<gate_id>.<field>` |
| 3 | Would a change to a **gate check's logic** (new check, tightened check) have caught it at gate time? | `gate_check` | **1** | `gate:<gate_id>` or `check:<type>` |
| 4 | Would a **prompt edit to an agent** fix it (the agent lacked a constraint or a step)? | `agent_prompt` | **1** | `agent:<name>` |
| 5 | Would a **method edit to a skill** fix it (the skill's technique was inadequate)? | `skill` | **1** | `skill:<name>` |
| 6 | Does the fix require a **schema** change (a class schema or `delivery.workflow.schema`)? | `schema` | **2** | `schema:<file>#<field>` |
| 7 | Does it require a **graph** change (nodes, edges, routing, loop structure)? | `workflow` | **2** | `workflow:<node_or_edge>` |

Tie-break: prefer the lower tier only when it genuinely resolves the issue — a fixture that masks
a real prompt gap is not a fix. **Only tier-0 findings may carry a `recipe`** (the precise
mechanical change: the fixture content, or the threshold old→new value). Tier-1 findings give the
diff target and intent for a PR; tier-2 findings escalate with rationale. A finding targeting
`agent:retro`/`skill:retro` is never tier 0 (hard rule 9).

### severity ladder
- **critical** — the run shipped broken/insecure code; a gate was bypassed (`decision: proceed`
  recorded while the underlying check was false); a security finding reached release.
- **high** — a node failed and was forced through; a review/security loop hit its `max` without
  passing; doc skipped a load-bearing file unjustified; a scope/security escape the gate missed.
- **medium** — wasted tool calls, backtracking, a missing trace/artifact for one node, an
  over-broad scout, a design risk with no mitigation.
- **low** — cosmetic, opinion-level, "could shave duration here."

### always-blocking categories (carry ≥ `high`, and demand at least one finding each)
- `state.json.status != done` (failed / blocked / escalated) — a `high` finding explaining why.
- Any gate left terminal with `decision != proceed`.
- A review or security loop that hit `max` with a non-pass verdict.
- An implementation left `status: done` with its own `validation_command_passed: false`.

## 6. Decide your own status (not the pipeline's)
`status: done` if you retrospected cleanly — **even on a failed run**. `status: blocked` only if
you could not retrospect (no `state.json`, every trace missing). Never inherit the pipeline's
failure as your own. Set `fields.pipeline_status` to the run's real terminal status separately.

## 7. Write the retro artifact
Body sections, in order. Everything decision-relevant lives in the structured return; the body is
for the human reader.
- **Summary** — ≤ 5 sentences: the run's terminal status, the two or three top findings, whether
  the retrospective itself is complete, and whether the loop has actionable tier-0/1 inputs.
- **Scores** — the five dimensions in a table with a one-sentence, evidence-anchored justification
  each, and the /25 total.
- **Findings** — one bullet per finding mirroring the return (id, severity, tier, fix_type,
  target, action). No novel facts. If none: `- None.`
- **Assumptions** — explicit, one line each (e.g. "state.json is the authoritative ledger;
  artifacts are read for evidence, not routing").
- **Open questions** — or `- None.`
- **Handoff** — the priority order for the applier and the human, grouped by tier: which tier-0
  recipes to auto-apply first, which tier-1 diffs to PR, which tier-2 items to escalate. Do not
  restate the findings table.

## 8. Carry-forward discipline
On each run, a recurring issue keeps its **same F-id** so the loop can recognise a pattern; a
resolved issue retires its id (note it in the Summary), never reused. Escalate a finding's tier
or severity when the cheap fix has demonstrably failed across runs — a tier-0 fixture that keeps
not preventing the same class of bug is really a tier-1 prompt/skill gap; reclassify and say so.

## Guardrails
You never modify source, tests, artifacts, traces, agents, skills, schemas, or `state.json` — your
output is the retro. You never bump a version (delivery/v1 has no contract-version concept; that
is an open decision, not your call). You never trigger a downstream agent. You never attach a
machine recipe to anything above tier 0.
