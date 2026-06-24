# Gate test fixtures

Artifact fixtures used by `tests/test_pipeline_gate.py` to exercise the
`runGate` engine and all check types.

| File | Purpose |
|------|---------|
| `analysis-report-good.md` | Valid analysis-class artifact (passes schema, has non-empty ACs, traceability R1+R2) |
| `analysis-report-bad-missing-ac.md` | Analysis artifact where one traceability entry has empty `acceptance_criteria` |
| `analysis-report-bad-placeholder-ac.md` | Analysis artifact where one AC is a placeholder string ("TBD") |
| `impl-report-good.md` | Valid impl-class artifact with `validation_command: "echo success"` (exits 0) |
| `impl-report-lying.md` | Impl artifact with `validation_command_passed: true` but `validation_command: "exit 1"` (exits non-zero) |
| `review-report-pass.md` | Review artifact with `verdict: pass`, no blocking findings |
| `review-report-needs-fix.md` | Review artifact with `verdict: needs_fix`, one blocking finding |
| `review-report-fail.md` | Review artifact with `verdict: fail`, one blocking finding |

The `schema` check calls `verify.verify(agent_class, slug, space)` which
expects the artifact at `{space}/.cronos/pipeline/{slug}/{prefix}-{slug}.md`.
Tests that exercise the schema check copy the fixture content to this
canonical path within `tmp_path`.
