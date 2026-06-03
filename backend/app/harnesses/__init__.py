"""
backend/app/harnesses — Harness data-layer package.

Re-exports the public surface used by upper layers (API router, store, validator)
so callers can do::

    from app.harnesses import Harness, HarnessNode, HarnessEdge, NodeType
    from app.harnesses import HarnessStore, HarnessNotFound, HarnessNameConflict
    from app.harnesses import HarnessGraphError, validate_graph
"""

from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)
from app.harnesses.store import HarnessNameConflict, HarnessNotFound, HarnessStore
from app.harnesses.validator import HarnessGraphError, validate_graph

__all__ = [
    "Harness",
    "HarnessEdge",
    "HarnessNode",
    "NodeRef",
    "NodeType",
    "Position",
    "HarnessStore",
    "HarnessNotFound",
    "HarnessNameConflict",
    "HarnessGraphError",
    "validate_graph",
]
