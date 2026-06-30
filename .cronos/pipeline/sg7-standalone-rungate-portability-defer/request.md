Spec 7 — Standalone runGate portability

After SG4/SG5, the only remaining app-coupling in the runner is `runGate`. The gate operation (gate.py) imports from `app.pipeline.verify` (2 symbols: line 25-26 of gate.py).

Everything else is already portable:
- state.read/write → lib/state (portable)
- telemetry.emit + budget kill-switch → lib/telemetry (portable)
- evalCondition → lib/conditions (SG3 lifts this)
- dispatchAgent → trace_parser.py has zero app imports
- escalate → via state.write (portable)
- events → adapter no-ops/logs for standalone

### Action (two options)

**Option A (preferred): lift verify.py + schemas/ to lib/**
Move `backend/app/pipeline/verify.py` → `packages/delivery-workflow/lib/verify.py`
Move `backend/app/pipeline/schemas/` → `packages/delivery-workflow/lib/schemas/`
Update gate.py to import from lib.verify
Re-export from app.pipeline.verify for backward compat

**Option B: shell-out**
StandaloneAdapter.runGate shells out to the same verify commands (subprocess call to the gate CLI)

### Why deferrable
Standalone uses headless `claude -p` (bills to separate metered credit after June 15 2026). The runner's budget ceiling (telemetry.emit → BudgetExceededSignal → escalate) is the kill-switch — already in lib/telemetry.
Building standalone is a separate future effort; this spec records what it needs so nothing in SG4/SG5 blocks it.

### References
- `backend/app/pipeline/gate.py` — the 2 app imports to sever
- `backend/app/pipeline/verify.py` — the verification logic to lift
- `backend/app/pipeline/schemas/` — 7 schema files to lift
- `packages/delivery-workflow/lib/` — destination

