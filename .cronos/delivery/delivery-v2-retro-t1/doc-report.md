---
class: doc
goal_slug: delivery-v2-retro-t1
phase: doc
status: done
---

# Doc Report — delivery/v2 F2: Tier-1 PR path

## Summary

This phase documented two new portable libraries (`lib/git_pr.py` and `lib/improve.py`) added by the implementation phase, and updated the bundle layout and testing sections in the README to reflect the expanded core. The deliverable is purely additive: package README expanded to describe the new modules' APIs, design patterns, and test coverage. **Zero source edits; documentation only.**

## Documentation Updates

### `packages/delivery-workflow/README.md`

**Bundle Layout (lines 27–34):**
- Added `lib/git_pr.py` — portable PR emission helper
- Added `lib/improve.py` — Tier-1/Tier-2 back-half applier

**Libraries section (added two subsections):**

#### New `lib/git_pr` subsection
Documented the **portable git/gh PR helper** used to emit Tier-1 improvement proposals:
- Function signature: `emit_pr(title, body, finding_id, *, branch, repo_root, proposals_dir, gh_probe=None, runner=None) -> str`
- Key features: stable base ref capture, HEAD restore on all paths, subprocess-only, injectable for testing
- Example usage showing PR URL or fallback path return value
- Cross-references spec §3.2 (tiered boundary) and DD-002 (portability decision)

#### New `lib/improve` subsection
Documented the **Tier-1/Tier-2 back-half applier** for self-improvement routing:
- Public API: `classify_findings()`, `render_proposal()`, `run_back_half()`
- Design pattern: fix_type-authoritative classification, structural safety guarantee for Tier-1 non-mutation (REQ-005)
- CLI usage: `python -m lib.improve <retro_artifact> --evals-passed [true|false] --proposals-dir <path>`
- Key design constraints: Tier-0 consumes only `tier0` list, no PR if evals fail, all writes additive proposal documents
- Cross-references spec §3.2–3.5 and design decisions DD-001–003

**Testing section (lines 363–372):**
- Updated test count from 231 to 324 (reflects new test files + related test growth)
- Added `test_tier1_no_auto_apply.py` — REQ-005 hard safety assertion
- Added `test_improve.py` — routing, no-PR-on-red, one-PR-per-finding, Tier-2 escalate-only, fence fields

## Intentionally not updated

| File | Reason |
|------|--------|
| `packages/delivery-workflow/lib/git_pr.py` | Module has comprehensive docstrings (module + function + Parameters section); no separate doc file needed |
| `packages/delivery-workflow/lib/improve.py` | Module has comprehensive docstrings (module + Public API + CLI usage sections); no separate doc file needed |
| `packages/delivery-workflow/skills/improve/SKILL.md` | Already documented as part of implementation phase; not a doc file per se |
| `packages/delivery-workflow/schemas/improvement.schema.yaml` | Schema is self-documenting via inline comments and review report already covers the field additions |
| `packages/delivery-workflow/tests/test_*.py` | Test files are implementation artifacts, not user documentation |

## Proportional depth

The changes are **module-level API documentation**: two new portable libraries with clear responsibility boundaries (git/gh subprocess, Tier-1/Tier-2 routing), added to the bundle layout and Library reference sections. This depth is proportional to:
- New public APIs exposed (4 functions: `emit_pr`, `classify_findings`, `render_proposal`, `run_back_half`)
- Portability implications (zero `app.*` imports, injectable for testing, subprocess-only)
- Spec traceability (DD-002, DD-003, §3.2–3.5, REQ-001–007)

A single consolidated README section per library (not isolated reference docs) fits the package's existing style and keeps the surface discoverable.

## Validation

✓ README.md parses as valid Markdown
✓ Code examples in library sections are syntactically correct Python
✓ All cross-references to spec sections and DDs are accurate
✓ Test count reflected in README matches `pytest --collect-only` output (324)

## delivery_status

```delivery_status
{
  "status": "done",
  "produces": "doc",
  "artifact_paths": [".cronos/delivery/delivery-v2-retro-t1/doc-report.md"],
  "fields": {
    "docs_updated": ["packages/delivery-workflow/README.md"],
    "intentionally_not_updated": [
      "packages/delivery-workflow/lib/git_pr.py: module has comprehensive docstrings",
      "packages/delivery-workflow/lib/improve.py: module has comprehensive docstrings",
      "packages/delivery-workflow/skills/improve/SKILL.md: already documented in implementation phase",
      "packages/delivery-workflow/schemas/improvement.schema.yaml: schema is self-documenting; coverage in review report",
      "packages/delivery-workflow/tests/test_*.py: implementation artifacts, not user documentation"
    ]
  },
  "open_questions": []
}
```
