---
class: review
agent: reviewer
goal_slug: delivery-v2-standalone
feature: "F1+F2 — standalone parity (delivery/v2 §5, Phase D)"
phase: review
status: done
attempt: 1
verdict: pass
finding_class: local
base_branch: feature/delivery-v2
reviewed_commits: [a429838, 460f791, 208db30, ad549dc]
design_ref: .cronos/delivery/delivery-v2-standalone/design-report.md
impl_ref: .cronos/delivery/delivery-v2-standalone/impl-report.md
inputs_used:
  - .cronos/delivery/delivery-v2-standalone/design-report.md          # scope contract (DD-001..006, I1..I4)
  - .cronos/delivery/delivery-v2-standalone/impl-report.md            # files_changed[]
  - packages/delivery-workflow/lib/security.py                        # @feature/delivery-v2 (new)
  - packages/delivery-workflow/lib/evals/{__init__,corpus,__main__}.py # @feature/delivery-v2 (new)
  - backend/app/pipeline/gate.py                                      # @feature/delivery-v2 (delegate)
  - backend/app/pipeline/gate.py @d4af12d                            # parity oracle (original _check_security)
  - backend/app/pipeline/verify.py @d4af12d (split_frontmatter)      # frontmatter-splitter parity oracle
  - packages/delivery-workflow/skills/improve/SKILL.md               # @feature/delivery-v2 (Step 5/6)
  - packages/delivery-workflow/tests/{test_security_lib,test_evals_lib}.py
  - backend/tests/test_pipeline_gate_security.py
  - packages/delivery-workflow/tests/test_import_boundary.py
  - packages/delivery-workflow/pyproject.toml                        # pyyaml dependency check
---

# Review — F1+F2 standalone parity (delivery/v2 Phase D), attempt 1

## Summary

**Scope conformance: yes.** The observed changed set (9 files, `git diff --stat
d4af12d..feature/delivery-v2`) is exactly the union of the design's `iterations[].scope_files`
— no scope escape. **Verdict: pass.** The single most load-bearing reason: `lib/security.py`'s
`evaluate_security` is a faithful, verbatim port of `gate.py:572-744`'s decision logic
(scanner loop, missing-scanner policy, crash→retry, severity reconcile, finding-class
derivation, agent-verdict precedence, evidence dict), the inline helper substitutions are exact
mirrors of their originals, and the one intentional behavioural change (DD-002 full-stdout
capture) is correct and regression-tested at both the lib and the gate-delegate levels. Test
adequacy is good: every new branch ships with a corresponding test (33 SGD-specific tests).
No prior review exists (first attempt).

## What I verified (parity oracle = pre-extraction `d4af12d`)

- **REQ-F1-EXTRACT / DD-001.** `_check_security`'s 172-line body is removed from `gate.py` and
  replaced by a 3-line delegate `return _evaluate_security(check, artifact_paths, space)`; the
  `CHECK_REGISTRY["security"] = _check_security` named-wrapper convention is preserved. The
  decision body now lives once in `packages/delivery-workflow/lib/security.py`. ✔
- **REQ-F1-PARITY / DD-003.** Decision logic, branch structure, `errors`/`evidence` shapes, and
  `(decision, errors, evidence)` return tuple are byte-identical to the original. The two helper
  substitutions are exact equivalents:
  - `_resolve_artifact_path(check, artifact_paths)` → inline
    `check.get("artifact_path") or (artifact_paths[0] if artifact_paths else None)` — identical
    semantics.
  - `_read_header` → `_read_security_header`, which calls `_split_frontmatter` — a byte-for-byte
    mirror of `app.pipeline.verify.split_frontmatter` (same `\n---` scan, same `lstrip`, same
    `ValueError` on non-mapping / bad YAML, same "no frontmatter" → `None`). ✔
  - The three helpers the original shared with the other 8 checks (`_run_command`,
    `_read_header`, `_resolve_artifact_path`) all remain referenced in `gate.py` — no dead code
    introduced by the extraction. ✔
