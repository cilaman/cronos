---
cc_version: "1.0"
agent: pipeline-scout
slug: featurefix-worker-decompose
phase: scout
status: done
confidence: 0.90
inputs_used:
  - memory:project_goal_workflow
  - memory:project_architecture_key_modules
  - memory:S1_data_model_impl
  - memory:S2_features_api_impl
  - backend/app/worker.py
  - backend/app/goal_sync.py
  - backend/app/storage.py
  - backend/app/git_ops.py
  - backend/app/feature_hooks.py
  - backend/app/api/features.py
outputs_produced:
  - .cronos/pipeline/featurefix-worker-decompose/scout-report-featurefix-worker-decompose.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/worker.py
    - backend/app/goal_sync.py
    - backend/app/feature_hooks.py
    - backend/app/storage.py
    - backend/app/git_ops.py
    - backend/app/api/features.py (S2 implementation)
  excluded:
    - frontend/: not relevant to worker decomposition logic
    - tests/: coverage at analysis phase
    - deploy/: deployment-only
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "S4 research — decompose-from-backlog in worker.py and feature_sync.py propagation logic; entry points, skill orchestration, done-detection, and git operations"
metrics:
  tool_calls: 18
  files_read: 6
  memory_hits: 4
---

## Summary

S4 decomposes features in PROCESSING state via a dedicated worker branch that orchestrates goal+task creation with realizes linking, then propagates feature state transitions upward. The design mirrors goal_sync.py but operates on FeatureState. Key integration points: (1) worker._run_one adds feature_state=PROCESSING branch calling _run_feature_decompose; (2) feature_sync.propagate_to_feature called from _finalize and tasks.py reply path; (3) enqueue_feature_decomposition hook (currently stubbed) invoked by POST /api/features/{id}/process; (4) git_ops.fetch_origin + new branch_exists_on_origin for done-detection.

## Coverage

### Searched
- backend/app/worker.py: _run_one branching, _finalize state logic, goal_sync integration
- backend/app/goal_sync.py: propagate_to_parent pattern as reference for feature_sync design
- backend/app/feature_hooks.py: enqueue_feature_decomposition contract stub location
- backend/app/storage.py: feature state transition methods, realizes field, set_issue_refs integration
- backend/app/git_ops.py: fetch_origin, detect_default_branch; missing branch_exists_on_origin
- backend/app/api/features.py (S2): /process endpoint wired to enqueue_feature_decomposition

### Excluded
- frontend/: UI layer; S4 is backend worker logic
- tests/: will be written during implementation, reviewed in test phase
- deploy/: out of scope for agent behavior changes

### Strategies
- memory_retrieval: 4 relevant entries found (goal workflow, architecture, S1 data model, S2 API)
- glob_structural: targeted searches of worker.py, goal_sync.py, feature_hooks.py, git_ops.py
- grep_symbol: located _run_one, _finalize, apply_reply, enqueue_feature_decomposition, transition_feature
- read_targeted: full read of critical sections (goal_sync 90 lines; worker _run_one/finalize ~200 lines; feature_hooks stub)

## Findings

### 1. Worker decomposition entry point (_run_one branching)

**Location**: backend/app/worker.py:420-428

```python
async def _run_one(self, task_id: str, user_message: str | None) -> None:
    task = self.store.get(task_id)
    if task is None:
        log.warning("Skipping unknown task %s", task_id)
        return
    if task.type == "goal":
        await self._run_goal(task_id, user_message)
    else:
        await self._run_task(task_id, user_message)
```

**Required change**: Add third branch after task.type=="goal" check:
- If `task.type in ("feature", "fix")` AND `task.feature_state == FeatureState.PROCESSING`: call `_run_feature_decompose(task_id)`
- NEVER fall through to `_run_task` for PROCESSING features (request note 3)
- Pattern: mutual exclusion, not fallthrough

**Design choice**: Whether to add field defensive check (`task.feature_state is not None`) or trust S1 schema. Recommend: trust schema (feature_state only set when type="feature"|"fix").

### 2. Feature decomposition runner (_run_feature_decompose stub location)

**Location**: backend/app/worker.py (method to be added, ~300-350 lines estimated)

**Pattern reference**: `_run_task` (line ~580-730) and `_run_goal` (line ~740-1060)

**Contract from request**:
- Run feature in `auto` mode with a skill that reads brief, designs goal+child tasks, POSTs them with `realizes=<feature_id>` on root goal
- On agent completion:
  - ≥1 realizing item: transition `processing→planned` (SUCCESS)
  - `STATUS:WAIT` / `BLOCKED` or no realizing items: transition `processing→waiting` with question (WAITING)
  - Reuse _finalize state mapping (lines 772-800) for question derivation

**Skill orchestration**: Request ambiguous whether to reuse pipeline-scaffold or create new skill. Key decision point for analysis phase.

### 3. Feature state propagation module (new backend/app/feature_sync.py)

**Location**: New module, analogue of backend/app/goal_sync.py:21-90

