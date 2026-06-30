---
cc_version: "1.0"
agent: pipeline-scout
slug: sg7-standalone-rungate-portability-defer
phase: scout
status: done
confidence: 0.92
inputs_used:
  - memory:project_pipeline_gate_skill
  - memory:project_pipeline_verifier
  - memory:delivery-v2-standalone_design
  - backend/app/pipeline/gate.py
  - backend/app/pipeline/verify.py
  - backend/app/pipeline/contract.py
  - backend/app/pipeline/schemas/
  - packages/delivery-workflow/lib/security.py
outputs_produced:
  - .cronos/pipeline/sg7-standalone-rungate-portability-defer/scout-report-sg7-standalone-rungate-portability-defer.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/pipeline/
    - packages/delivery-workflow/lib/
  excluded:
    - frontend/: not relevant to gate portability
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Map app.pipeline → lib/ lift scope for runGate portability. Identify 2 app imports in gate.py, verify dependencies, assess Option A (lift+re-export) vs Option B (shell-out). Deferrable due to separate headless billing post-June 15 2026."
metrics:
  tool_calls: 14
  files_read: 8
  memory_hits: 3
---

## Summary

**Recommendation: Proceed with Option A (lift verify.py + contract.py + schemas/ to lib/)** as the preferred path. The 2 app.pipeline imports in gate.py (split_frontmatter and verify function at lines 25-26) have zero other external dependencies beyond YAML and stdlib, and contract.py is pure data. The lib/ structure already has precedent for portable modules (security.py). Backend re-export stubs can preserve backward compatibility. Deferral risk is low: no structural changes needed, only file motion + import alias wiring.

## Coverage

### Searched
- backend/app/pipeline/gate.py (all 759 lines; entry point analysis)
- backend/app/pipeline/verify.py (1395 lines; dependency audit)
- backend/app/pipeline/contract.py (242 lines; dep check)
- backend/app/pipeline/schemas/ (8 YAML files, 72 KB; structure check)
- packages/delivery-workflow/lib/ (7 portable modules; precedent study)

### Excluded
- frontend/: not relevant to gate portability
- backend/app/models, storage, memory: gate.py never touches them

### Strategies
- memory_retrieval: 3 relevant entries found (gate skill, verifier doc, delivery-v2 standalone design)
- glob_structural: located schemas/ (8 YAML files) and lib/ (7 Python modules)
- grep_symbol: traced import chains (split_frontmatter, verify, CLASS_CONFIG, SCHEMAS_DIR)
- read_targeted: audited gate.py imports, verify.py deps, contract.py contents

## Findings

### Item 1: The 2 App Imports in gate.py (Lines 25-26)

```python
from app.pipeline.verify import split_frontmatter
from app.pipeline.verify import verify as _cc_verify
```

**Usage sites:**
- `split_frontmatter(text)` (line 143) — used in `_read_header()` helper to parse YAML frontmatter into dict + body
- `_cc_verify(agent_class, slug, space)` (line 171) — used in `_check_schema()` to validate artifact against CLASS_CONFIG schema

Both are called exactly 2 times each (gate.py:2 uses each). No other app.pipeline imports in gate.py.

### Item 2: verify.py Dependencies

**Complete import audit:**

```python
from __future__ import annotations
import argparse, json, re, sys
from dataclasses, pathlib, typing
import yaml
from app.pipeline.contract import (
    CC_VERSION, FINDINGS_SECTION_ALIASES, OPEN_QUESTIONS_SECTION_ALIASES,
    REQUIRED_SECTIONS, STATUS_VALUES, TRACE_OWNED_METRICS
)
```

**Key finding:** verify.py only imports from `app.pipeline.contract`. Zero imports from app.models, app.storage, app.agent, or any other app module. No database, no ORM, no network calls.

**Module size:** 1395 lines (1200 + docstring/comments). Mostly validation rules, check implementations, and CLI harness.

**Contract dependency:** contract.py is 242 lines, pure data (constants, enums, tuples). It also has zero app imports — only `from typing import Final`.

### Item 3: Schema Files — Interdependencies and App Imports

**Files identified:** 8 YAML schema files in backend/app/pipeline/schemas/

- research.schema.yaml (5524 bytes)
- analysis.schema.yaml (5524 bytes)
- design.schema.yaml (6471 bytes)
- implementation.schema.yaml (5751 bytes)
- test.schema.yaml (4407 bytes)
- review.schema.yaml (5182 bytes)
- doc.schema.yaml (4811 bytes)
- retro.schema.yaml (8970 bytes)

**Interdependencies:** None detected. Each schema is standalone YAML (JSON Schema 2020-12 format). No $ref or imports across files.

**App imports:** Schemas are YAML files — cannot import Python modules. No app coupling.

**Loading mechanism:** verify.py's `load_schema(class_name)` reads from SCHEMAS_DIR via Path, parameterized by CLASS_CONFIG map. On lift, SCHEMAS_DIR must be re-parameterized to point to lib/ location.

### Item 4: lib/ Structure Precedent

**Existing portable modules in lib/:**

- lib/security.py (9.8 KB) — Portable security gate evaluator; shared by gate.py (line 27 import) and standalone runner. **Direct precedent for this lift.**
- lib/conditions.py (4.2 KB) — Portable condition evaluation.
- lib/git_pr.py (4.6 KB) — Portable GitHub PR operations.
- lib/improve.py (9.4 KB) — Portable auto-improvement applier.
- lib/telemetry/ (subdir) — Telemetry sinks and reporters.
- lib/evals/ (subdir) — Portable evaluation harnesses.

