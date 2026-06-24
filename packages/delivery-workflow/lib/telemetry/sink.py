from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.state.store import StateStore


class BudgetExceededSignal(Exception):
    """Raised by TelemetrySink.emit() when cumulative usd_spent exceeds usd_ceiling."""

    def __init__(self, usd_spent: float, usd_ceiling: float) -> None:
        super().__init__(
            f"Budget exceeded: spent ${usd_spent:.4f}, ceiling ${usd_ceiling:.4f}"
        )
        self.usd_spent = usd_spent
        self.usd_ceiling = usd_ceiling


class TelemetrySink:
    """Portable telemetry accumulator satisfying TelemetryOps Protocol — R12/R13.

    Args:
        usd_ceiling: Budget ceiling in USD. 0.0 (default) means no ceiling enforced.
        state_store: Optional StateStore; when provided, emit() persists per-node
            telemetry and cumulative usd_spent into state.json atomically.
    """

    def __init__(
        self,
        *,
        usd_ceiling: float = 0.0,
        state_store: StateStore | None = None,
    ) -> None:
        self._usd_ceiling = usd_ceiling
        self._usd_spent: float = 0.0
        self._node_data: dict[str, dict[str, float]] = {}
        self._store = state_store

    @property
    def usd_spent(self) -> float:
        """Cumulative USD spent across all emitted nodes."""
        return self._usd_spent

    def emit(self, node_id: str, data: dict[str, float]) -> None:
        """Record telemetry for node_id and accumulate usd_spent.

        Persists to state.json when a StateStore is configured.
        Raises BudgetExceededSignal after accumulation if ceiling is breached.
        """
        self._node_data[node_id] = dict(data)
        self._usd_spent += data.get("usd", 0.0)

        if self._store is not None:
            self._persist(node_id, data)

        if self._usd_ceiling > 0.0 and self._usd_spent > self._usd_ceiling:
            raise BudgetExceededSignal(self._usd_spent, self._usd_ceiling)

    def node_data(self, node_id: str) -> dict[str, float] | None:
        """Return a copy of the most recent telemetry dict emitted for node_id, or None."""
        data = self._node_data.get(node_id)
        return dict(data) if data is not None else None

    def _persist(self, node_id: str, data: dict[str, float]) -> None:
        assert self._store is not None
        state = self._store.read()
        if node_id in state.nodes:
            state.nodes[node_id].telemetry = dict(data)
        state.budget.usd_spent = self._usd_spent
        self._store.write(state)
