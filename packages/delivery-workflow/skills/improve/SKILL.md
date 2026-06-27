---
name: improve
description: Tier-0 self-improvement applier for delivery/v1. Reads the retro artifact's delivery_status fence, selects only tier-0 findings with machine-readable recipe fields, snapshots all touched files, applies each recipe (fixture or threshold), runs the delivery/v1 eval corpus, keeps changes on green, rolls back ALL snapshots on red. Emits a delivery_status (class improvement) and writes improve-report.md. This is a native port of the auto_improver.py Tier-0 control flow re-targeted for delivery/v1 paths and recipe semantics.
---

# improve

Apply Tier-0 self-improvements from a retro artifact. You read, filter, snapshot, apply, eval,
keep-or-rollback, and report. You never read a finding twice, never apply beyond tier 0, and
never touch the retro artifact itself.

## 0. Safety invariants (load-bearing — never relax)

1. **Tier-0 only.** Apply only findings with `tier == 0` AND `fix_type ∈ {fixture, threshold}`
   AND a present, non-null `recipe` field. Skip everything else silently.
2. **Never apply a finding targeting `agent:retro` or `skill:retro`.** Hard block — an agent
   must not silently rewrite the thing that critiques it. Escalate such a finding instead.
3. **Snapshot BEFORE any write.** For every file you will touch, capture its current content
   (or record its non-existence) before the first write. If a file is touched more than once,
   the first capture wins (snapshot the original state).
4. **All-or-nothing on eval failure.** If the eval corpus exits non-zero, restore **every**
   snapshot entry — including files created from scratch (delete them). Report
   `tier0_rolled_back` equal to the count of findings that had been applied.
5. **Never modify the retro artifact.** It is your input; you read it once. Never edit or
   delete it. Never write to `state.json` or any other run ledger.
6. **Blast-radius limit.** `fixture` recipe targets must resolve to paths under
   `packages/delivery-workflow/` (relative to repo root). Reject any path with `..` segments or
   that resolves outside that directory. `threshold` recipe targets must be YAML keys inside
   delivery/v1 YAML config files (`packages/delivery-workflow/*.yaml`). Reject anything else.
7. **No version bump.** delivery/v1 has no contract-version concept. Do not bump any version
   constant. Do not edit `contract.py` or CC-v1 schema `cc_version` fields.

---

## 1. Locate and parse the retro artifact

