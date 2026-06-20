"""Push notification on terminal / needs-human state transitions.

Reads CRONOS_NOTIFY_URL from the environment. If the env var is unset or empty,
all calls are silent no-ops. Posts a JSON payload to the configured URL using
httpx with a 5-second timeout (connect + read). Any exception is caught and
logged at WARNING level so a failed POST never propagates to callers.

Design constraints:
- Must be fire-and-forget (callers use asyncio.create_task).
- Must never raise — broad except → WARNING log.
- Must use httpx.AsyncClient (already a backend dep, no new import needed).
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("cronos.notifier")

_NOTIFY_URL_ENV = "CRONOS_NOTIFY_URL"


async def notify_state_change(
    task_id: str,
    task_title: str,
    status: str,
    exit_reason: str | None,
    summary: str | None,
) -> None:
    """POST a JSON notification to CRONOS_NOTIFY_URL.

    Silent no-op when CRONOS_NOTIFY_URL is unset or empty.
    Never raises — all exceptions are logged at WARNING level.

    Payload schema (analyst R6 acceptance criterion):
    {
        "task_id": str,
        "task_title": str,
        "status": str,        # e.g. "waiting", "done"
        "exit_reason": str | null,
        "summary": str | null
    }
    """
    url = os.environ.get(_NOTIFY_URL_ENV, "").strip()
    if not url:
        return

    payload = {
        "task_id": task_id,
        "task_title": task_title,
        "status": status,
        "exit_reason": exit_reason,
        "summary": summary,
    }
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            log.info(
                "Notification sent: task=%s status=%s http=%d",
                task_id, status, resp.status_code,
            )
    except Exception:
        log.warning(
            "notify_state_change failed for task %s (url=%r); continuing",
            task_id, url,
            exc_info=True,
        )
