Build the `DevRuntimeManager` core in
`backend/app/dev_runtimes.py` (extends SG1's allocator). Keyed by
`space_id`; mirrors the agent subprocess pattern. **No HTTP API or
UI in this subgoal.**

**Lifecycle.** `start(space_id)` / `stop(space_id)` /
`restart(space_id)`. Spawn with
`asyncio.create_subprocess_exec` mirroring `run_agent`
([agent.py:254-260](backend/app/agent.py#L254-L260)), `cwd =
space_dir(space_id)`
([space_storage.py:659-669](backend/app/space_storage.py#L659-L669)),
env inheriting + the allocated ports. **Net-new:** pass
`start_new_session=True` so the whole process group can be killed
(dev servers fork children — `run_agent` does not do this).
Command resolution: `kind != custom` runs `command`;
`kind=custom` runs `start_script` (stop via `stop_script`).

**Status.** Track `stopped | starting | running | healthy |
unhealthy | exited | error` per space (registry dict modeled on
`WorkerPool._workers`,
[worker_pool.py:39](backend/app/worker_pool.py#L39)).

**Log capture + pub/sub.** Capture stdout/stderr into a bounded
ring buffer (mirror `drain_stderr`,
[agent.py:269-283](backend/app/agent.py#L269-L283)) and a stdout
read loop ([agent.py:344-375](backend/app/agent.py#L344-L375))
that does **not** block on EOF (see the comment at
[agent.py:337-343](backend/app/agent.py#L337-L343) — dev servers
keep the pipe open). Fan lines out to subscribers via a
`subscribe(space_id)`/`_publish` pair mirroring
[worker.py:161-178](backend/app/worker.py#L161-L178) +
[worker.py:899-930](backend/app/worker.py#L899-L930) (replay
buffer + drop-oldest backpressure).

**Stop/restart.** SIGTERM the process group → wait 2s → SIGKILL
(mirror `kill_on_cancel`,
[agent.py:285-302](backend/app/agent.py#L285-L302)) using
`os.killpg`. `restart` = stop then start.

**Health poller.** Per running runtime, an async task GETs
`health_url` every `CRONOS_DEV_HEALTH_INTERVAL_S` (default 3):
200 → `healthy` and record the URL; non-200/exception →
`unhealthy`; stop polling on process exit. Skip if no `health_url`.

**Shutdown.** `stop_all()` mirroring `WorkerPool.stop_all`
([worker_pool.py:132-143](backend/app/worker_pool.py#L132-L143)).

**Acceptance** (unit, mocked subprocess + health client): `start`
spawns with correct cmd/cwd/env and `start_new_session=True`;
stdout lines are captured and replayed to a subscriber; the health
poller flips `running → healthy` on a mocked 200; `stop`
terminates the process group; `restart` = stop then start; two
managers on different spaces don't collide on ports.

