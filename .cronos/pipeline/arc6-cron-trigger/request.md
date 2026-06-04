Add a cron scheduler: one `asyncio.create_task(cron_loop, …)` in main.py `lifespan`
alongside the existing `watcher`/`archiver`/`memory_pruner` loops.

- Re-read the canonical harness list each tick (no per-harness timers; no
  double-registration on `watch_spaces_dir` reload). A `cron` Trigger carries its
  expression in `data`.
- **Overlap guard:** skip a tick if the harness already has an `active` run (a set check;
  single-process asyncio, no lock).
- Parse cron expr + timezone correctly. Missed ticks across restart are not back-filled —
  document this.

Acceptance: a cron Trigger fires at the scheduled time (shortened interval in tests);
a tick during an active run is skipped.

