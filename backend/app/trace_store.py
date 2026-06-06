from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path

from .trace_parser import RunTrace
from .trace_redact import redact_trace_dict

log = logging.getLogger("cronos.trace_store")

CRONOS_SUBDIR = ".cronos"
TRACES_SUBDIR = "traces"


class TraceStore:
    """Persist per-run traces as individual JSON files.

    Traces are stored at:
        {spaces_dir}/{space_id}/.cronos/traces/{task_id}/{run_index:04d}.json

    Unlike stats, traces live WITH the task and are deleted when the task is
    deleted. One file per run; no accumulation.
    """

    def __init__(self, spaces_dir: Path) -> None:
        self._spaces_dir = spaces_dir
        self._lock = asyncio.Lock()

    def _trace_dir(self, space_id: str, task_id: str) -> Path:
        return (
            self._spaces_dir
            / space_id
            / CRONOS_SUBDIR
            / TRACES_SUBDIR
            / task_id
        )

    def _trace_path(self, space_id: str, task_id: str, run_index: int) -> Path:
        return self._trace_dir(space_id, task_id) / f"{run_index:04d}.json"

    async def save_run(self, space_id: str, task_id: str, trace: RunTrace) -> None:
        async with self._lock:
            path = self._trace_path(space_id, task_id, trace.run_index)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            try:
                clean = redact_trace_dict(trace.model_dump(mode="json"))
                tmp.write_text(
                    json.dumps(clean, indent=2),
                    encoding="utf-8",
                )
                os.replace(tmp, path)
            except Exception:
                log.exception("Failed to write trace for %s/%s run %d", space_id, task_id, trace.run_index)
                tmp.unlink(missing_ok=True)

    async def load_run(self, space_id: str, task_id: str, run_index: int) -> RunTrace | None:
        path = self._trace_path(space_id, task_id, run_index)
        if not path.exists():
            return None
        try:
            text = await asyncio.to_thread(path.read_text, encoding="utf-8")
            return RunTrace.model_validate_json(text)
        except Exception:
            log.exception("Failed to load trace %s/%s/%04d", space_id, task_id, run_index)
            return None

    async def load_latest(self, space_id: str, task_id: str) -> RunTrace | None:
        trace_dir = self._trace_dir(space_id, task_id)
        if not trace_dir.is_dir():
            return None
        files = sorted(trace_dir.glob("*.json"))
        if not files:
            return None
        latest = files[-1]
        try:
            text = await asyncio.to_thread(latest.read_text, encoding="utf-8")
            return RunTrace.model_validate_json(text)
        except Exception:
            log.exception("Failed to load latest trace for %s/%s", space_id, task_id)
            return None

    async def list_runs(self, space_id: str, task_id: str) -> list[RunTrace]:
        trace_dir = self._trace_dir(space_id, task_id)
        if not trace_dir.is_dir():
            return []
        results: list[RunTrace] = []
        for path in sorted(trace_dir.glob("*.json")):
            try:
                text = await asyncio.to_thread(path.read_text, encoding="utf-8")
                results.append(RunTrace.model_validate_json(text))
            except Exception:
                log.warning("Skipping unreadable trace file %s", path)
        return results

    async def count_runs(self, space_id: str, task_id: str) -> int:
        trace_dir = self._trace_dir(space_id, task_id)
        if not trace_dir.is_dir():
            return 0
        return len(list(trace_dir.glob("*.json")))

    async def delete_task_traces(self, space_id: str, task_id: str) -> None:
        trace_dir = self._trace_dir(space_id, task_id)
        await asyncio.to_thread(shutil.rmtree, trace_dir, True)
