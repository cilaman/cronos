---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T10:49:05Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1049-features-fixes-deep-qa-review
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages:
- Move this goal and all subtasks to done
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: Features & Fixes Deep QA Review
type: goal
updated_at: '2026-06-08T04:44:24Z'
waiting_question: null
---

# Brief

Deep-dive QA review of the Features & Fixes feature implementation in Cronos.

## Context

The Features & Fixes arc (root goal `2026-06-03-1631-features-and-fixes`) added a Kanban-style
feature tracking system with 5 state lanes (backlog, processing, planned, waiting, done), GitHub
issue mirroring, and automated goal decomposition. This review goal audits the current state of
that implementation.

## Scope

Backend: `backend/app/api/features.py`, `backend/app/storage.py` (feature methods),
`backend/app/feature_sync.py`, `backend/app/feature_hooks.py`, `backend/app/feature_state.py`,
`backend/app/models.py` (Feature* schemas), `backend/app/worker.py` (_run_feature_decompose).

Frontend: `frontend/src/pages/FeaturesPage.tsx`, `frontend/src/components/FeaturesBoard.tsx`,
`frontend/src/components/Board.tsx` (shared Backlog), `frontend/src/api.ts` (feature API calls),
`frontend/src/hooks/useFeatures.ts`, `frontend/src/types.ts` (FeatureState, FEATURE_LANES).

Tests: `backend/tests/test_api/test_features*.py`, `backend/tests/test_feature*.py`,
`frontend/src/components/__tests__/FeaturesBoard.test.tsx`.

## Child tasks

1. **Backend Features Audit** — audit storage, API, state machine, sync, and hooks for correctness, missing methods, and error handling gaps.
2. **Frontend UX & Wiring Audit** — audit frontend wiring, missing API calls, UX divergencies from existing Cronos patterns.
3. **Test Coverage Audit** — identify untested code paths and missing scenario coverage.
4. **Synthesize & Create Refactoring Goals** — read all audit reports, group findings into focused refactoring goals, and create them in the Cronos board via API.

# History
