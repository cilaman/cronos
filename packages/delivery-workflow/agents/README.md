# Agents — delivery/v1 Bundle

The agent roster: 9 agents spanning research → design → build → verify → docs. Each agent is
a role definition + input/output contract + hard rules (no `.cronos` paths, no Cronos API, no
`STATUS:` sentinels, ≤~80 lines). **Paired skills** carry the method/craft — the agent owns the
role, the skill owns the how.

## Agent roster & I/O contract

| Agent | Tier | Role | Consumes | Produces | Modifies | Paired skill |
|-------|------|------|----------|----------|----------|--------------|
| **scout** | Haiku | Recon (upfront + dispatchable) | brief + memory + codebase | `scout-report` (`research`) | — | — |
| **analyst** | Sonnet | Requirements & scope | scout-report | `analysis-report` (`analysis`): has_ui, REQ-ids | — | `analysis` |
| **frontend-designer** | Sonnet | Mocks + FE spec (if `has_ui`) | analysis-report | `frontend-spec` (`frontend`) | — | `frontend` |
| **architect** | Opus | Iterations DAG + DD contract | analysis + FE spec | `design-report` (`design`): DD-ids, risks[] | — | `design` |
| **test-architect** | Opus | Test suite + test plan | design-report | test suite + `test-plan` (`test`) | test files | `test-design` |
| **implementor** | Sonnet | Build per-iteration | design-report (one `iterations[]` entry) | `impl-report` (`implementation`) | source code | `implement` |
| **reviewer** | Opus | Judge diff vs design | design + impl diff | `review-report--attempt{N}` (`review`): verdict, findings[] | — | `code-review` |
| **tester** | Sonnet | Execution + coverage | test suite + built code | `test-report` (`test`) | — | — |
| **doc-sync** | Haiku | Update docs for changes | impl + design + code | `doc-report` (`doc`) | doc files | `doc` |
| **retro** | Opus | Post-run retrospective & scoring | run state (state.json, events.jsonl, artifacts, traces) | `retro-report` (`retro`): scores, tier/fix-type findings | — | `retro` |

**The Modifies column is the guardrail:** only three agents write existing project files
(test-architect, implementor, doc-sync), over disjoint file trees. The three agents that *judge*
quality (reviewer, tester, retro) have no Edit tool, so they cannot patch what they evaluate.

---

## Structured return: `delivery_status`

Every agent emits a **structured control signal** (the parsing-gate's routing surface), not a
free-text `STATUS:` line. Format (fenced YAML):

````
```delivery_status
{
  "status": "done | blocked | needs_fix | failed",
  "artifact_paths": ["path/to/report.md"],
  "produces": "research | analysis | design | implementation | review | test | doc | frontend | retro | improvement",
  "fields": {
    "verdict": "pass | needs_fix",              # for reviewer, tester gates
    "has_ui": true,                              # for analyst → frontend branch
    "finding_class": "architectural | local",   # for reviewer routing
    "req_ids_covered": ["REQ-001", "REQ-002"],  # for analyst/design gates
    "dd_ids_covered": ["DD-001"],
    "files_changed": ["src/x.py", "tests/y.py"],  # for implementor
    "validation_command_passed": true,          # for impl gate
    "coverage_pct": 82.5                         # for tester gate
  },
  "open_questions": [],
  "telemetry": { "tokens": 12345, "usd": 0.18, "seconds": 42 }
}
```
````

**Rules:**
- `status`: agent's own exit code (done = success; blocked = manual decision needed; needs_fix
  = can retry; failed = unrecoverable).
- `artifact_paths`: array of paths the runtime gave you (write artifact there, never hardcode
  paths).
- `produces`: the artifact class, matching the node's `produces.class`.
- `fields`: the routing surface — agent reads these from your report/computation, struct is not
  nested, no arbitrary nesting. Omit unused keys.
- `open_questions`: array of strings (for escalation gates, not for control flow).
- `telemetry`: cumulative tokens/usd/seconds *this run* (Cronos fills if not emitted).

---

## Tool allowlists — the guardrails

Each agent's `tools` array in the workflow defines what it may do. Reading the entire codebase
is "recon's job, not yours"; writing non-artifact files is off-limits. Tool lists are **exact**
(no wildcards, no "and maybe this one too").

