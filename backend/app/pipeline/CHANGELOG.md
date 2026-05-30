# CC Pipeline Contract Changelog

Version history for `CC_VERSION` in `backend/app/pipeline/contract.py`.

Every pipeline run stamps its `cc_version` into:
- `pipeline-state.json` top-level field (set at `init_pipeline` time)
- Each phase entry in `pipeline-state.json["phases"][phase]["cc_version"]`
- Each line in `phases-log.jsonl["cc_version"]`

This three-layer stamp enables replay and audit even when the contract is bumped
mid-pipeline: each phase record shows exactly which version governed it.

---

## Versioning rules

- **Patch (1.0 → 1.0)**: no bump. Clarifications, docs, new optional fields that
  old verifiers ignore.
- **Minor (1.0 → 1.1)**: additive schema changes that old verifiers tolerate
  (new optional header fields, new R-rules that old verifiers do not enforce).
  Bump the patch component: `"1.0"` → `"1.1"`.
- **Breaking (1.x → 2.0)**: any change that makes existing artifacts invalid
  under the new verifier. Bump the major component. The verifier MUST reject
  artifacts whose `cc_version` is outside the supported set.

`CC_VERSION` is a plain string, not semver — the verifier does an exact-set
membership check, not a range comparison. When bumping, add the new version
string to `SUPPORTED_VERSIONS` (introduced alongside any breaking change) so
the verifier can accept both old and new artifacts during a migration window.

---

## Version history

### 1.0 — 2026-05-30 (initial)

Initial Cronos adaptation of Delivery Notes Agent Contract v1.0.

Key decisions:
- `memory_hits` replaces Delivery Notes' `kb_hits` (Cronos has no `.kb/`
  substrate; per-space memory store is the equivalent).
- `duration_s` and `token_spend` are trace-owned — agents NEVER write them.
  They are derived post-hoc from the run trace by `trace_parser`.
- Artifacts live at `{space}/.cronos/pipeline/{goal_slug}/{phase}-report-{goal_slug}.md`
  instead of Delivery Notes' `.ai/pipeline/{slug}/...`.
- `cc_version` is a mandatory YAML header field (Delivery Notes encoded version
  implicitly in the contract document path).
- No `kb-first preflight` or `sandboxed architect convention` — Cronos memory
  retrieval handles the validated-decisions substrate automatically.

Delivered by goal `pipeline-foundation-cc-v1-contract-schem` (2026-05-30,
commit b91d9ec). 1144 backend + 673 frontend tests green, 81.93% coverage.