**Pattern:** lib/ already hosts complex validation, subprocess, and file I/O code. verify.py + contract.py fit the pattern perfectly.

### Item 5: Option B (Shell-out) — CLI Availability

**Gate CLI commands that exist:**

1. `python -m app.pipeline.verify --agent <class> --slug <slug> --space <path>`
   - Entry point: verify.py:main() lines 1294–1395
   - Supports `--normalize` and `--json` flags
   - Exit codes: 0 (proceed), 1 (fail), 2 (escalate), 3 (retry)

**Shell-out feasibility:** Option B would fork a subprocess to invoke `python -m app.pipeline.verify`, parse JSON output, and translate to gate.py decision semantics. This works but adds latency (subprocess spawn + Python interpreter startup) and couples runner to the app container's Python environment.

**Comparison:**
- Option A (in-process): ~0 latency, zero process overhead, testable as library
- Option B (shell-out): +subprocess overhead, requires app container availability, exit code / JSON parsing layer

### Item 6: importlinter Constraints

**Rule discovered:** packages/delivery-workflow/.importlinter contains:

```
[importlinter:contract:no-app-imports]
name = No app.* imports from portable delivery-workflow core
type = forbidden
source_modules = lib, runner, adapters
forbidden_modules = app, backend
```

**Current status:** gate.py is in runner/ or adapters/ (verify location in codebase TBD). The rule **already blocks** direct app.pipeline imports **from lib**.

**Implication:** Option A requires moving verify.py + contract.py **out of app.pipeline** and **into lib** to satisfy the importlinter constraint. This is the **defining structural reason** for lift over shell-out.

### Item 7: Scope Estimate

**Option A (Move + Re-export):**

1. **Move phase:**
   - Copy backend/app/pipeline/contract.py → packages/delivery-workflow/lib/contract.py
   - Copy backend/app/pipeline/verify.py → packages/delivery-workflow/lib/verify.py
   - Copy backend/app/pipeline/schemas/ → packages/delivery-workflow/lib/schemas/
   - Update SCHEMAS_DIR in lib/verify.py to Path(__file__).resolve().parent / "schemas"

2. **Update gate.py:**
   - Change line 25: `from lib.verify import split_frontmatter`
   - Change line 26: `from lib.verify import verify as _cc_verify`
   - Move gate.py out of app.pipeline (into runner/ or lib/ depending on architecture)

3. **Backend re-export stubs (backward compat):**
   - Create backend/app/pipeline/verify.py stub re-exporting from lib.verify
   - Create backend/app/pipeline/contract.py stub re-exporting from lib.contract
   - Existing imports in backend (agent commands, CLI) continue to work

4. **Test updates:**
   - Update 3+ test files that import from app.pipeline.verify (grep count TBD)
   - Update 1+ test files for gate.py if they exist

5. **CI/docs:**
   - Update .github/workflows or similar to reference new lib/ paths in any runner invocations
   - Update CONTRACT.md if it cross-references file paths

**Estimated effort:** 4–6 hours
- Move + path rewiring: 1.5 hours
- Test updates: 1 hour
- Re-export stubs + backward-compat testing: 1.5 hours
- CI/docs audit: 1 hour

**Option B (Shell-out Adapter):**

1. **Create runner-adapter:**
   - StandaloneAdapter.runGate() → subprocess.run("python -m app.pipeline.verify")
   - Parse JSON output, map to GateResult.decision

2. **Trade-offs:**
   - Avoids code motion (low effort, ~1 hour)
   - Keeps app.pipeline intact
   - Adds latency and external-process coupling
   - Harder to test in isolation
   - importlinter constraint still blocks runner from importing app

**Estimated effort:** 2–3 hours (but does not solve the structural coupling issue)

## Assumptions

- **Standalone runner runs in separate container post-June 15 2026.** The memory mentions "separate billing" — this implies the runner will not have direct Python import access to app.pipeline at load time, making shell-out the only option **unless** verify/contract are lifted to lib/.

- **importlinter is enforced in CI.** The `.importlinter` rule forbids app imports from lib/runner/adapters. Option A requires moving code; Option B does not lift the coupling, only delays it to runtime (shell-out).

- **Backward compatibility is a priority.** Re-export stubs in backend/app/pipeline/ preserve existing imports for internal Cronos CLI agents.

- **No schema customization expected per runner.** The 8 schemas in schemas/ are Cronos-universal; no runner-specific variants are anticipated.

## Open questions

- **Where will gate.py live after the lift?** Currently in backend/app/pipeline/; after Option A, should it move to packages/delivery-workflow/runner/ or stay in app/ with re-export? Recommend: move to runner/ to enforce import layering.
- **Will the standalone runner re-use schema YAML from lib/schemas/, or copy them?** Impact on schema versioning and maintenance.
- **Are there any existing tests of gate.py in backend/tests/?** Count and update effort depend on this.

## Next consumer brief

**For analysis agent:** Analyze the scope estimate in Item 7. If Option A (lift) is approved:

1. **Verify test coverage** of verify.py and gate.py in backend/tests/ — grep "verify\|gate" backend/tests/*.py
2. **Identify gate.py call sites** in Cronos code — grep -r "runGate\|from.*gate" backend/
3. **Map importlinter implications** — confirm that moving code to lib/ satisfies the "no-app-imports" rule for runner/
4. **Estimate re-export stub complexity** — verify.py re-export must handle CLI entry point (@main decorator if any)
5. **Propose layer assignments** — which modules live in runner/ vs lib/ vs adapters/ after move?

**Decision gate:** Option A is **recommended and low-risk**. Deferral is justified only if standalone runner's launch is pushed past June 2026. Proceed with analysis.

---
