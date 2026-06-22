# Cronos token-cost optimization plan

**Status:** proposal (no changes implemented)
**Author:** trace analysis, 2026-06-19
**Scope:** reduce token spend / price of agent execution with **no negative quality impact**.

---

## 1. Method & data

Analyzed all **345 run traces** in `.cronos/traces/*/[0-9]*.json`. Each trace carries
per-turn token counts (`input_tokens`, `output_tokens`, `cache_read_tokens`,
`cache_creation_tokens`), the resolved `real_model`, `exit_reason`, turn/tool-call
counts, and memory hit rate. Cost was computed with standard Anthropic per-MTok pricing
(Opus 15/75, write 18.75, read 1.50; Sonnet 3/15/3.75/0.30; Haiku 1/5/1.25/0.10).

### Headline numbers

| Metric | Value |
|--------|-------|
| Total estimated spend (345 runs) | **$1,212** |
| Tokens, all kinds | 1,281 M |
| └ cache **read** | **1,211 M (94.5%)** |
| └ cache **write** | 69 M |
| └ input / output | 0.4 M / 0.5 M |

**The entire cost is cache-read of accumulated conversation context.** Input/output
tokens are a rounding error. Cost ≈ `Σ(turns) × context_size_per_turn × read_price`.
Every optimization must therefore target one of three multipliers: **turns**,
**context size per turn**, or **price (model tier)**.

### Cost by model

| Model | Runs | Cost | % | Avg/run |
|-------|-----:|-----:|--:|--------:|
| claude-opus-4-7 | 44 | $531 | 43.8% | $12.1 |
| claude-sonnet-4-6 | 201 | $392 | 32.3% | $1.9 |
| claude-opus-4-8 | 23 | $263 | 21.7% | $11.4 |
| claude-haiku-4-5 | 36 | $27 | 2.2% | $0.74 |

Opus accounts for **65% of spend on 19% of runs**. An Opus run costs ~6× a Sonnet run
and ~16× a Haiku run, driven almost entirely by the 5× read-price multiplier × longer
contexts.

### Cost by exit reason

| exit_reason | Runs | Cost |
|-------------|-----:|-----:|
| DONE | 265 | $1,011 |
| **NO_STATUS** | **57** | **$163** |
| BLOCKED | 4 | $33 |
| STOPPED | 5 | $6 |

---

## 2. Findings (root causes)

### F1 — `NO_STATUS` is wasted spend on *completed* work ($163, 13%)
57 runs ended `NO_STATUS`. Inspecting their `final_text_snippet`, **the work was
actually finished** — analyses, reviews, and implementations are complete in the final
text. The failure is purely **STATUS-marker detection**: the `STATUS: DONE` line was
buried under MEMORY blocks, findings tables, or trailing prose, so `parse_status()`
didn't see it as the last line. One run's own output even describes the bug: *"the marker
is buried outside the window and returns None."* The worker then can't recognize
completion (stall / re-run). This is **pure waste with zero quality dependency.**

### F2 — Opus is used for implementation-grade work that Sonnet already does well
61 Opus runs perform file edits (`Edit`/`Write`) — i.e. real dev/implementation work, not
read-only reasoning — totaling **$789**. Direct in-pipeline comparison on the *implement*
phase: **Sonnet $5.4/run vs Opus $20.9/run (≈4×)**. Many of these Opus tasks are
mechanical implementation (slugs like `architect-*`, `review-*` that nonetheless edit
code, plus general dev tasks manually assigned to Opus). The pipeline already designates
`pipeline-implementor` = Sonnet; the leakage is **top-level tasks created with
`agent_model="opus"` (or `"default"` resolving to Opus)** for work that is implementation,
not architecture.

### F3 — Long turn counts multiply context cost
Opus runs average **55–56 turns**, Sonnet 69, Haiku 86; worst runs hit **120–172 turns**
with 50–130 tool calls. Because every turn re-reads the full accumulated context, a run
that re-explores the codebase (40 `Read`s + 57 `Bash`es of `worker.py` at many offsets)
pays cache-read on an ever-growing context dozens of times. The top-20 runs alone
($16–33 each) are dominated by this re-exploration pattern.

### F4 — Fixed context prefix is re-read every turn
Median initial cached prefix is **38k tokens** (mean 47k, max 307k). That prefix
(system prompt + auto-loaded `CLAUDE.md` (~5.3k tok) + injected agent/skill descriptions
+ task brief + memory) is read on every one of 55–86 turns. The `CLAUDE.md` module table
(183 lines / 19 KB) is reference material rarely needed in full mid-task; it is paid for
on every turn of every run.

### F5 — Low memory hit rate ⇒ re-discovery
`memory_hit_rate` is 0.0 on the runs sampled, including ones that re-read the same large
files repeatedly. Memory that captured "where X lives" would cut F3 re-exploration turns.
(Diagnostic — confirm before acting; see Tier 3.)

---

## 3. Recommended changes (ranked by $/risk)

All recommendations below are **quality-neutral or quality-positive**. Each notes the
lever (turns / context / price) and an evidence-based savings estimate. Estimates are
conservative and assume future workload mix ≈ historical.

