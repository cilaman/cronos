---
cc_version: "1.0"
agent: pipeline-reviewer
slug: g06-plugin-install-guard--attempt1
phase: review
status: done
confidence: 0.85
inputs_used:
  - memory:project-remediation-board-setup
  - memory:project-plugin-frontend-i1-impl
  - .cronos/pipeline/g06-plugin-install-guard/design-report-g06-plugin-install-guard.md
  - .cronos/pipeline/g06-plugin-install-guard/impl-report-g06-plugin-install-guard.md
  - .cronos/pipeline/g06-plugin-install-guard/test-report-g06-plugin-install-guard.md
  - .claude/settings.json
  - backend/app/tools/plugins.py
  - frontend/src/components/PluginsPanel.tsx
  - docs/security/plugin-trust-boundary.md
  - backend/tests/test_settings_deny_guard.py
  - backend/tests/test_plugin_guard_integration.py
  - backend/tests/test_plugins_allowlist.py
outputs_produced:
  - .cronos/pipeline/g06-plugin-install-guard/review-report-g06-plugin-install-guard--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 16
  files_read: 10
  memory_hits: 2
  diff_lines_reviewed: 600
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: high
    file: docs/security/plugin-trust-boundary.md
    evidence: "Doc §3 states: 'Default: https://claude.ai/marketplace (official Anthropic marketplace). Set TRUSTED_MARKETPLACE_SOURCES= (empty) to disable restriction'. But plugins.py _get_trusted_sources() returns frozenset() when the env var is unset (test_get_trusted_sources_default_unrestricted asserts default = unrestricted). The security doc states the inverse of the actual default posture."
    blocking: true
    suggested_action: "In docs/security/plugin-trust-boundary.md §3, change the default description to: 'Default: unset = unrestricted (any marketplace source allowed). Set TRUSTED_MARKETPLACE_SOURCES=<comma-separated URLs> to opt into allowlist enforcement.' Mirror the impl-report's documented deviation so the trust-boundary record (consumed by G12) matches code behaviour."
  - id: F2
    severity: medium
    file: backend/app/tools/plugins.py:236
    evidence: "install() only rejects when the plugin is found in the LIST_PLUGINS available[] set AND its source is untrusted; a plugin_id absent from available[] falls through and installs unchecked (test_install_unknown_plugin_allowed confirms). The allowlist gate on install() is therefore partial — add_marketplace() is the only hard gate."
    blocking: false
    suggested_action: "Acceptable per the design assumption (add_marketplace is the primary gate), but make it explicit: add a one-line note in plugin-trust-boundary.md §3 stating install() trusts plugins already surfaced via an approved marketplace and does not re-validate unknown ids. No code change required unless stricter enforcement is desired."
  - id: F3
    severity: medium
    file: backend/tests/test_settings_deny_guard.py:18
    evidence: "_deny_pattern_matches() is a hand-rolled regex re-implementation of the matcher; the deny tests assert that command strings start with the pattern prefix — they do not exercise the real Claude Code CLI permission engine. Design risk #1 required smoke-checking with `claude --disallowedTools`; no evidence of that verification is captured. The core security claim (the deny list actually blocks the tool call) is unverified by automated tests."
    blocking: false
    suggested_action: "Add a note in the impl-report open-questions or the trust-boundary doc citing the manual `claude --disallowedTools 'Bash(claude plugin install:*)'` smoke-check result, OR add an integration test that shells the real CLI with --disallowedTools to confirm enforcement. Non-blocking because the threat note correctly attributes enforcement to the CLI permission system."
---

## Summary

Scope conformance: yes — all 9 files in the impl `files_changed[]` are within the design `iterations[].scope_files[]` union; agent.py was correctly left untouched (I2 is regression-test-only). The test gate passed (4165p/0f, 85.8% cov) and the 4 new backend test files pass locally (25 tests). Verdict is **needs_fix** on one blocking finding: the security trust-boundary doc (`plugin-trust-boundary.md`) states the `TRUSTED_MARKETPLACE_SOURCES` default restricts to `claude.ai/marketplace`, but the shipped code defaults to **unrestricted** (the implementor's own documented deviation) — a security doc that misstates the actual default posture and feeds G12. Two non-blocking findings note the partial install() allowlist (unknown plugins skip the check, by design) and that the deny-list tests validate a hand-rolled regex rather than the real CLI permission engine.

## Findings

- **F1 (high, blocking)** — `docs/security/plugin-trust-boundary.md` §3 claims default = `https://claude.ai/marketplace`; `_get_trusted_sources()` returns an empty (unrestricted) set when the env var is unset. The trust-boundary record states the inverse of reality.
- **F2 (medium, non-blocking)** — `install()` only enforces the allowlist for plugins present in the `available[]` list; unknown ids install unchecked (`test_install_unknown_plugin_allowed`). `add_marketplace()` is the real gate; the install gate is partial by design.
- **F3 (medium, non-blocking)** — Deny-list tests assert against a re-implemented `_deny_pattern_matches()` regex, not the live CLI permission engine; design risk #1's `claude --disallowedTools` smoke-check is uncaptured.

## Verdict

needs_fix. The diff is in-scope, tested, and green, but the security trust-boundary doc materially contradicts the shipped default (default-allow, not default-deny); correcting the doc is a small, recoverable edit for attempt 2.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union; observed_changed_set ⊆ allowed_scope_set (no scope escape).
- The intentional omission of a broad `Bash(claude plugin:*)` deny entry (design risk #1 suggested belt-and-suspenders) is correct, not a defect: a broad prefix would also block the read-only `claude plugin list` / `marketplace list` commands the backend depends on. The six explicit per-subcommand entries cover all known mutations while keeping read paths open.
- Test gate result (`gate_decision: pass`) is taken from the test report; the reviewer did not re-run the full suite as its gate, only the 4 new backend test files for sanity.

## Open questions

- None.

## Next consumer brief

Implementor, re-run iteration **I6** (`docs/security/plugin-trust-boundary.md`) to address **F1**: correct §3 so the documented default matches code — default (unset) is *unrestricted*; the allowlist is opt-in via `TRUSTED_MARKETPLACE_SOURCES=<urls>`. While editing I6, optionally fold in F2 (one line: install() does not re-validate unknown plugin ids) and F3 (cite the `claude --disallowedTools` smoke-check evidence). F2/F3 are non-blocking and may be deferred; only F1 must be resolved to reach `pass`. No source or test code changes are required for the blocker — it is documentation-only.
