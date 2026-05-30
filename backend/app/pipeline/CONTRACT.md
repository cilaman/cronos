# CC-v1 — Cronos Agent Contract v1.0

`CC_VERSION = "1.0"`

The single canonical artifact format every pipeline agent in
`backend/app/pipeline/` produces. Adapted from Delivery Notes' Agent Contract
v1.0 (`/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md`) for
the Cronos runtime.

This file is the human-readable spec. The machine-readable counterpart
(field names, section names, rule names, constants) lives in
[`contract.py`](contract.py). The two must agree; if they ever drift,
`contract.py` is authoritative for code and this file is authoritative for
intent.

This task (1.1) defines the contract only. Per-class schemas, the verifier,
the normalizer, and the regression harness are tasks 1.2–1.5. No agents
are referenced yet.

---

## 1. The artifact

Every pipeline agent produces exactly one markdown artifact at:

```
{space}/.cronos/pipeline/{goal_slug}/{phase}-report-{goal_slug}.md
```

where:

- `{space}` is the absolute space directory (e.g. `/data/spaces/cronos-development`).
- `{goal_slug}` is the verbatim slug owned by the orchestrator; agents NEVER
  re-derive it (see §6).
- `{phase}` is the phase identifier from the per-class schema (e.g.
  `scout`, `architect`, `backend-impl`). Phase identifiers are defined in
  task 1.2 (per-class schemas) — not in this file.

Artifacts live under `.cronos/` so they share fate with the rest of
Cronos' on-disk state and inherit the existing gitignore for `.cronos/`.

The artifact has two parts:

1. A strict YAML frontmatter header (§2).
2. A markdown body with required H2 sections in a fixed order (§4).

---

## 2. YAML header — mandatory fields

```yaml
---
cc_version: "1.0"
agent: <agent name from the pipeline registry>
slug: <goal slug, verbatim from orchestrator>
phase: <phase identifier from per-class schema>
status: done | partial | blocked | failed
confidence: 0.0-1.0
inputs_used:
  - <workspace-relative forward-slash path or identifier>
outputs_produced:
  - <workspace-relative forward-slash path>
blockers: []
next_consumer: <downstream agent name or "user">
metrics:
  tool_calls: <int>
  files_read: <int>
  memory_hits: <int>
---
```

The full canonical field order is exported as `HEADER_FIELDS` in
[`contract.py`](contract.py). Per-class schemas (task 1.2) MAY add extra
fields after `metrics` (e.g. `coverage_summary` for research-class agents)
but MUST NOT omit or reorder these.

### 2.1 `cc_version`

Every artifact stamps the contract version it was written against. Verifier
rejects artifacts whose `cc_version` is not in the set of currently-supported
versions. Bumped on breaking schema changes; additive 1.x changes do not bump
it.

### 2.2 `status`

The legal values are `done`, `partial`, `blocked`, `failed`. Their meanings
are documented inline in `contract.py::STATUS_VALUES`. The cross-field rules
R1 and R2 (§5) constrain which combinations are coherent.

### 2.3 `inputs_used` / `outputs_produced` — path format (R7)

- MUST be workspace-relative (no leading `/`, no drive letter).
- MUST use forward slashes only.
- MUST NOT be absolute paths.

R7 enforces this. The normalizer (task 1.4) auto-fixes backslashes
→ forward slashes; everything else is a hard fail.

### 2.4 `next_consumer`

The downstream agent name (e.g. `architect`, `backend-impl`) or the literal
string `"user"` when the next stop is human review. The string `"user"` is
exported as `NEXT_CONSUMER_USER_SENTINEL` in `contract.py`.

The orchestrator (built in a later goal — not this one) reads this field to
route the next phase. It is the primary structured handoff signal.

### 2.5 `metrics` — split ownership

| Owner | Field | Meaning |
| --- | --- | --- |
| **Agent** | `tool_calls` | Every tool invocation, including the final Write of the agent's own artifact. No "substantive only" filtering. |
| **Agent** | `files_read` | Count of unique files opened via the Read tool. See §2.5.1 for what counts. |
| **Agent** | `memory_hits` | Count of memory_store entries the agent relied on (typically items surfaced via the `# Memory Context` prompt block, plus any explicit memory lookups). |
| **Trace** | `duration_s` | Wall-clock time. Derived post-hoc from the run trace by `trace_parser`. **Agents NEVER write this.** |
| **Trace** | `token_spend` | Token count for the agent invocation. Derived from the run trace. **Agents NEVER write this.** |

