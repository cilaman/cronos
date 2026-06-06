---
cc_version: "1.0"
agent: pipeline-reviewer
slug: showing-commit--attempt1
phase: review
status: done
confidence: 0.85
inputs_used:
  - memory:project_pipeline_reviewer_agent
  - memory:project_branding
  - .cronos/pipeline/showing-commit/design-report-showing-commit.md
  - .cronos/pipeline/showing-commit/analysis-report-showing-commit.md
  - .cronos/pipeline/showing-commit/impl-report-showing-commit--i1.md
  - .cronos/pipeline/showing-commit/impl-report-showing-commit--i2.md
  - .cronos/pipeline/showing-commit/impl-report-showing-commit--i3.md
  - .cronos/pipeline/showing-commit/impl-report-showing-commit--i4.md
  - .cronos/pipeline/showing-commit/test-report-showing-commit.md
  - deploy/upgrade.sh
  - deploy/VPS_SETUP.md
  - backend/Dockerfile
  - backend/app/main.py
  - backend/tests/test_info_endpoint.py
  - backend/app/pipeline/schemas/review.schema.yaml
  - backend/app/pipeline/verify.py
  - frontend/Dockerfile
  - frontend/src/api.ts
  - frontend/src/types.ts
  - frontend/src/hooks/useBuildInfo.ts
  - frontend/src/components/BuildInfo.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/__tests__/BuildInfo.test.tsx
  - docker-compose.yml
  - docker-compose.prod.yml
outputs_produced:
  - .cronos/pipeline/showing-commit/review-report-showing-commit--attempt1.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 52
  files_read: 23
  memory_hits: 2
  diff_lines_reviewed: 422
verdict: pass
attempt: 1
findings:
  - id: F1
    severity: high
    file: frontend/src/components/Sidebar.tsx:205
    evidence: "Sidebar header (lines 104-113) holds the CRONOS brand mark; BuildInfo is mounted at line 207 inside the bottom footer next to ThemePicker (`<ThemePicker /> <BuildInfo />`), not next to CRONOS in the top-left corner."
    blocking: false
    suggested_action: "Operator override 2026-06-01: footer placement next to ThemePicker is accepted; the user explicitly confirmed `\"I am OK with F1 - showing it in footer instead of header\"`. Demoted from blocking to non-blocking; positional acceptance criterion is waived for this goal."
  - id: F2
    severity: low
    file: frontend/src/components/BuildInfo.tsx:36
    evidence: "`showTwoTimestamps = timesAreDiverged(backendTime, frontendTime)` shows both timestamps only when divergence > 5 min; in the happy path (single upgrade.sh run) only one labeled `Built ...` line is rendered, even though the user request says `Surface upgrade/build timestamps for both the frontend (GUI) and backend`."
    blocking: false
    suggested_action: "Either (a) always render both labeled lines (API: ..., UI: ...) regardless of divergence, or (b) document the design choice in the BuildInfo docstring/comment so the next reviewer understands the merged-when-equal rule is intentional. Current behaviour is defensible but not literal to the acceptance wording."
  - id: F3
    severity: low
    file: frontend/src/components/__tests__/BuildInfo.test.tsx
    evidence: "Implementor I4 self-flagged: `Line 56 of BuildInfo.tsx has a branch not covered by tests (the shortSha && repoUrl check when SHA is set but repoUrl is null — a SHA-only display without link)`. No Test 6 covers the plain `<span>{shortSha}</span>` branch."
    blocking: false
    suggested_action: "Add a sixth test case mocking `{ commit_sha: 'abc1234', build_time: null, repo_url: null }` and assert `queryByRole('link')` is null while `screen.getByText('abc1234')` is present, exercising the SHA-only-no-link branch."
  - id: F4
    severity: medium
    file: backend/pyproject.toml:37
    evidence: "Both I3 (`pytest tests/test_info_endpoint.py -v`) and I4 (`npm test -- ... --run`) validation commands as written in the design report exit 1 against the project-wide coverage floors (pyproject `--cov-fail-under=60`; vitest `lines:27`). Implementors had to bypass with `--no-cov` / `npx vitest run` to get exit 0."
    blocking: false
    suggested_action: "Either update the design's per-iteration validation_command strings to include `--no-cov` (backend) and direct `npx vitest run` (frontend), or add per-test-file coverage exclusions, so future per-iteration gates pass cleanly without the implementor having to invent a workaround. Carry into the next design refresh."
---

## Summary