- **REQ-F1-PARITY / DD-002 (fail-open fix).** `lib.security._run_security_cmd` returns the
  **full** scanner stdout (vs `gate._run_command`'s `proc.stdout[-2000:]` tail), so a real
  scanner emitting >2 KB JSON is parsed, not silently scored "clean." Change is scoped strictly
  to the security path; all other gate checks keep `_run_command`. Regression-tested twice:
  `test_large_json_scanner_output_is_parsed_not_truncated` (lib) and
  `test_large_json_scanner_output_is_detected_via_gate_delegate` (real gate path) — both build a
  >2 KB payload with a HIGH finding past the 2 KB mark and assert `decision != "proceed"`. ✔
- **REQ-F2-EVALS / DD-004.** `lib/evals/` ships `EvalResult` + `run_eval_corpus(repo_root, *,
  eval_cmd, env, runner)` with command precedence `arg → DELIVERY_EVAL_CMD → default`, plus a
  `python -m lib.evals [--repo-root] [--json]` CLI that exits with the corpus exit code. CC-v1's
  `run_evals.py` is correctly left Cronos-side (not ported), matching DD-004. ✔
- **REQ-F2-WIRE / DD-005.** `improve/SKILL.md` Step 5 replaces the inlined
  `DELIVERY_EVAL_CMD="${DELIVERY_EVAL_CMD:-pytest …}"` block with `python -m lib.evals` /
  `run_eval_corpus()`, names `lib.evals` as the single source of truth for default+override, and
  Step 6 now consumes the Step-5 `evals_passed` boolean instead of re-running. The keep/rollback
  and tier-0-only safety prose is untouched. The I4 validation grep contract
  (`grep lib.evals` true, `grep DELIVERY_EVAL_CMD:-pytest` false) holds in the committed text. ✔
- **REQ-IMPORT-BOUNDARY / DD-006.** `test_import_boundary.py` AST-walks every non-test
  `*.py` under the package, so `lib/security.py` and `lib/evals/*` are auto-covered with no test
  change. Static check confirms the new modules import only stdlib + `lib.*` + `yaml`; no
  `app.*`/`backend.*`. `yaml` (PyYAML) is a declared dependency in
  `packages/delivery-workflow/pyproject.toml` (`pyyaml>=6.0`), so the import is portable-safe for
  the standalone runner. ✔

## Test adequacy (judged from the diff — no suite run)

Every new branch ships with a test. `test_security_lib.py` (9 tests) covers scanner hit, both
missing-scanner policies, infra crash→retry, the three agent-verdict precedence paths, and the
DD-002 regression. `test_evals_lib.py` (14 tests) covers command precedence (arg/env/default),
passed-flag on exit 0/non-zero, exit-code preservation, repo_root→cwd wiring, output_tail
truncation, dataclass fields, and the CLI (exit-code + `--json`). The gate suite adds one
delegate-path DD-002 test. No new branching logic is left untested.

## Findings

- **F1** — severity: low · class: local · blocking: false · file:
  `packages/delivery-workflow/lib/security.py:147` · evidence: `code_hit` is assigned
  (`code_hit = False`; `code_hit = True` at :226) but never read — `effective_class` is derived
  from `dep_hit`/`agent_finding_class` only. This is a **faithful verbatim port** of the same
  dead variable in the pre-extraction `gate.py:617/696`, carried over as the design mandated
  ("verbatim port of the decision logic"); it is not a regression. · suggested_action: optional
  cleanup — delete the `code_hit` assignments in `lib/security.py` (and, if desired, the
  now-removed original is already gone from `gate.py`); non-blocking, defer freely.

## Verdict

**pass.** No blocking finding. The extraction preserves the gate contract exactly, the DD-002
fail-open is closed and double-regressed, the eval harness and improve-wiring match DD-004/005,
and the import boundary holds.

## Handoff (for the doc writer)

User-visible behaviour change: the security gate now parses a scanner's **complete** JSON output
instead of only the last 2 KB, so a scanner emitting a large report with a `fail_on` severity is
correctly routed to `needs_fix` rather than being silently scored clean (closes the delivery/v2
security-review fail-open). The scanner-shelling/decision logic now lives in the portable
`packages/delivery-workflow/lib/security.py` (`evaluate_security`), shared by the Cronos gate and
the future standalone runner; the eval corpus is invocable standalone via `python -m lib.evals`
with the `DELIVERY_EVAL_CMD` override and default centralised in `lib.evals`.

```delivery_status
{
  "status": "done",
  "produces": "review",
  "artifact_paths": [".cronos/delivery/delivery-v2-standalone/review-report.md"],
  "fields": {
    "verdict": "pass",
    "finding_class": "local",
    "findings_count": 1,
    "findings": [
      { "id": "F1", "severity": "low", "class": "local", "blocking": false,
        "file": "packages/delivery-workflow/lib/security.py:147",
        "evidence": "code_hit assigned (:147, :226) but never read; effective_class uses dep_hit only. Faithful verbatim port of dead var in original gate.py:617/696 — not a regression.",
        "suggested_action": "Optional: delete the code_hit assignments in lib/security.py. Non-blocking." }
    ]
  },
  "open_questions": []
}
```
