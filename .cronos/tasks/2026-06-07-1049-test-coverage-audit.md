---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-07T10:49:05Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1049-test-coverage-audit
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1049-features-fixes-deep-qa-review
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: Test Coverage Audit
type: task
updated_at: '2026-06-07T10:49:05Z'
waiting_question: null
---

# Brief

Audit the test coverage of the Features & Fixes backend implementation in Cronos.
Identify untested code paths and missing scenario coverage.

## Setup

```bash
cd /data/spaces/cronos-development/backend
pip install -e ".[dev]" -q
```

## Step 1: Run the feature-scoped tests with coverage

```bash
cd /data/spaces/cronos-development/backend
python -m pytest tests/ -k "feature" --cov=app --cov-report=term-missing   --override-ini="addopts=" -q 2>&1 | head -200
```

Note the overall coverage % and which lines are NOT covered (the "Miss" column).

## Step 2: Run full test suite coverage for feature modules

```bash
cd /data/spaces/cronos-development/backend
python -m pytest tests/ --cov=app/api/features --cov=app/feature_sync   --cov=app/feature_hooks --cov=app/feature_state   --cov-report=term-missing --override-ini="addopts=" -q 2>&1 | tail -60
```

## Step 3: Analyze missing lines

For each module with less than 85% coverage, read the source file and identify what scenario
is not tested. Cross-reference with the test files:

- `backend/tests/test_api/test_features_create.py`
- `backend/tests/test_api/test_features_board.py`
- `backend/tests/test_api/test_features_state_transition.py`
- `backend/tests/test_api/test_features_process.py`
- `backend/tests/test_api/test_features_realize.py`
- `backend/tests/test_api/test_features_read.py`
- `backend/tests/test_api/test_features_edit.py`
- `backend/tests/test_feature_sync.py`
- `backend/tests/test_feature_hooks.py`
- `backend/tests/test_feature_numbering.py`

## Step 4: Identify critical missing scenarios

Look specifically for tests covering:

A. Feature stuck in PROCESSING if decomposition fails (worker error path in _run_feature_decompose)
B. Feature with NO realizing items after decomposition (waiting_question fallback path)
C. Feature transition to WAITING via propagate_to_feature (if set_feature_waiting_question exists)
D. Race condition guard on _next_feature_key (concurrent feature creation)
E. GitHub mirror failure (gh CLI not available / no remote configured)
F. Space isolation: features in space A don't appear in space B's board
G. Delete endpoint (501 response)
H. Validate_realizes rejection cases (self-realize, wrong type, cross-space)

## Output format

Write your findings to `/data/spaces/cronos-development/.cronos/qa/features-test-audit.md`.
Create the directory if it doesn't exist (use Bash: `mkdir -p /data/spaces/cronos-development/.cronos/qa`).

Structure:

```markdown
# Features Test Coverage Audit

## Coverage Summary
| Module | Coverage % | Uncovered Lines |
|--------|-----------|-----------------|

## Critical Untested Scenarios
(scenarios where absence of tests hides real bugs)

## Missing Tests (P1)
...

## Missing Tests (P2)  
...

## Test Quality Notes
(are existing tests well-written? any false-positive tests?)
```

After writing the file, verify it exists with Bash.

## Acceptance

- Full-suite coverage run completed and module coverage %s reported
- Missing line ranges identified for each feature module below 90%
- All 8 scenarios (A–H) checked and documented
- Findings file written to `/data/spaces/cronos-development/.cronos/qa/features-test-audit.md`

Then run /task-finalize

# History