The runtime supplies the retro artifact path (from the `g-retro` node's `artifact_paths`). Parse
the `delivery_status` fence inside it — do NOT regex-scrape the body. The structured fence is the
machine surface. Extract `fields.findings[]`.

If the retro artifact is missing or its `delivery_status` fence is absent/malformed → emit
`status: failed`, `errors: ["retro artifact not found or unparseable"]`, stop.

---

## 2. Classify all findings via the authoritative classifier

Run `classify_findings()` from `lib.improve` on `fields.findings[]` to partition
every finding into `tier0 / tier1 / tier2` (DD-003, fix_type-authoritative):

```python
from lib.improve import classify_findings
routed = classify_findings(findings)
# routed.tier0 — these go to Step 3 (Tier-0 apply)
# routed.tier1 — these go to Step 6 (Tier-1/Tier-2 back-half)
# routed.tier2 — these go to Step 6 (Tier-1/Tier-2 back-half)
```

The `tier` value in each finding is **ignored** — `fix_type` is authoritative:
- `gate_check`, `agent_prompt`, `skill` → **tier1** (PR path, never in-place)
- `schema`, `workflow` → **tier2** (escalate only)
- `fixture`, `threshold` (or anything else) → **tier0** (in-place apply)

**The Tier-0 apply step (Steps 3–5) consumes ONLY `routed.tier0`.**

If `routed.tier0` is empty, skip Steps 3–5 (set `tier0_applied: 0,
tier0_rolled_back: 0, errors: []`) and proceed to Step 6.

---

## 3. Snapshot all touched files

Before writing anything, for each candidate determine the file path(s) it will write:
- `fixture` finding: target is `fixture:<rel_path>` — the file at `<repo_root>/<rel_path>`.
- `threshold` finding: target is `threshold:<gate_id>.<field>` — resolve to the YAML config
  file for that gate (e.g. `packages/delivery-workflow/delivery.workflow.yaml`).

For each resolved file path:
- If file exists: read its current bytes into the snapshot dict (key = absolute path).
- If file does not exist: record `None` in the snapshot dict (rollback = delete).

Only capture once per path (first-write wins; later passes on the same file use the original).

---

## 4. Apply each recipe

### 4a. `fixture` recipe

`target` form: `fixture:<rel_path>` where `<rel_path>` is relative to repo root.

```
Validate: rel_path must start with "packages/delivery-workflow/"
Validate: no ".." in path segments
Validate: rel_path resolves inside packages/delivery-workflow/ (no symlink escape)
Write: recipe.content → <repo_root>/<rel_path> (create parent dirs as needed)
       Append a trailing newline if content does not end with one.
```

On any validation failure: add an error string to `errors[]`, skip this finding (do NOT apply
it), continue to the next candidate.

### 4b. `threshold` recipe

`target` form: `threshold:<gate_id>.<field>` (e.g. `threshold:g-tests.max`).

`recipe` carries: `{old: <old_value>, new: <new_value>}`.

```
Resolve the config YAML file that contains this threshold. For delivery/v1:
  - Numeric gate thresholds (loop max, budget.usd_ceiling) live in
    packages/delivery-workflow/delivery.workflow.yaml
  Parse the YAML, locate the key path for <gate_id>.<field>.
  Validate: recipe.old matches the current value (cast to the appropriate type).
    If mismatch → add error, skip this finding, continue.
  Apply: set the key to recipe.new (same type as old; for integers cast new to int).
  Re-validate the mutated YAML against packages/delivery-workflow/schemas/delivery.workflow.schema.yaml.
    If schema-invalid → restore this file from snapshot, add error, skip this finding, continue.
  Write the mutated YAML back to the file.
```

---

## 5. Run the eval corpus

After all candidates have been applied (or skipped with errors), run the delivery/v1 eval
corpus:

```sh
DELIVERY_EVAL_CMD="${DELIVERY_EVAL_CMD:-pytest packages/delivery-workflow/tests/ -q --no-header}"
```

If `DELIVERY_EVAL_CMD` is set in the environment, use it. Otherwise default to
`pytest packages/delivery-workflow/tests/ -q --no-header`. Run from repo root.

**Exit code 0** → evals green → keep all changes.

**Exit code non-zero** → evals red → rollback:
- Restore every snapshot entry:
  - If entry has content (`bytes`): overwrite the file with that content.
  - If entry has `None` (file was new): delete the file.
- Set `tier0_rolled_back` = count of findings that had been applied.
- Set `tier0_applied` = 0.
- Add the eval failure detail to `errors[]`.
- Set `status: done` (the improve node succeeded at its job; the rollback is the correct
  outcome, not a crash). Note: set `status: failed` only if the improve procedure itself
  crashed (recipe parse error, unhandled exception, etc.).

---

## 6. Run the Tier-1/Tier-2 back-half

Run the eval corpus **once** (shared with Step 5 Tier-0 keep/rollback) and capture the boolean
verdict. Then invoke the back-half module:

```sh
# From repo root:
python -m lib.improve <retro_artifact_path> \
    --evals-passed <true|false> \
    --proposals-dir <repo_root>/.cronos/improvement-tier1/
```

Or call from Python:

```python
from lib.improve import run_back_half
back = run_back_half(
    routed.tier1,
    routed.tier2,
    evals_passed=evals_passed,        # from Step 5 eval run
    repo_root=repo_root,
    proposals_dir=Path(repo_root) / ".cronos" / "improvement-tier1",
)
# back.tier1_pr_urls   — PR URLs or PROPOSED_PR.md paths (one per Tier-1 finding)
# back.tier1_findings  — finding ids routed to Tier-1
# back.tier2_escalated — finding ids recorded as Tier-2 escalations
# back.errors          — per-finding emission failures
```

**Tier-1 gate (REQ-002):** if `evals_passed` is False, `tier1_pr_urls` and
`tier1_findings` will be empty — no PRs are emitted on red evals.

**Tier-2 (REQ-004):** tier2 findings are recorded in `tier2_escalated` only. No file is
written, no branch is created, no PR is opened. This happens regardless of eval verdict.

---

## 7. Write the improve report and emit delivery_status

Write a short `improve-report.md` at the runtime-supplied output path:

```markdown
---
class: improvement
run_id: <from state.json>
---

# Improve Report

## Summary
<1-2 sentences: how many tier-0 findings considered, applied, rolled back;
how many tier-1 PRs emitted; how many tier-2 escalated; errors.>

## Applied
<list: finding id, target, recipe type, files written>
- None. (if zero applied)

## Rolled back
<list if any; eval failure detail>
- None. (if zero rolled back)

## Tier-1 PRs
<list: finding id, PR URL or PROPOSED_PR.md path>
- None. (if zero tier-1 findings or evals red)

## Tier-2 Escalated
<list: finding id, fix_type, target — for human follow-up>
- None. (if zero tier-2 findings)

## Errors
<list if any>
- None. (if no errors)

## Skipped
<count of non-tier-0 findings skipped (i.e. routed to tier1/tier2); not a list>
```

Then emit the structured return (merge Tier-0 counts with Tier-1/Tier-2 back-half results):

```delivery_status
{
  "status": "done",
  "produces": "improvement",
  "artifact_paths": ["<runtime-given improve-report path>"],
  "fields": {
    "tier0_applied": <int>,
    "tier0_rolled_back": <int>,
    "errors": ["<error strings if any>"],
    "tier1_pr_urls": ["<PR URL or PROPOSED_PR.md path per Tier-1 finding>"],
    "tier1_findings": ["<finding ids routed to Tier-1>"],
    "tier2_escalated": ["<finding ids escalated as Tier-2>"]
  },
  "open_questions": []
}
```

Set `status: failed` (not `done`) only if the improve procedure itself crashed — e.g. the retro
artifact was missing, a snapshot raised an OS error, or an unhandled exception occurred. A clean
rollback is `status: done` with `tier0_rolled_back > 0`.

---

## Exit-code contract (mirrors auto_improver.py reference implementation)

| Outcome | `tier0_applied` | `tier0_rolled_back` | `status` |
|---------|----------------|---------------------|----------|
| Applied, evals green | N > 0 | 0 | done |
| Applied, evals red → rollback | 0 | N | done |
| No tier-0 candidates (no-op) | 0 | 0 | done |
| Procedure crash / artifact missing | 0 | 0 | failed |

---

## Guardrails

- Read the retro artifact's `delivery_status` fence **once**. Do not re-read mid-apply.
- The improve report is your only write output besides the applied recipe files.
- Do not call any gate, trigger any downstream node, or emit a `next_consumer`.
- If `recipe.content` for a fixture is suspiciously large (> 50 KB), add it to `errors[]`
  and skip — do not write.
- For `threshold` targets: the bounded-range rule applies. Only numeric changes within a
  sensible range (e.g. loop `max` between 1 and 20, `usd_ceiling` between 1.0 and 500.0)
  are accepted. Reject changes that would set a value to 0 or a negative number.
