---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: sg1-sentinel-bridge
phase: doc
status: done
confidence: 0.85
inputs_used:
  - memory:project_parse_status_fix
  - memory:project_trace_structure
  - memory:project_pipeline_foundation_merged
  - .cronos/pipeline/sg1-sentinel-bridge/review-report-sg1-sentinel-bridge--attempt1.md
  - .cronos/pipeline/sg1-sentinel-bridge/impl-report-sg1-sentinel-bridge--i1.md
  - .cronos/pipeline/sg1-sentinel-bridge/impl-report-sg1-sentinel-bridge--i2.md
  - .cronos/pipeline/sg1-sentinel-bridge/impl-report-sg1-sentinel-bridge--i3.md
  - docs/HARNESSES.md
  - CLAUDE.md
outputs_produced:
  - .cronos/pipeline/sg1-sentinel-bridge/doc-report-sg1-sentinel-bridge.md
  - docs/HARNESSES.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: CLAUDE.md
    reason: "memory_parser module already documented; parse_node_status_block is a new internal function used by parse_status (not a public API); no user-visible API change in CLAUDE.md needed."
  - path: README.md
    reason: "Agent completion signals and parse_status details are harness-implementation topics; README.md documents quick-start and basic ops; users are directed to HARNESSES.md for signal details."
  - path: TESTING.md
    reason: "Comprehensive test suite already added in I3 (43 tests in test_parse_status_bridge.py covering all 5 vocab values, 4-tier precedence, needs_fix mapping); no new testing guidance needed for users."
  - path: deploy/VPS_SETUP.md
    reason: "Deployment configuration unchanged; this is a backend-internal signal parsing refactor; no new environment variables, system dependencies, or deployment steps required."
metrics:
  tool_calls: 8
  files_read: 6
  memory_hits: 3
  docs_updated: 1
  docs_considered: 5
---

## Summary

The SG1 Sentinel Bridge implementation adds a 4-tier parse_status() resolution model for agent completion signals, enabling integration with external systems. The implementation modified:

1. **backend/app/memory_parser.py** (I1) — Added `parse_node_status_block()` to extract status and summary from `node_status` JSON fenced blocks (new Sentinel Bridge channel).
2. **backend/app/agent.py** (I2) — Extended `parse_status()` from 2-tier to 4-tier precedence: node_status (tier 1) > cronos_status (tier 2) > delivery_status (tier 3) > STATUS: line (tier 4, deprecated). Introduced `_VOCAB_MAP` and `_map_vocab()` for context-sensitive status vocabulary normalization.
3. **backend/tests/test_parse_status_bridge.py** (I3) — Added 43 comprehensive tests covering all 5 vocab values (`done`, `wait`, `blocked`, `failed`, `needs_fix`), both bridge tiers, 4-tier precedence, dual-branch `needs_fix` mapping, backward compatibility, and finalizer integration.

User-facing documentation updated: **docs/HARNESSES.md** now documents the 4-tier agent completion sentinel model, clarifying precedence and introducing the new `node_status` channel for external system integration. The Signal precedence section in the Decision node documentation also reflects the updated tier ordering.

This is a backend-only internal change with no new user-visible API surface — existing harness behavior is fully preserved. The integration point is the new `node_status` block format documented for external systems that wish to emit status signals.

## Updated docs

| File | Change summary |
|------|----------------|
| docs/HARNESSES.md | Updated § 7 Agent completion sentinel to document 4-tier model (node_status → cronos_status → delivery_status → STATUS: line). Updated § 8 Decision signal precedence to reflect new tier ordering and introduce Sentinel Bridge terminology. Updated § 14 Quick reference Agent completion signals section. |

## Intentionally not updated

- **CLAUDE.md** — memory_parser module already documented; parse_node_status_block is a new internal function used by parse_status (not a public API); no user-visible API change in CLAUDE.md needed.
- **README.md** — Agent completion signals and parse_status details are harness-implementation topics; README.md documents quick-start and basic ops; users are directed to HARNESSES.md for signal details.
- **TESTING.md** — Comprehensive test suite already added in I3 (43 tests in test_parse_status_bridge.py covering all 5 vocab values, 4-tier precedence, needs_fix mapping); no new testing guidance needed for users.
- **deploy/VPS_SETUP.md** — Deployment configuration unchanged; this is a backend-internal signal parsing refactor; no new environment variables, system dependencies, or deployment steps required.

## Assumptions

- The 4-tier parse_status() resolution is fully backward-compatible; existing callers using `cronos_status` blocks are unaffected (tier 2 remains unchanged).
- The new `node_status` channel (tier 1) is the Sentinel Bridge tier for external system integration; documentation anchors this with terminology ("Sentinel Bridge channel (new)").
- The `is_runner_task` parameter added to `parse_status()` is keyword-only (default False), preserving the ~35 existing positional callers per R5 (backward compat).
- The TODO(OQ-1 sg1-sentinel-bridge) marker in `_map_vocab()` is a grep-discoverable anchor for the deferred runner-tag wiring task; both branches of the needs_fix mapping are covered by test cases as the executable spec.
- Memory hits counted from the context block: project_parse_status_fix, project_trace_structure, project_pipeline_foundation_merged.

## Open questions

- None. The deferred OQ-1 runner-tag call-site wiring (when `is_runner_task=True` at runner agent call sites) is explicitly out-of-scope per the design report and captured by executable test specs in `TestNeedsFixMapping`.

## Next consumer brief

The documentation update is complete. Users running harnesses with agent nodes should be aware that:

1. **New Sentinel Bridge channel**: External systems can now emit `node_status` JSON blocks (with lowercase status values) as the highest-precedence completion signal.
2. **Tier reordering**: The documented precedence is now node_status (new) > cronos_status > delivery_status > STATUS: line, reflecting the 4-tier implementation.
3. **No breaking changes**: Standard harnesses using `cronos_status` or `delivery_status` blocks continue to work exactly as before; the change is purely additive.

If you have harnesses relying on agent completion signals, review the updated Agent completion sentinel section in docs/HARNESSES.md (§ 7) and the Decision signal precedence table (§ 8) to understand the new tier ordering. No action is required for existing harnesses — they remain fully functional.

The implementation resolves bug #2 (delivery_status:done now correctly maps to DONE status, previously failed to route) and enables integration with external CC-v1 pipeline systems via the node_status channel.