**Pattern**: goal_sync.propagate_to_parent(child_id, store, worker_pool)

**Feature-specific extension**:
- `propagate_to_feature(item_id, store, pool)` called from:
  1. worker.py:_finalize (after goal_sync call, ~line 435 in current code)
  2. tasks.py:apply_reply reply path (~line 535 in current code)

**State transitions orchestrated**:
1. **Item→WAITING & Feature PLANNED**: copy question up; `planned→waiting` (uses _finalize mapping for question)
2. **Item→ACTIVE from WAITING**: surface feature; `waiting→planned` (resume path)
3. **Item→DONE or ARCHIVED & Feature PLANNED**: invoke done-detection (see section 5)

**Design note**: Only honor `realizes` on directly-linked root goal. Child's parent is irrelevant; traverse up to root_parent (no parent_id) and check if that goal's realizes == feature_id.

### 4. Finalize integration points and state mapping

**Current _finalize location**: backend/app/worker.py:732-892

**Critical lines**:
- Line 772-800: Status→state mapping (DONE, WAIT, BLOCKED, error handling)
  - `result.status == Status.DONE` → `TaskState.DONE`
  - `result.status == Status.WAIT` → `TaskState.WAITING` with `result.context` as waiting_question
  - `result.status == Status.BLOCKED` → `TaskState.WAITING` with "Blocked: {context}" as waiting_question
  - `result.exit_code != 0` → `TaskState.WAITING` with crash message
- Line 811-817: finalize_run persists new_state + waiting_question + history_entry
- Line 890: `await goal_sync.propagate_to_parent(task_id, self.store, self._pool)`

**S4 insertion point**: After goal_sync call, add:
```python
await feature_sync.propagate_to_feature(task_id, self.store, self._pool)
```

**Question derivation**: feature_sync should reuse lines 772-800 logic when needed (e.g., when feature item→WAITING and feature is PLANNED).

### 5. Done-detection via git branch check

**Current pattern**: 
- backend/app/git_ops.py:324-328 `fetch_origin(space_dir)`: async, uses _auth_env for credentials
- backend/app/git_ops.py:331-351 `detect_default_branch(space_dir, hint)`: queries remote

**Required new function**: `branch_exists_on_origin(space_dir: Path, branch: str) -> bool`

**Implementation sketch**:
```python
async def branch_exists_on_origin(space_dir: Path, branch: str) -> bool:
    """Return True if branch exists on origin remote (after fetch).
    
    Validates branch name, fetches origin, then queries git for
    refs/remotes/origin/{branch}. Returns False on any error (safe default).
    """
    validate_branch(branch)
    # Caller should have already called fetch_origin; this is read-only verification.
    code, _, _ = await _run("rev-parse", "--verify", f"origin/{branch}", cwd=space_dir)
    return code == 0
```

**Caller responsibility**: feature_sync.propagate_to_feature done-detection path must:
1. Call `await git_ops.fetch_origin(space_dir)` first
2. Strip date prefix from feature.id to get slug (e.g., "2026-06-03-1234-widget-feature" → "widget-feature")
3. Query `await git_ops.branch_exists_on_origin(space_dir, f"feature/{slug}")`
4. Only transition `planned→done` when all items DONE/ARCHIVED AND branch absent

**Design decision**: Whether to keep fetch outside feature_sync (caller responsibility) or move inside. Recommend: keep outside (explicit, avoids N fetches if multiple realizing items).

### 6. Feature API /process endpoint (S2 implementation reference)

**Location**: backend/app/api/features.py:330-368

**Flow**:
1. User POST /api/features/{feature_id}/process
2. API transitions feature to PROCESSING via `store.transition_feature(feature_id, FeatureState.PROCESSING, allowed=FEATURE_USER_TRANSITIONS)`
3. Fires mirror (reason='state_change')
4. Awaits `enqueue_feature_decomposition(task)` (currently no-op stub at feature_hooks.py:178-190)

**S4 hook contract**: enqueue_feature_decomposition signature must remain unchanged. S4 implementation should:
- Extract feature.brief as decomposition prompt
- Construct skill brief (e.g., pipeline-scaffold input or custom decomposition skill brief)
- Enqueue a task via worker with realizes=feature_id on the created goal
- **NOT** perform state transition (already done by API)

### 7. Storage extensions from S1 (feature state, realizes, issue tracking)

**Available from S1 impl** (backend/app/storage.py):
- `transition_feature(task_id, new_state, allowed)`: line 819, enforces FEATURE_WORKER_TRANSITIONS
- `realizing_items(feature_id)`: line 1309, returns TaskSummary[] where realizes == feature_id
- `set_realizes(item_id, feature_id)`: line 1322, enforces validate_realizes cycle check
- `set_issue_refs(task_id, issue_number, issue_url, proposed_issue_path)`: line 1353

**For S4 use**:
- Call `realizing_items(feature_id)` to check if ≥1 item exists for state transition decision
- Call `transition_feature()` with FEATURE_WORKER_TRANSITIONS for worker-initiated transitions

