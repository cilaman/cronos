"""
Unified status-envelope parser.

Delivery/harness agents emit a fenced structured-return block. As of the
``node_status`` generalization the agents emit ``node_status``; older CC-v1
reports emit ``delivery_status``. Consumers must accept both so an adapter can
read whichever fence an agent produced. This is the single seam both adapters
route through so their parsing cannot drift.

Both underlying block types expose the same read surface used by callers:
``status``, ``artifact_paths``, ``produces``, ``fields``, ``open_questions``.
"""

from __future__ import annotations

from lib.delivery_status import DeliveryStatusBlock, parse_delivery_status
from lib.node_status import NodeStatusBlock, parse_node_status


def parse_status_envelope(
    text: str,
) -> NodeStatusBlock | DeliveryStatusBlock | None:
    """Return the first status envelope in *text*, or ``None``.

    Tries ``node_status`` (preferred) first, then ``delivery_status`` (legacy).
    """
    return parse_node_status(text) or parse_delivery_status(text)
