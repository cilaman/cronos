from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from .stats import TaskStats

log = logging.getLogger("cronos.stats_store")

CRONOS_SUBDIR = ".cronos"
STATS_SUBDIR = "stats"


class StatsStore:
    """Persist per-task run statistics as JSON files.

    Stats are stored at:
        {spaces_dir}/{space_id}/.cronos/stats/{task_id}.json

    This directory is separate from .cronos/tasks/ so stats survive task
    deletion (which only moves the .md file to .trash/).
    """

    def __init__(self, spaces_dir: Path) -> None:
        self._spaces_dir = spaces_dir
        self._lock = asyncio.Lock()

    def _stats_path(self, space_id: str, task_id: str) -> Path:
        return (
            self._spaces_dir
            / space_id
            / CRONOS_SUBDIR
            / STATS_SUBDIR
            / f"{task_id}.json"
        )

    async def load(self, space_id: str, task_id: str) -> TaskStats | None:
        path = self._stats_path(space_id, task_id)
        if not path.exists():
            return None
        try:
            text = await asyncio.to_thread(path.read_text, encoding="utf-8")
            return TaskStats.model_validate_json(text)
        except Exception:
            log.exception("Failed to load stats for %s/%s", space_id, task_id)
            return None

    async def append_run(
        self,
        space_id: str,
        task_id: str,
        title: str,
        run: object,  # RunStats
    ) -> TaskStats:
        async with self._lock:
            path = self._stats_path(space_id, task_id)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing or start fresh
            existing: TaskStats | None = None
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8")
                    existing = TaskStats.model_validate_json(text)
                except Exception:
                    log.warning("Corrupted stats for %s/%s; resetting", space_id, task_id)

            if existing is None:
                existing = TaskStats(task_id=task_id, space_id=space_id, title=title)

            # Update title in case it changed
            existing = existing.model_copy(
                update={"title": title, "runs": existing.runs + [run]}
            )

            # Atomic write
            tmp = path.with_suffix(".tmp")
            try:
                tmp.write_text(
                    json.dumps(existing.to_file_dict(), indent=2),
                    encoding="utf-8",
                )
                os.replace(tmp, path)
            except Exception:
                log.exception("Failed to write stats for %s/%s", space_id, task_id)
                tmp.unlink(missing_ok=True)

            return existing

    async def list_space(self, space_id: str) -> list[TaskStats]:
        stats_dir = self._spaces_dir / space_id / CRONOS_SUBDIR / STATS_SUBDIR
        if not stats_dir.is_dir():
            return []
        results: list[TaskStats] = []
        for path in sorted(stats_dir.glob("*.json")):
            try:
                text = await asyncio.to_thread(path.read_text, encoding="utf-8")
                ts = TaskStats.model_validate_json(text)
                results.append(ts)
            except Exception:
                log.warning("Skipping unreadable stats file %s", path)
        return results

    async def list_all(self, space_ids: list[str]) -> list[TaskStats]:
        all_stats: list[TaskStats] = []
        for space_id in space_ids:
            space_stats = await self.list_space(space_id)
            all_stats.extend(space_stats)
        return all_stats