### 8. Task state machine and reply path integration

**Current reply path** (backend/app/api/tasks.py:522-537):
```python
outcome = await store.apply_reply(task_id, body.message)
if outcome.should_enqueue:
    await get_worker_for_task(request, task_id).enqueue(task_id, user_message=body.message)
await goal_sync.propagate_to_parent(task_id, store, pool)
```

**S4 insertion point**: After goal_sync, add feature_sync call:
```python
await feature_sync.propagate_to_feature(task_id, store, pool)
```

**Relevance**: When a realizing task (type="task"|"goal" with realizes="feature-id") transitions (e.g., user resumes it), feature_sync detects the realizes link and applies corresponding feature transitions.

### 9. Model fields summary (from S1)

**Task model additions**:
- `feature_state: FeatureState | None = None`
- `feature_key: str | None = None` (e.g., "FEAT-001")
- `realizes: str | None = None` (task_id of feature/fix)
- `issue_number: int | None = None`
- `issue_url: str | None = None`
- `proposed_issue_path: str | None = None`

**TaskType extended**: `Literal["task", "goal", "issue", "feature", "fix"]`

**FeatureState enum**:
- BACKLOG, PROCESSING, PLANNED, WAITING, DONE

## Assumptions

- Decomposition skill (pipeline-scaffold or custom) will be responsible for setting realizes field via API; S4 worker logic does not mutate realizes (design note 6 says "reuse existing skills").
- feature_sync.propagate_to_feature is the ONLY place that mutates feature_state from PROCESSING→PLANNED or PROCESSING→WAITING after decomposition completes; no other code path should.
- Branch name convention is `feature/{slug}` where slug is the feature.id with date prefix stripped (per request note 4).
- fetch_origin is called before branch_exists_on_origin to ensure origin is up-to-date; feature_sync caller (or _run_feature_decompose finish handler) is responsible for the fetch.
- feature_state transitions bypass TaskState entirely; they are independent state machines on the same Task entity, not a nested state. Never confuse the two.

## Open questions

- **Decomposition skill**: Should S4 reuse pipeline-scaffold (which would need a `realizes` argument) or create a new feature-specific decomposition skill? Request is ambiguous ("reuse [[pipeline-scaffold]]/[[create-goal]] with a `realizes` arg"). Design phase should clarify.
- **Done-detection timing**: Should feature.state transition to DONE immediately after the last realizing item finishes, or only when feature-branch is merged AND closed? Request says "branch gone from origin" (merged + force-pushed), which implies asynchronous detection. Should feature_sync.propagate_to_feature poll periodically, or rely on user-triggered checks via API?
- **Parallel realizing items**: If a feature has multiple realizing goals/tasks running concurrently, what happens when the first one transitions to WAITING? Does the feature immediately go PLANNED→WAITING (blocking others), or does each item have independent waiting state? Request says "child waiting bubbles feature to waiting" (singular), suggesting no parallelism guarantee at this stage.

## Next consumer brief

**For analysis agent**:

1. **Entry points to document**: 
   - Worker._run_one branch for feature_state=PROCESSING (line 420)
   - POST /api/features/{id}/process transitions to PROCESSING then calls enqueue_feature_decomposition (features.py:330)
   - Reply path propagation insertion point (tasks.py:535, api/tasks.py line 524-537)

2. **Modules to create/extend**:
   - New backend/app/feature_sync.py analogue of goal_sync.py
   - backend/app/worker.py: add _run_feature_decompose method
   - backend/app/git_ops.py: add branch_exists_on_origin read-only function
   - backend/app/feature_hooks.py: enqueue_feature_decomposition body (currently no-op)

3. **State transitions to specify**:
   - PROCESSING→PLANNED (≥1 realizing item created)
   - PROCESSING→WAITING (no items, or agent returned WAIT/BLOCKED)
   - PLANNED→WAITING (child item→WAITING while feature PLANNED)
   - WAITING→PLANNED (resume: child item→ACTIVE)
   - PLANNED→DONE (all items DONE/ARCHIVED AND branch absent from origin)
   - Blocker: done-detection timing (poll vs event-driven?)

4. **Skill orchestration gap**: Decomposition skill signature and behavior (does it know about realizes? does S4 worker set it or skill?).

5. **Unresolved design choices from request**:
   - Reuse pipeline-scaffold with `realizes` arg vs new skill?
   - Async done-detection polling vs manual API check?
   - Concurrent realizing item parallelism guarantees?

6. **Test focus areas** (for review phase):
   - Worker branches correctly on feature_state=PROCESSING
   - feature_sync mirrors goal_sync transitions but on FeatureState
   - Done-detection: branch_exists_on_origin correctly validates; all-items-terminal condition
   - reply path propagates to both parent goal AND feature
   - realizes linking prevents cycles (validate_realizes already in S1)
   - Issue close fires on feature→DONE (via mirror_feature_to_github reason='state_change' check)