The agent-written subset is exported as `AGENT_REPORTED_METRICS`; the
trace-derived subset as `TRACE_OWNED_METRICS`. If an agent-written artifact
contains either trace-owned field, the verifier flags it as a contract
violation.

#### 2.5.1 Counting `files_read`

`metrics.files_read` counts every unique file opened via the Read tool
during the agent's run, **not** just the ones it wrote to. The common
under-counting error is forgetting to include the upstream artifact the
agent was given as input (the scout report, the architect report, the goal
brief, etc.). Glob / Grep without a follow-up Read does NOT contribute.

R4 (§5) cross-checks: `files_read + memory_hits >= len(inputs_used)`. If R4
fails, the most common cause is the upstream input doc being listed in
`inputs_used` but not added to `files_read`.

---

## 3. The no-prose-parsing rule

> **Orchestrators and downstream agents NEVER parse markdown prose to make
> routing or gating decisions. Every decision-relevant fact lives in the
> YAML header (or per-class schema extensions). If a routing decision
> depends on something not in the header, the contract or schema is
> incomplete — escalate, do not prose-parse.**

This is the single rule from which most others derive. Exported verbatim as
`NO_PROSE_PARSING_RULE` in `contract.py` so the same string can appear in
agent prompts and verifier error messages.

Consequences:

- The verifier reads only the YAML header (plus section presence, not
  section content).
- Per-class schemas (task 1.2) extend the header with whatever extra
  structured fields downstream agents need. They do **not** add
  prose-parsing escape hatches.
- Markdown bodies are for the human reader and for the agent that
  composed them — not for the runtime.

---

## 4. Markdown body — required sections

H2 headings, in this exact order:

1. `## Summary` — max 5 sentences, decision-oriented.
2. `## Coverage` — what was searched / inspected and what was excluded.
3. `## Findings` — the substantive output. Per-class schemas MAY rename
   this slot to `## Decisions` or `## Top relevance`. The verifier accepts
   any name in `FINDINGS_SECTION_ALIASES`.
4. `## Assumptions` — explicit assumptions, one-line justification each.
5. `## Open questions` — may be empty, but the section MUST exist. Agents
   with `status ∈ {blocked, failed}` MAY rename to `## Blockers`. The
   verifier accepts either (see `OPEN_QUESTIONS_SECTION_ALIASES`).
6. `## Next consumer brief` — max 300 words, compressed handoff for the
   downstream agent named in `next_consumer`.

Per-class schemas MAY require additional sections after `Next consumer
brief`. They MUST NOT omit any of these or change their order.

The exact canonical list is exported as `REQUIRED_SECTIONS` in
[`contract.py`](contract.py).

---

## 5. Cross-field rules R1–R7

Enforced by the verifier (task 1.3) on every artifact. R-rule IDs are
exported as `R_RULES` in `contract.py` and referenced verbatim in verifier
output, normalizer logs, and regression fixtures.

| ID | Rule | What fails |
| --- | --- | --- |
| **R1** | Non-empty `blockers[]` requires `status ∈ {blocked, failed}`. | `status=done` or `status=partial` with blockers listed → fail. Normalizer coerces `status=partial + blockers` → `status=blocked`. |
| **R2** | `status=done` requires `confidence >= 0.7`. | `status=done` + `confidence=0.5` → fail. |
| **R3** | `confidence` MUST be in `[0.0, 1.0]`. | `confidence=1.2` → fail. |
| **R4** | `metrics.files_read + metrics.memory_hits >= len(inputs_used)`. | `inputs_used=[a, b, c]` + `files_read=1` + `memory_hits=0` → fail. R4 catches the "fictional inputs_used" pattern; every listed input must be accounted for by either a Read or a memory hit. |
| **R5** | `outputs_produced[0]` SHOULD match the agent's canonical artifact path. | Primary artifact in the wrong slot → warning, not hard fail. |
| **R6** | `slug` MUST equal the slug the orchestrator passed; agents never re-derive. | Agent writes `slug: my-goal-v2` when orchestrator passed `my-goal` → fail. |
| **R7** | Paths in `inputs_used` / `outputs_produced` MUST be workspace-relative forward-slash. | `c:\path\foo` or `/abs/path` → fail. Normalizer fixes backslash → forward slash. |

Per-class schemas (task 1.2) MAY add class-specific rules (e.g. `R-impl-*`
for implementation-class, `R-rev-*` for review-class). Those are scoped to
the schema that defines them and do not appear in the base `R_RULES` tuple.

---

## 6. Slug discipline (R6)

