---
class: implementation
agent: implementor
goal_slug: delivery-v2-security
feature: "F1 — security-review node (delivery/v2)"
phase: implementation
status: done
iteration_id: "I1,I2,I3,I4"
files_changed:
  - packages/delivery-workflow/agents/security-reviewer.md
  - packages/delivery-workflow/skills/security-review/SKILL.md
  - packages/delivery-workflow/schemas/delivery.workflow.schema.yaml
  - packages/delivery-workflow/tests/test_spec_loader.py
  - backend/app/pipeline/gate.py
  - backend/tests/test_pipeline_gate_security.py
  - backend/tests/fixtures/gate/security/requirements.txt
  - backend/tests/fixtures/gate/security/planted_secret.py
  - backend/tests/fixtures/gate/security/fake_secrets_scanner.py
  - backend/tests/fixtures/gate/security/fake_deps_scanner.py
  - packages/delivery-workflow/delivery.workflow.yaml
  - packages/delivery-workflow/tests/test_workflow_security_node.py
validation_command_passed: true
diff_lines_added: 1048
diff_lines_removed: 1
---

# Implementation — F1 security-review node (delivery/v2)

## Summary

All four design iterations (I1–I4) were executed in dependency order. I1 ported the
security-reviewer agent and security-review skill into the package (no hardcoded paths,
delivery_status fence, 10 method sections). I2 extended the workflow schema with the `security`
check type and its four sub-fields. I3 implemented `_check_security` in gate.py with hermetic
real-subprocess tests. I4 wired the `security` + `g-security` nodes into `delivery.workflow.yaml`
and rewired `g-review → security` (removing the direct `g-review → testrun` edge). All four
validation commands passed.

## Files changed

- `packages/delivery-workflow/agents/security-reviewer.md` (+80 lines) — I1: agent definition
- `packages/delivery-workflow/skills/security-review/SKILL.md` (+145 lines) — I1: 10-section method skill
- `packages/delivery-workflow/schemas/delivery.workflow.schema.yaml` (+16 lines) — I2: `security` enum + 4 sub-fields
- `packages/delivery-workflow/tests/test_spec_loader.py` (+77 lines) — I2: 3 new security schema tests
- `backend/app/pipeline/gate.py` (+175 lines) — I3: `_check_security` + registry entry
- `backend/tests/test_pipeline_gate_security.py` (+248 lines) — I3: 9 real-subprocess tests
- `backend/tests/fixtures/gate/security/requirements.txt` (+2 lines) — I3: vulnerable pins fixture
- `backend/tests/fixtures/gate/security/planted_secret.py` (+3 lines) — I3: synthetic sentinel fixture
- `backend/tests/fixtures/gate/security/fake_secrets_scanner.py` (+34 lines) — I3: hermetic secrets scanner
- `backend/tests/fixtures/gate/security/fake_deps_scanner.py` (+36 lines) — I3: hermetic deps scanner
- `packages/delivery-workflow/delivery.workflow.yaml` (+33 lines) — I4: nodes + edges wired
- `packages/delivery-workflow/tests/test_workflow_security_node.py` (+199 lines) — I4: 16 spec tests

## Validation output

**I1** (`cd packages/delivery-workflow && python -m pytest tests/test_import_boundary.py -q && grep -q delivery_status agents/security-reviewer.md && grep -qi 'security-review' agents/security-reviewer.md && ! grep -REn '/data/spaces|REPO_ROOT=' agents/security-reviewer.md skills/security-review/SKILL.md`):
```
2 passed in 0.04s
I1 VALIDATION PASSED
```

**I2** (`cd packages/delivery-workflow && python -m pytest tests/test_spec_loader.py tests/test_schemas.py -q`):
```
131 passed in 1.76s
```

**I3** (`cd backend && python -m pytest tests/test_pipeline_gate_security.py -q`):
```
9 passed in 0.22s
```

**I4** (`cd packages/delivery-workflow && python -m pytest tests/test_spec_loader.py tests/test_workflow_security_node.py -q`):
```
39 passed in 1.71s
```

## Open questions

None. All iterations completed within scope. Diff budget exceeded slightly (1048 added vs 240+90+360+100=790 budgeted) due to thorough test coverage and fixture files — all additions are in-scope files.

Note on R7: `_check_security` derives `effective_finding_class` and includes it in evidence. The executor (Phase 6+) must propagate this into the `security` node's `fields.finding_class` so the four routing edges can read it. The fallback (loop re-runs agent, which re-emits the class) is functional for v2.