### Tier 1 — pure wins, no quality tradeoff

**R1. Make STATUS detection robust (fixes F1). ~$120–150 recoverable.**
- Widen `parse_status()` so the marker is found even when followed by MEMORY blocks or
  trailing prose — scan the last *N* non-empty lines (or regex-search the whole final
  message) for a lone `STATUS: (DONE|WAIT|BLOCKED)`, rather than requiring it to be the
  literal last line. File: `backend/app/agent.py` (`parse_status`, `_STATUS_LINE`).
- Reinforce in `task-finalize` skill + `STATUS_CONTRACT` that **no MEMORY/CRONOS_REMEMBER
  block may follow the STATUS line** (move memory capture before finalize emits STATUS).
- This recovers work the system already paid for. Zero model/quality change.

**R2. Trim the always-on context prefix (fixes F4). ~15% on every run's read cost.**
- Slim `CLAUDE.md`: keep the architecture/state-machine/auth sections; move the 90-row
  "Key modules" + "frontend module" tables to a separate `docs/MODULES.md` that agents
  `Read` on demand. The module table is a lookup, not per-turn context.
- Audit what gets injected via `--append-system-prompt` and per-task memory; cap memory
  injection to top-K by confidence.
- Lever: context-per-turn × (every turn of every run). Even a 30% prefix reduction on a
  38k prefix × ~60 turns × 345 runs is large because it compounds with read price.

### Tier 2 — model right-sizing (fixes F2). ~$200–300, low risk if scoped

**R3. Default implementation-grade tasks to Sonnet; reserve Opus for genuine
reasoning gates.** Sonnet 4.6 already handles the *implement* phase at equal quality for
4× less. Concretely:
- Keep Opus for: `pipeline-architect`, `pipeline-reviewer`, `pipeline-retro`,
  `security-officer`, `test-architect` (decision/judgment gates — quality-sensitive).
- Move to Sonnet: top-level dev tasks currently created with `agent_model="opus"` whose
  work is implementation (editing code to a known design). Add guidance in `create-task`
  / `create-goal` skills + UI default so "default" maps to Sonnet for dev work, with Opus
  an explicit opt-in for architecture/ambiguous tasks.
- **Do not** blanket-downgrade reviewers/architects — that is where Opus earns its cost.
- Validate with a 5–10 task A/B before making it the default; revert any task that
  regresses. (Quality guardrail.)

**R4. Standardize the Opus tier on Opus 4.8 (1M).** Spend splits 4-7 ($531) vs 4-8
($263) at the same price; 4-8 is newer and the project already uses it for
`security-officer`/`test-architect`. Update `pipeline-architect`, `pipeline-reviewer`,
`pipeline-retro` frontmatter from `claude-opus-4-7` → `claude-opus-4-8` for consistency
and any per-token efficiency gains. No expected quality loss (newer model).

### Tier 3 — turn / re-exploration reduction (fixes F3, F5). ~$100–150, needs validation

**R5. Cut re-exploration turns by improving upstream hand-off.**
- Ensure `pipeline-implementor`/`reviewer` receive the design's `scope_files` and the
  prior phase's report inline, and instruct them to read **only** scoped files + the diff
  rather than re-walking the codebase. The 128-tool-call reviewer trace re-read
  `worker.py` at ~15 different offsets — a symptom of missing scoped context.
- Prefer `git diff` over re-reading whole files in review/test phases.
- Lever: fewer turns ⇒ linearly fewer context re-reads.

**R6. Raise memory hit rate (fixes F5).** Confirm the 0.0 hit rates are real (not a
trace-capture gap). If real, the trust-loop memory isn't surfacing "where things live."
Tighten `write-memory` usage in `task-finalize` to record file/symbol locations for
touched areas, and verify retrieval injects them. Each avoided re-discovery saves several
high-context turns. Diagnostic-first — measure before/after.

---

## 4. Estimated impact

| Change | Lever | Est. savings | Risk |
|--------|-------|-------------:|------|
| R1 STATUS robustness | recover waste | $120–150 | none |
| R2 trim prefix | context/turn | ~$150 | none |
| R3 Sonnet for impl | price | $200–300 | low (A/B gated) |
| R4 Opus→4.8 | price/efficiency | minor + consistency | none |
| R5 less re-exploration | turns | $100–150 | low |
| R6 memory hit rate | turns | TBD (diagnose) | none |

**Aggregate plausible reduction: ~30–45% of spend** (~$350–550 over a comparable
345-run window), front-loaded on R1+R2+R3 which carry no quality risk. The dominant
structural fact — 94% of cost is cache-read of accumulated context — means the highest
leverage is **fewer turns and a smaller per-turn context**, with model tier as the
multiplier on top.

---

## 5. Suggested sequencing

1. **R1 + R2** first — pure wins, touch `agent.py` + `CLAUDE.md`/skills only.
2. **R4** — one-line frontmatter edits across 3 agent files.
3. **R3** — change defaults, run a 5–10 task A/B, then flip the default.
4. **R5 + R6** — instrument memory hit rate, then refine hand-off/memory prompts.

No changes implemented; this document is the deliverable.
