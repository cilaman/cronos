---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-09T07:46:40Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-09-0746-implement-adding-feature-dialogue
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: 2026-06-09-0713-adding-feature-dialogue
space_id: cronos-development
state: archived
title: 'Implement: Adding feature dialogue'
type: goal
updated_at: '2026-06-16T09:30:16Z'
waiting_question: null
---

# Brief

Implement a proper feature/fix creation and editing dialogue for Cronos.

Currently clicking "+" on the features board focuses an inline text input (FeatureComposer in FeaturesBoard.tsx). This goal replaces that inline form with a proper modal dialog (like TaskForm.tsx), and aligns the feature detail view editing experience with the task/goal editing UX pattern.

## Scope

1. Create FeatureForm modal component (frontend/src/components/FeatureForm.tsx)
2. Update FeaturesBoard.tsx to open the modal instead of the inline composer
3. Update FeatureDetail.tsx to align with task UX (Start icon instead of Process button; type toggle in edit mode)
4. Write frontend tests for the new/changed components
5. Finalize and merge

## Acceptance Criteria

- Clicking "+" on the Backlog lane opens a proper modal dialog
- Modal allows setting title, type (feature/fix), priority, and brief  
- Modal dismiss works via Escape key and Cancel button
- FeatureDetail shows a Start/play icon for triggering decomposition (not a "Process" button)
- FeatureDetail edit mode includes a type toggle (feature/fix)
- Full test suite passes (60% coverage floor)

# History

```
2026-06-09T09:09:09Z [agent]
All tasks complete. Completed 5, skipped 0 already-done.
```