| Agent | Tools | Notes |
|-------|-------|-------|
| scout | Read, Grep, Glob, Bash | Read-only recon; no Write (artifact is written by runtime) |
| analyst | Read, Grep, Glob, Bash, Write | Write for own artifact only (no Glob mutations) |
| frontend-designer | Read, Grep, Glob, Bash, Write | Write for own artifact only |
| architect | Read, Grep, Glob, Bash, Write | Write for own artifact + re-design revisions only |
| test-architect | Read, Edit, Write, Bash, Grep, Glob | Can Edit test files; Write own artifact + test suite |
| implementor | Read, Edit, Write, Bash, Grep, Glob | The app-source writer — free to edit source files in scope |
| reviewer | Read, Grep, Glob, Bash, Write | **No Edit** by design — reads diffs, writes findings only |
| tester | Read, Bash | Execution only; no Write (results POSTed via the runtime) |
| doc-sync | Read, Glob, Bash, Write | Can Write doc files + own artifact; no Edit (regenerate, don't patch) |
| retro | Read, Grep, Glob, Bash, Write | **No Edit** — reads run state, writes findings only (propose, never apply) |

**Guardrail principle:** if an agent's job is to *judge* (reviewer, tester), it has no Edit.
If its job is to *write* a specific tree (tests, source, docs), it has Edit only for that tree.

---

## Harvest-then-author pattern

**The pattern:** Do not write agents from scratch. Instead:

1. **Harvest** — Identify an existing agent/skill in Cronos or a prior pipeline that plays this
   role (or a closely adjacent one). Read its method, its outputs, its I/O.
2. **Adapt the role** — Re-author the agent definition (markdown frontmatter + prose role) to
   match `delivery/v1`: emit `delivery_status`, drop `verify.py` calls, narrow scope, keep
   ≤~80 lines. The role definition should *not* carry implementation detail; it defines the
   input/output contract and the hard rules. See `reviewer.md` exemplar.
3. **Craft the skill** — The agent definition references a paired skill (except scout, tester).
   The skill carries the detailed method. See `skills/code-review/SKILL.md` exemplar.

Why:
- **Portability** — agents are small, definition-focused; skills are large, method-focused. A
  skill can have many pages; an agent has ~60 lines. Moving agents between runtimes is cheap
  (no embedded logic). Runtimes can apply their own skill hooks (e.g., Cronos hooks vs
  standalone CC hooks).
- **Clarity** — the agent role is a contract; the skill is the implementation recipe. Users
  (harness authors) read the agent; developers working on delivery craft read the skill.
- **Evolution** — if a skill's method changes, agents stay in place (same role). The runtime
  can swap skill implementations (e.g., fancier lint rules in a future skill) without touching
  agents.

---

## Hard rules (load-bearing — do not relax)

1. **No `.cronos` paths** — agents are portable across runtimes; never hardcode `.cronos/`,
   `.claude/`, or runtime-specific state paths. Paths come from the executor's `inputs` and
   `artifact_paths` parameters.
2. **No Cronos API calls** — no `curl http://backend:8000/api/...`, no task creation, no
   memory manipulation. The executor provides the interface; the harness is the control plane.
3. **No `verify.py` / `STATUS:` sentinels** — emit `delivery_status` JSON only. No legacy
   `STATUS: DONE`/`BLOCKED` lines (they break parsers expecting the new format).
4. **No loop or routing logic** — agents emit verdicts and findings; the harness routes on
   them. Never decide "I'll run scout again" or "skip the next phase." That is the harness's
   job via `edges` and `loop:` blocks.
5. **≤~80 lines** (agent definition) — a role definition, inputs, outputs, hard rules, and
   return schema. Method goes in the skill. If the agent grows past 80 lines, extract method
   to the skill and reference it.
6. **Paired skill owns the method** — agent says "Load the X skill"; skill says "Here's how to
   X." No embedded step-by-step in the agent. Exception: scout and tester (simple and portable
   enough that they may not need skills; doc-sync is a thin wrapper, same).
7. **Telemetry is optional at agent-write time** — the runtime fills it if absent. If you call
   the Agent tool (scout recon), add `{ "tokens": N, "usd": M, "seconds": S }` to your return.

---

## Recon-on-demand (intra-node capability)

