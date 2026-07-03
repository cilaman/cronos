---
name: analysis
description: Method for decomposing a feature brief into testable requirements — memory preflight, scout-report loading, requirement decomposition, has_ui determination, REQ-id assignment, traceability table construction. Loaded by the analyst agent.
---

# analysis

How to decompose a feature into requirements. The `analyst` agent owns the role and the hard rules; this skill owns the method.

## 1. Memory-first preflight
Scan injected memory before reading any file. Treat relevant entries (naming conventions, prior design decisions, known constraints, scope rules) as **binding constraints**: a feature that conflicts with one is a blocker, not a new requirement.

## 2. Load the scout report
Read the scout-report artifact. Extract:
- Existing implementation state (files, modules, APIs already present).
- Known gaps or blockers the scout flagged.
- Open questions the scout deferred.

Treat scout findings as ground truth for what is already implemented. Do not derive requirements for things the scout found already done.

## 3. Decompose into requirements
For each distinct behaviour, constraint, or interface the feature needs:
1. Write a one-sentence requirement statement.
2. Assign `REQ-NNN` (zero-padded, sequential; never reuse a retired id).
3. List 1–3 acceptance criteria (testable assertions, not sub-tasks).
4. Mark a `verifying_phase` (test | review | doc) — where this req is validated.
5. Assign a confidence (0.0–1.0) reflecting your certainty the req is correctly understood.

Keep requirements at the *what*, not the *how*. Implementation detail belongs in design.

## 4. Determine has_ui
`has_ui = true` iff the feature requires any of:
- A new or modified page, route, or component visible to the user.
- Changes to existing UI behaviour (layout, interaction, data display).
- New API endpoints consumed only by the frontend.

`has_ui = false` for backend-only, CLI, infra, or doc-only changes.

This field drives routing: `analyze.fields.has_ui == true` gates the `frontend-designer` node.

## 5. Build the traceability table
Produce a table mapping REQ-ids → acceptance criteria → verifying phase. This is the anchor the architect and reviewer use for traceability checks.

## 6. Validation checklist
Before emitting:
- [ ] Every requirement has a REQ-id, 1–3 ACs, a verifying_phase, and a confidence.
- [ ] `has_ui` is a boolean (not a string, not null).
- [ ] No requirement was invented to compensate for a vague brief — open questions are surfaced instead.
- [ ] `req_ids[]` in delivery_status matches the full set of REQ-ids in the artifact.

## 7. Escalation table
| Signal | Action |
|--------|--------|
| Brief too vague to decompose | Surface as open_questions; do not guess |
| Scout report missing or empty | Request re-run of scout; block analysis |
| Conflicting scope signals | Name the conflict; ask for scope decision |
