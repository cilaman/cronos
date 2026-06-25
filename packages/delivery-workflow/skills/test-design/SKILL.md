---
name: test-design
description: Method for designing a test suite — TC-id assignment, test suite composition from design iterations[], coverage-gap identification, and tester delegation pattern. Loaded by the test-architect agent.
---

# test-design

How to design a test suite for a feature. The `test-architect` agent owns the role and the hard rules; this skill owns the method.

## 1. Memory-first preflight
Scan injected memory for existing test patterns, coverage floors, mocking conventions, and prior test debt. These are binding: a feature that violates the coverage floor must include enough TCs to close the gap.

## 2. Seed from design iterations
For each iteration in `iterations[]`:
- The `validation_command` is a test-case seed (verify it passes = TC-NNN).
- `scope_files[]` is the candidate set for unit tests.
- Create at least one TC per iteration; more for complex branching logic.

## 3. Seed from requirements
For each REQ-NNN and its acceptance criteria:
- Map each AC to one or more TCs.
- Record the mapping in a traceability table: `TC-NNN → REQ-NNN → AC-text`.
- At least one TC per REQ should be an integration or end-to-end test (not just a unit assertion).

## 4. Assign TC-ids
Sequential, zero-padded: TC-001, TC-002, .... Each TC record:
- `id`: TC-NNN
- `name`: short slug (snake_case)
- `type`: unit | integration | e2e
- `req_ids`: [REQ-NNN, ...]
- `iteration_ids`: [I1, ...] — which design iterations this TC covers
- `method`: what to assert (concrete, not "check that it works")

## 5. Coverage-gap identification
After mapping TCs to iterations and REQs:
- List any REQs with zero TCs → gap (must be filled or escalated).
- List any iterations where all TCs are unit-only → consider adding an integration TC.
- Flag edge cases not covered by any AC (e.g. empty input, auth boundary, large data set).

## 6. Tester delegation pattern
The `tester` agent receives this test-design artifact and executes the suite. In the artifact, write explicit run commands per TC where needed (e.g. `pytest tests/test_x.py::test_y -v`). The tester must be able to run each TC without re-reading the design.

## 7. Validation checklist
Before emitting:
- [ ] Every REQ-id maps to at least one TC.
- [ ] Every iteration in `iterations[]` has at least one TC seeded from its `validation_command`.
- [ ] `tc_ids[]` in delivery_status matches the full set of TC-NNN ids in the artifact.
- [ ] No TC requires the tester to read the analysis or design artifact to execute it.
