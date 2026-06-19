---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-05T23:35:07Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-05-2335-auto-repair-missing-sibling-deps-in-run
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: auto-repair missing sibling deps in _run_goal
type: goal
updated_at: '2026-06-05T23:35:07Z'
waiting_question: null
---

# Brief

# Fix: auto-repair missing sibling deps in multi-subgoal goals

## Problem

When pipeline subgoals are created, their `depends_on` is sometimes left empty
while internal tasks carry cross-subgoal deps (e.g. scout of SG-B depends on
doc of SG-A). `_topo_children` only uses **sibling** `depends_on` for ordering;
non-sibling deps are invisible to it. With `manual_order=0` on all subgoals,
they sort alphabetically — often executing in the wrong order (SG-B before SG-A).

When the worker tries to activate SG-B and finds the dep unmet, it fails the
**entire parent goal** into waiting state. The user then has to manually patch
deps and re-enqueue. This has happened on `features-and-fixes` (2026-06-04) and
`harness-editor-usability` (2026-06-05).

## Fix

In `backend/app/worker.py` `_run_goal`: when `InvalidTransition("unmet
dependencies: X")` is raised and `X` is a **non-sibling** dep (X's parent !=
the current goal), automatically add X's parent goal as a sibling dep on the
child, re-order, and resume — instead of failing the whole goal.

## Child tasks (sequential)
1. Implement auto-repair in `_run_goal`
2. Tests

# History