The four-iteration DAG (infra to infra to backend to frontend) delivers a baked-in commit SHA, build timestamp, and repo URL through `upgrade.sh` -> `--build-arg` -> Dockerfile ARG/ENV -> `os.environ.get` in `/api/info` -> React Query `useBuildInfo` hook -> `BuildInfo` component. Scope conformance is clean: every `files_changed` entry across all four impl reports is a subset of its iteration's `scope_files`, no escapes, no edits to security-sensitive paths. Test report says 1934p / 0f / 0e at 82.54% coverage; gate decision `pass`. Three of four user acceptance criteria are met as written (build-time bake, GitHub-comparable short SHA, upgrade.sh + docker build wiring). The fourth — `<BuildInfo />` placement in the top-left corner next to "CRONOS" — was initially flagged: the implementation renders BuildInfo in the bottom-right footer next to `<ThemePicker />`. On 2026-06-01 the operator explicitly accepted the footer placement (`"I am OK with F1 - showing it in footer instead of header"`), so F1 is demoted to non-blocking. With no blocking findings remaining, verdict is `pass`.

## Findings

- F1 (high, non-blocking — operator override 2026-06-01) — `frontend/src/components/Sidebar.tsx:205` — BuildInfo renders in bottom-right footer next to ThemePicker, not next to the CRONOS brand mark in the top-left header. Originally flagged as a literal-acceptance miss ("next to the CRONOS text in the top-left corner"), but the user explicitly accepted the footer placement: `"I am OK with F1 - showing it in footer instead of header"`. Demoted to non-blocking; no implementor action required.
- F2 (low, non-blocking) — `frontend/src/components/BuildInfo.tsx:36` — Backend and frontend timestamps are folded into a single `Built ...` line when within 5 min; the user wording "Surface upgrade/build timestamps for both" reads literally as always-show-both. Defensible interpretation but worth either changing or documenting.
- F3 (low, non-blocking) — `frontend/src/components/__tests__/BuildInfo.test.tsx` — Self-flagged in I4: the SHA-set / repo-url-null branch in BuildInfo.tsx is not exercised by any of the five tests. Add a sixth case.
- F4 (medium, non-blocking) — `backend/pyproject.toml:37` — Per-iteration validation commands in the design fail against project-wide coverage floors; implementors had to manually bypass with `--no-cov` to get exit 0. Update design's validation_command strings or add per-file coverage exclusions.

## Verdict

pass

Originally `needs_fix` on F1 alone (footer vs. top-left header placement of `<BuildInfo />`). On 2026-06-01 the operator explicitly accepted the deviation: `"I am OK with F1 - showing it in footer instead of header"`. F1 was demoted to `blocking: false`; no other findings were blocking. With R-rev-4 satisfied (no blocking findings remain), verdict is `pass`. F2-F4 are recorded as non-blocking follow-ups; they can be picked up by a future task at the operator's discretion but do not gate this goal.

## Assumptions

- The user request `"next to the CRONOS text in the top-left corner"` is the binding acceptance, not the analyst's looser R5 wording `"adjacent to or below the CRONOS text"`. The reviewer audits implementations against the user contract first; design/analyst relaxations do not absolve a positional miss.
- Scope contract is the union of `iterations[].scope_files[]` from the design report. The pre-existing unstaged modifications to `backend/app/pipeline/state_writer.py`, `backend/tests/test_pipeline_state_writer.py`, `.claude/skills/goal-finalize/SKILL.md`, etc. originate from prior pipeline-foundation tasks (commits 519d778..f6034bc) and are not part of the `showing-commit` goal — they were ignored.
- Test report's `tool_calls: 9` and `inputs_used: []` are the known tester-adapter quirk (gate runner, not authoring). Gate decision `pass` is treated as authoritative.
- The review-class schema (`review.schema.yaml`) at `additionalProperties: false` rejects `coverage_summary` and `prior_review_slug`; both are omitted from this header despite being mentioned in the task prompt. Coverage information is conveyed in the prose `## Summary` instead.

## Open questions

- None.

## Next consumer brief

pipeline-doc-sync (Phase 7, terminal):
- Verdict is `pass`; no implementor re-run required. Proceed to doc-sync against the union of `files_changed` from impl-report-showing-commit--i1..i4.md.
- Files touched across the goal (consult each impl report for exact lists): `upgrade.sh`, `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml`, `backend/app/main.py` (`/api/info` endpoint), `backend/tests/test_info_endpoint.py`, `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/hooks/useBuildInfo.ts`, `frontend/src/components/BuildInfo.tsx`, `frontend/src/components/Sidebar.tsx`, `frontend/src/components/__tests__/BuildInfo.test.tsx`.
- Non-blocking follow-ups F2-F4 are not gating but should be linked in the doc-report's `intentionally_not_updated[]` or open-questions section so they can be picked up later: (F2) always-show-both timestamps wording, (F3) sixth BuildInfo test for SHA-only-no-link branch, (F4) design's per-iteration validation_command vs. project coverage floor.
- F1 (footer placement of BuildInfo) is accepted as-is per operator override; no doc disclaimer is required.
