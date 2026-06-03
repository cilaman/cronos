"""
backend/app/harnesses/run_state — RunState + NodeState dataclasses and atomic persistence.

Persistence contract
--------------------
save_atomic(path, state) writes the serialized RunState to a temporary file in the
same directory as `path` and then atomically replaces it via os.replace().  This
guarantees that a reader never sees a partially-written file.

Crash-safety / resume note
---------------------------
If the process is killed between the tmpfile write and the os.replace() call, the
original file at `path` is intact and the partial tmpfile is left as a stale orphan.
On the next startup the tmpfile is ignored (load() only reads `path`).

The load() function does NOT automatically convert ``in_progress`` nodes to
``pending``.  The caller (HarnessExecutor) is responsible for reconciliation:

  * For each node found in ``RunState.nodes_executed`` with
    ``status == 'in_progress'``, the executor should query the TaskStore for
    ``NodeState.child_task_id``.  If the child task exists and is DONE, mark
    the node done; otherwise re-execute from scratch (treat as pending).

Valid status values: 'pending' | 'in_progress' | 'done' | 'failed' | 'skipped'

Control-flow node status semantics
------------------------------------
``in_progress`` is the canonical status for control-flow nodes (Decision, Wait,
Aggregator) while they are actively evaluating.  It is set by the executor before
invoking the evaluator and cleared to 'done' or 'failed' on completion.  For human
Wait nodes specifically, the node remains ``in_progress`` for the entire period the
harness run goal is parked in TaskState.WAITING — the executor resumes traversal
from the Wait node's outgoing edges once the reply arrives.

Wait-human resume routing
--------------------------
``RunState.waiting_node_id`` is the **single** source of truth for human Wait resume
routing.  When the executor parks a harness run in TaskState.WAITING it sets
``waiting_node_id`` to the Wait node's id and persists the RunState.  On resume,
the executor reads ``waiting_node_id`` to know which node's outgoing edges to
traverse next.  **No other component may duplicate this routing logic.**  The worker
(I7) re-enters ``executor.execute()`` unchanged; the executor consults
``waiting_node_id`` internally.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class NodeState:
    """Execution state for a single harness node."""

    status: str  # 'pending' | 'in_progress' | 'done' | 'failed' | 'skipped'
    child_task_id: str | None = None
    output: str | None = None
    reason: str | None = None  # populated for 'skipped' and 'failed' nodes


@dataclass
class RunState:
    """Snapshot of a harness run's execution progress."""

    run_id: str
    harness_id: str
    goal_task_id: str
    nodes_executed: dict[str, NodeState] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Wait-human resume routing
    # ------------------------------------------------------------------

    waiting_node_id: str | None = None
    """
    The id of the Wait(human) node that is currently blocking this run, or None
    if the run is not parked at a human Wait.

    This is the **single** source of truth for Wait-human resume routing:
    - Set by the executor (I6) when entering a human Wait node and the run
      goal is transitioned to TaskState.WAITING.
    - Cleared (set back to None) by the executor when traversal resumes from
      the Wait node's outgoing edges.
    - Read by the executor on re-entry to determine where to resume.
    - Must NOT be set or read by the worker (I7) — the worker calls
      executor.execute() unchanged and the executor handles routing internally.
    """

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a plain dict suitable for JSON serialisation."""
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RunState":
        """Reconstruct a RunState from the plain dict produced by to_dict()."""
        nodes_raw: dict = data.get("nodes_executed", {})
        nodes: dict[str, NodeState] = {
            node_id: NodeState(
                status=ns["status"],
                child_task_id=ns.get("child_task_id"),
                output=ns.get("output"),
                reason=ns.get("reason"),
            )
            for node_id, ns in nodes_raw.items()
        }
        return cls(
            run_id=data["run_id"],
            harness_id=data["harness_id"],
            goal_task_id=data["goal_task_id"],
            nodes_executed=nodes,
            waiting_node_id=data.get("waiting_node_id"),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load(path: "str | Path") -> RunState | None:
    """
    Load a RunState from a JSON file.

    Returns None if the file does not exist.
    Raises ValueError if the file exists but cannot be parsed.

    NOTE: ``in_progress`` nodes are returned as-is.  The caller is responsible
    for reconciling them against the live TaskStore before resuming execution.
    """
    p = Path(path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return RunState.from_dict(data)


def save_atomic(path: "str | Path", state: RunState) -> None:
    """
    Atomically write *state* to *path* as JSON.

    Uses a sibling temporary file + os.replace() so readers always see a
    complete file — even if the process is killed mid-write.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(state.to_dict(), indent=2, ensure_ascii=False)

    # Write to a temp file in the same directory so os.replace() is atomic
    # (same filesystem, single rename syscall).
    fd, tmp_path = tempfile.mkstemp(dir=p.parent, prefix=".run_state_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_path, p)
    except Exception:
        # Clean up orphan tmpfile on unexpected failure.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
