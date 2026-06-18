# Memory Bug Fixes

Three critical correctness bugs in the memory system that defeat its purpose.

## Bug 1 — Multiplicative boost from zero (memory_lifecycle.py)

boost() computes min(score * 1.2, 10.0). New items are created with score=0.0, and 0.0 * 1.2 = 0.0 forever. Fix: use additive boost so zero-scored items can actually rise. Add test for boost(0.0, ...).

## Bug 2 — decay() is dead code (memory_lifecycle.py)

decay() is defined but never called. Wire it into MemoryStore.get() before boost() so scores actually age.

## Bug 3 — Injection drops the body (agent.py build_prompt())

build_prompt() only injects first body line if it differs from title. Full body (file paths, procedures, etc.) never reaches the agent. Fix: include full body in memory context.

## Test gaps to fill

- boost(0.0, ...) case
- decay applied at get() time
- full body in build_prompt() memory section
- should_prune() correctly protects boosted items

## Files to change

- backend/app/memory_lifecycle.py (bugs 1 + 2 definition side)
- backend/app/memory_store.py (bug 2 call site)
- backend/app/agent.py (bug 3)
- backend/tests/test_memory_lifecycle.py (new tests)
- backend/tests/test_memory_store.py (new tests)
- backend/tests/test_agent.py (new tests)

All changes on a single feature branch: feature/memory-bug-fixing
