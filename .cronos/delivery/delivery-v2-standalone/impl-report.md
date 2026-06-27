---
class: implementation
agent: implementor
goal_slug: delivery-v2-standalone
phase: implementation
status: done
base_branch: feature/delivery-v2
iterations_completed: [I1, I2, I3, I4]
validation_command_passed: true
files_changed:
  - packages/delivery-workflow/lib/security.py
  - packages/delivery-workflow/tests/test_security_lib.py
  - packages/delivery-workflow/lib/evals/__init__.py
  - packages/delivery-workflow/lib/evals/corpus.py
  - packages/delivery-workflow/lib/evals/__main__.py
  - packages/delivery-workflow/tests/test_evals_lib.py
  - backend/app/pipeline/gate.py
  - backend/tests/test_pipeline_gate_security.py
  - packages/delivery-workflow/skills/improve/SKILL.md
---

# Implementation Report — F1+F2 standalone parity (delivery/v2 Phase D)

## Summary

All 4 iterations executed in order (I1→I2, I3→I4 as two independent chains).
Each iteration committed with `impl-sgd-I{n}:` prefix on `feature/delivery-v2`.

## Iterations

### I1 — Portable security evaluator (`lib/security.py`) ✅

Created `packages/delivery-workflow/lib/security.py` containing:
- `_run_security_cmd()`: captures **full** stdout (DD-002 fix — no 2 KB tail truncation)
- `_split_frontmatter()`: portable YAML frontmatter splitter (mirrors `verify.split_frontmatter` without `app.*` import)
- `_read_security_header()`: reads and parses security agent artifact headers
- `evaluate_security(check, artifact_paths, space) -> (decision, errors, evidence)`: verbatim port of `gate.py:572-744` decision logic

Tests in `tests/test_security_lib.py`: 11 tests covering scanner hit, missing scanner policy, infra crash, agent verdict precedence, and DD-002 regression (>2 KB JSON must not score clean).

Validation: `cd packages/delivery-workflow && python -m pytest tests/test_security_lib.py tests/test_import_boundary.py -q` → **11 passed**.

Commit: `a429838`

### I2 — Re-point Cronos gate to portable evaluator ✅

In `backend/app/pipeline/gate.py`:
- Added `from lib.security import evaluate_security as _evaluate_security`
- Replaced 172-line `_check_security` body with a 3-line delegate: `return _evaluate_security(check, artifact_paths, space)`
- Added DD-002 regression test to `backend/tests/test_pipeline_gate_security.py`

Validation: `cd backend && python -m pytest tests/test_pipeline_gate_security.py -q --override-ini="addopts="` → **10 passed** (narrow run; `--override-ini` bypasses 80% floor for module-scoped run per project convention).

Commit: `460f791`

### I3 — Portable eval-corpus harness (`lib/evals/`) ✅

Created `packages/delivery-workflow/lib/evals/` package:
- `corpus.py`: `EvalResult` dataclass + `run_eval_corpus(repo_root, *, eval_cmd, env, runner)` with arg→env→default precedence
- `__init__.py`: exports `run_eval_corpus`, `EvalResult`
- `__main__.py`: CLI with `--repo-root` and `--json` flags, exits with corpus exit code

Tests in `tests/test_evals_lib.py`: 16 tests covering command precedence, passed flag, exit code propagation, repo_root wiring, output_tail, and CLI smoke tests.

Validation: `cd packages/delivery-workflow && python -m pytest tests/test_evals_lib.py tests/test_import_boundary.py -q` → **16 passed**.

Commit: `208db30`

### I4 — Wire `improve` flow onto `lib.evals` ✅

Edited `packages/delivery-workflow/skills/improve/SKILL.md`:
- Step 5: replaced inlined `DELIVERY_EVAL_CMD="${DELIVERY_EVAL_CMD:-pytest …}"` block with `python -m lib.evals` / `run_eval_corpus()` invocation; noted that default+override now live in `lib.evals`
- Step 6: clarified that `evals_passed` comes from the Step 5 result (no re-run)
- No `DELIVERY_EVAL_CMD:-pytest` pattern remains in the SKILL

Validation: `cd packages/delivery-workflow && grep -q 'lib.evals' skills/improve/SKILL.md && ! grep -q 'DELIVERY_EVAL_CMD:-pytest' skills/improve/SKILL.md && python -m pytest tests/ -q` → **347 passed**.

Commit: `ad549dc`

## Acceptance Criteria

- [x] `_check_security` body extracted to `packages/delivery-workflow/lib/security.py` — shared by Cronos gate and standalone runner
- [x] Portable eval harness: `packages/delivery-workflow/lib/evals/` — F2 Tier-0/1 runnable standalone via `python -m lib.evals`
- [x] Import-boundary test still green — no `app.*` imports added to portable core

## Open Questions Resolved

- R1 (wrong base branch): Workspace was already on `feature/delivery-v2` — no rebase needed.
- R6 (no analysis-report): REQ set derived from spec §5 Phase D + goal ACs as noted in design report.

```delivery_status
{
  "status": "done",
  "produces": "implementation",
  "artifact_paths": [".cronos/delivery/delivery-v2-standalone/impl-report.md"],
  "fields": {
    "iterations_completed": ["I1", "I2", "I3", "I4"],
    "validation_command_passed": true
  },
  "open_questions": []
}
```