When a node sets `recon: on`, the workflow **grants** that agent the capability to dispatch
the scout subagent at *its own startup*, with a task-specific brief. Scout returns a fresh,
focused map (not a gated artifact, not seen by the router).

**Who gets it:**
- **implementor** ← strongest case: fresh per-iteration map of a changing codebase.
- **reviewer** ← moderate: map of invariants around the diff being reviewed.
- **architect** ← moderate, mainly on re-design: see what the impl actually did vs the design.
- analyst, frontend-designer, doc-sync, tester ← `off` (no recon needed).

**Rules:**
- Recon output is **transient working context** for the calling agent only — not a gated
  artifact, not a DAG node, never routed on.
- Agent's own `tools` list **does not declare `Agent`** — the workflow grants it; agent just
  calls it (isolation boundary is kept at the harness, not the agent).
- Telemetry for recon (tokens, cost) **is visible and counts against the run budget**, so its
  use is justified by (e.g.) the iteration cost of a fresh map. A recon call that changes
  *what runs next* is a spec violation.

---

## Inputs & artifact paths (never hardcode)

The executor provides all paths via **function parameters** (or in a Cronos context, via task
environment):

- **`inputs`** — map of `{ upstream_node_id: [artifact_path, ...] }`, one per edge in the
  harness. Read these to load prior reports.
- **`artifact_paths`** — array of paths where you must write your output (one path per
  `produces.class`, or looped attempts). Write there and nowhere else.

Never hardcode a path like `/some/fixed/location/report.md`. The executor controls where
artifacts live (`.cronos/pipeline/...` in Cronos, a temp dir in the standalone runner, etc.).

---

## Example: implementor agent

```markdown
---
name: implementor
description: Builds one iteration from the design's iterations[] list. Emits an implementation artifact (class=implementation) with files_changed[] and validation_command_passed (outcome-gated). The design's iteration scope is the allowed universe — only files in scope_files[] may be changed.
model: sonnet
tools: Read, Edit, Write, Bash, Grep, Glob
recon: on
---

# implementor

You build one iteration from the design contract. Your output is the changed code; the gate
verifies it compiles and passes linting. You **respect scope**: the design's `iterations[]`
entry defines `scope_files[]` — the universe of files you may touch. Any file outside that
scope is a violation (the reviewer will catch it, but fail sooner by respecting the boundary).

**Load the `implement` skill for the method.** It carries how to read the design, stage changes
iteratively, validate, and emit the structured return.

## Inputs
- **`design`** — the design contract. Read `iterations[<your_index>].scope_files[]` to see
  what files you may change.
- **`prior_review`** (on retry) — prior review findings; address blocking ones.

## Output — the implementation artifact + the structured return

Write the impl artifact (class `implementation`), then emit:

```delivery_status
{
  "status": "done",
  "produces": "implementation",
  "artifact_paths": ["<runtime-given path>"],
  "fields": {
    "files_changed": ["src/x.py", "tests/y.py"],
    "validation_command_passed": true
  },
  "open_questions": []
}
```

## Hard rules
1. **Scope respect.** Only edit files in `iterations[<your_index>].scope_files[]`.
2. **Validation.** Before writing the artifact, run the validation command (typically `pytest
   -xvs`) and set `validation_command_passed` to the exit code (0 = true).
3. **One iteration per run.** You run once per `iterations[]` entry; don't loop or make
   decisions about what's next.
```

---

## Checklist: before committing an agent

- [ ] Agent frontmatter: name, description, model, tools, recon (if applicable)
- [ ] Agent prose: ≤80 lines, role only (method goes in skill)
- [ ] Inputs documented: what you read from the harness
- [ ] Output documented: artifact + structured return (delivery_status JSON)
- [ ] Hard rules: scope, no .cronos, no routing logic, no STATUS: lines
- [ ] Paired skill: written, if the agent references one
- [ ] Tool allowlist: exact match to the delivery/v1 table above
- [ ] Test: if the skill has a complex method, write a test for the method (not the agent,
  which is portable)

---

## References

- **Spec**: `../../docs/delivery-pipeline/delivery-v1-docs/delivery-v1-spec.md` (§4.1 roster,
  §4.2 recon, §8 return format)
- **Exemplar agent**: `../../docs/delivery-pipeline/delivery-v1-docs/delivery-workflow/agents/reviewer.md`
- **Exemplar skill**: `../skills/code-review/SKILL.md`
