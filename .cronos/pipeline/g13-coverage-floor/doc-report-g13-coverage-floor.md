---
cc_version: '1.0'
agent: pipeline-doc-sync
slug: g13-coverage-floor
phase: doc
status: done
confidence: 0.95
inputs_used:
  - .cronos/pipeline/g13-coverage-floor/impl-report-g13-coverage-floor--i1.md
  - .cronos/pipeline/g13-coverage-floor/review-report-g13-coverage-floor--attempt1.md
  - TESTING.md
  - CLAUDE.md
outputs_produced:
  - .cronos/pipeline/g13-coverage-floor/doc-report-g13-coverage-floor.md
  - TESTING.md
  - CLAUDE.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: README.md
    reason: "Dev commands section only mentions coverage test requirement without the specific 60% floor; references pyproject.toml as authoritative, so no update needed."
  - path: deploy/VPS_SETUP.md
    reason: "Deployment procedures unchanged; implementation affected only `backend/pyproject.toml` configuration."
metrics:
  tool_calls: 8
  files_read: 4
  memory_hits: 1
  docs_updated: 2
  docs_considered: 4
---

## Summary

The implementation raised the pytest coverage floor from 60% to 80% in `backend/pyproject.toml` line 39. Two documentation files referenced this value and required updating: `TESTING.md` (line 17) and `CLAUDE.md` (lines 17 and 133). All references are now aligned with the new floor. README.md and deployment docs did not require updates since they do not hardcode the coverage floor value.

## Updated docs

| File | Change summary |
|------|---|
| TESTING.md | Updated line 17: "60% coverage" → "80% coverage" and `--cov-fail-under=60` → `--cov-fail-under=80` |
| CLAUDE.md | Updated line 17 comment from "60% coverage floor" to "80% coverage floor" |
| CLAUDE.md | Updated line 133 from "Pytest suite (60% coverage floor)" to "Pytest suite (80% coverage floor)" |

## Intentionally not updated

- **README.md** — Dev commands section only mentions coverage test requirement without the specific floor value; references `pyproject.toml` as authoritative source.
- **deploy/VPS_SETUP.md** — Deployment procedures unchanged; implementation affected only `backend/pyproject.toml` configuration.

## Assumptions

- `backend/pyproject.toml` line 39 is the authoritative source of truth for the coverage floor value.
- Documentation that hardcodes or references the 60% floor is outdated and must be updated to 80%.
- The CI job (G02) reads `addopts` from `pyproject.toml` at runtime and enforces the new floor without requiring CI configuration changes.

## Open questions

None.

## Next consumer brief

G13 documentation sync is complete. The coverage floor has been raised from 60% to 80% in `backend/pyproject.toml` and all user-facing documentation (TESTING.md, CLAUDE.md) now reflects this change. The new floor provides ~6.84% headroom above the current 86.84% coverage baseline and is enforced by the test suite and CI pipeline.