The goal slug is owned by the orchestrator. It is generated once, at the
start of the pipeline, and passed verbatim to every agent invocation. Agents
**NEVER** re-kebab-case, suffix, normalize, or otherwise reconstruct the
slug from the goal title or any other field.

If an agent needs sub-slugs for fan-out (e.g. running N scout instances in
parallel), the orchestrator composes the sub-slugs as
`<goal_slug>--<sub_topic_slug>` and passes each instance its composed
identifier. The agent stays "slug verbatim".

In Cronos terms: the goal's slug (the `id` of the goal task in
`backend/app/storage.py`) IS the pipeline slug. There is no second source
of truth.

---

## 7. Cronos deviations from Delivery Notes v1.0

This section is the changelog versus the upstream Delivery Notes contract.
Read it alongside `/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md`.

### 7.1 `kb_hits` → `memory_hits`

Delivery Notes has a `.kb/` substrate (validated KB pages, episodic chunks,
`kb_search` tool). Cronos does not — its equivalent is the per-space memory
store (`backend/app/memory_store.py`) surfaced to agents through the
`# Memory Context` prompt block (`backend/app/memory_retrieval.py`,
`backend/app/agent.py::build_prompt`).

`memory_hits` counts memory_store entries the agent relied on. The semantics
are the Cronos analogue of `kb_hits` — both measure "did the agent consult
the validated-decisions substrate before re-deriving things".

The Delivery Notes "KB-first preflight" rule (their §9) does not carry over
literally; the Cronos equivalent is the existing memory_retrieval pipeline,
which surfaces relevant memories automatically. The contract here merely
asks the agent to count and report what was actually used.

### 7.2 Agents NEVER write `duration_s` / `token_spend`

In Delivery Notes, the orchestrator stamps `duration_s` and `token_spend`
into the artifact header post-hoc. In Cronos, those values are derivable
from the run trace (`backend/app/trace_parser.py`, `backend/app/trace_store.py`)
without rewriting the artifact, so they live in the trace and not in the
artifact at all. The artifact stays append-only.

If an agent-written artifact contains either field, the verifier (task 1.3)
flags it as a contract violation. The normalizer (task 1.4) strips them
silently when seen — they were not the agent's to write.

### 7.3 Artifact path location

Delivery Notes: `.ai/pipeline/{slug}/<phase>-report-{slug}.md`.
Cronos: `{space}/.cronos/pipeline/{goal_slug}/<phase>-report-{goal_slug}.md`.

The Cronos location lives under the existing per-space `.cronos/` state
directory, which is already excluded from version control. No new gitignore
rules required.

### 7.4 No `coverage_summary.strategies` enum in the base

Delivery Notes' base contract pins a strategy enum (`kb_search`,
`grep_symbol`, etc.) shaped for their scout class. Cronos pushes that into
per-class schemas (task 1.2). The base contract here does not constrain
`coverage_summary` — only the `## Coverage` section name.

### 7.5 `cc_version` is a header field

Delivery Notes encodes the contract version implicitly (it lives in the
contract document path). Cronos stamps `cc_version` into every artifact so
that a future v2.0 verifier can reject v1.x artifacts cleanly and vice
versa.

### 7.6 No `kb-first preflight` (§9), `sandboxed architect convention` (§13)

Both of those Delivery Notes sections address concerns specific to their
runtime (KB-as-source-of-truth, SDK worktree base-commit bug F-24).
Cronos has different primitives:

- Memory store + memory retrieval already give every agent the validated-
  decisions substrate without a preflight step.
- Cronos already has a worktree-per-task model with sound base-commit
  selection, so F-24's workaround is not needed.

These sections may be revisited in CC-v1.x if a Cronos-side analogue
emerges, but they are deliberately absent from v1.0.

---

## 8. What this task delivers

- `contract.py` — header field list (`HEADER_FIELDS`), required-section list
  (`REQUIRED_SECTIONS`), R-rule names (`R_RULES`), status values
  (`STATUS_VALUES`), metrics ownership tuples (`AGENT_REPORTED_METRICS`,
  `TRACE_OWNED_METRICS`), artifact path template (`ARTIFACT_PATH_TEMPLATE`),
  `CC_VERSION = "1.0"`.
- `CONTRACT.md` — this document.

No agents are wired up. No verifier exists yet. Per-class schemas come in
task 1.2; the verifier in task 1.3; the normalizer in task 1.4; regression
fixtures in task 1.5.

## 9. Version history

- **v1.0** (2026-05-30) — Initial Cronos adaptation of Delivery Notes
  Agent Contract v1.0. Deltas listed in §7.
