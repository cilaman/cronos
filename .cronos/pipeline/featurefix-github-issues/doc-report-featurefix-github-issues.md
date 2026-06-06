---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: featurefix-github-issues
phase: doc
status: done
confidence: 0.85
inputs_used:
  - .cronos/pipeline/featurefix-github-issues/review-report-featurefix-github-issues--attempt2.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i1.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i2.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i3.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i4.md
  - .cronos/pipeline/featurefix-github-issues/impl-report-featurefix-github-issues--i5.md
  - README.md
  - CLAUDE.md
  - TESTING.md
  - deploy/VPS_SETUP.md
outputs_produced:
  - .cronos/pipeline/featurefix-github-issues/doc-report-featurefix-github-issues.md
  - README.md
  - CLAUDE.md
  - deploy/VPS_SETUP.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: TESTING.md
    reason: "Test guide focuses on test execution mechanics (pytest/vitest commands, coverage settings, test-architect agent). GitHub mirror is a feature implementation detail not relevant to the test-running instructions."
metrics:
  tool_calls: 18
  files_read: 11
  memory_hits: 0
  docs_updated: 3
  docs_considered: 4
---

## Summary

S3 (GitHub issue mirror) ships with one-way sync from Cronos tasks to GitHub issues. Implementation created two new modules (`git_issues.py` for gh CLI wrappers, `feature_hooks.py` for mirror orchestration), added `set_issue_refs` method to storage, and rewired `api/features.py` to fire mirrors as background asyncio tasks (non-blocking). All four mutating endpoints (POST create, PATCH edit, PATCH state-change, POST process) now schedule the mirror. Lifespan startup wires `feature_hooks.configure_store(task_store)` for production persistence. Documentation updated in README (new "## GitHub issue mirror" section describing user-visible behavior and `gh auth login` prerequisite), CLAUDE.md (added git_issues.py module entry, updated feature_hooks.py and api/features.py descriptions, updated main.py lifespan note), and deploy/VPS_SETUP.md (new §3.1 GitHub CLI installation and authentication). TESTING.md intentionally not updated — test commands unchanged and GitHub mirror is implementation detail outside test-guide scope.

## Updated docs

| File | Change summary |
|------|----------------|
| README.md | Added "## GitHub issue mirror" section after Quick Start describing mirror behavior (create→issue, edit→gh issue edit, done→gh issue close), background execution, and `gh auth login` prerequisite. |
| CLAUDE.md | (1) Updated main.py entry: added "lifespan startup wires feature_hooks.configure_store(task_store)"; (2) Updated storage.py entry: added "includes `set_issue_refs` method for GitHub issue persistence"; (3) Updated api/features.py entry: clarified "single _fire_mirror funnel for non-blocking background GitHub mirror dispatch"; (4) Added git_issues.py entry: "GitHub issue API helpers — `gh_issue_upsert` and `gh_issue_close`; falls back to `.cronos/issues/{task_id}.md`"; (5) Updated feature_hooks.py entry: changed from "async no-op stubs" to full description of mirror implementation with fire-and-forget scheduling. |
| deploy/VPS_SETUP.md | Added §3.1 "GitHub CLI (optional, for issue mirroring)" with installation steps (`sudo apt-get install -y gh`) and authentication flow (`gh auth login`). Documented fallback behavior (local `.cronos/issues/{task_id}.md` when gh unavailable). Added GitHub CLI to Prerequisites section in §1. |

## Intentionally not updated

- **TESTING.md** — Test guide focuses on test execution mechanics (pytest/vitest commands, coverage settings, test-architect agent). GitHub mirror is a feature implementation detail not relevant to the test-running instructions. No changes to backend/frontend test invocations or coverage requirements.

## Assumptions

- User-visible changelog hook taken from review report "## Next consumer brief" section, verbatim.
- Workspace-relative paths in doc updates assume standard Cronos repo structure (backend/, frontend/, deploy/, etc. at root).
- GitHub CLI (gh) is optional for basic Cronos operation; documented as optional prerequisite in VPS_SETUP to avoid blocking non-GitHub-mirror users.
- `.cronos/issues/{task_id}.md` fallback is silent and automatic — users don't need to configure it, only understand it exists when gh is unavailable.

## Open questions

- None.

## Next consumer brief

The S3 feature (GitHub issue mirror) is fully documented. Users should be aware of:

1. **README.md** section "## GitHub issue mirror" explains the feature end-to-end — what happens when you create/edit/move a feature/fix task, and that it's non-blocking.

2. **CLAUDE.md** Key modules table now documents both `git_issues.py` (CLI helpers) and updated `feature_hooks.py` (mirror orchestration), and notes that `main.py` lifespan startup wires the hook storage persistence.

3. **deploy/VPS_SETUP.md** §3.1 covers GitHub CLI installation and authentication — this is the only required setup step for the live mirror path. The fallback (local `.cronos/issues/{task_id}.md`) requires no extra configuration.

4. No test documentation changes needed — test suite coverage is verified by the tester phase (Phase 6); the github mirror feature is implementation-transparent from a test-running perspective.

If a user deploys Cronos to a VPS and links a repo but forgets to run `gh auth login`, the mirror will silently fall back to writing local `.cronos/issues/{task_id}.md` files — this is documented in README and VPS_SETUP.
