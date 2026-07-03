"""
packages/delivery-workflow/compiler_a.py — Compiler A: spec dict → IRGraph.

Takes a validated delivery/v1 spec dict (from spec_loader.load_spec) and
produces an IRGraph.  Sync, no I/O, no app.* imports.

Responsibilities
----------------
1. Resolve ``model: {use: alias}`` against ``defaults.models``; raise a
   descriptive ValueError listing all undefined aliases up-front.
2. Fold ``defaults.budget`` into ``IRGraph.metadata['budget']``.
3. Emit one IRNode per spec node with ``data`` containing the raw node config
   (minus the id/kind fields which are promoted to the dataclass).
4. Parse ``loop:`` stanzas into LoopPolicy instances.
5. Emit one IREdge per spec edge.
6. Bare-string ``model: 'opus'`` (no ``{use: ...}``) passes through verbatim.
7. Validate ``on_reject:`` routes on human nodes (OD-1/R7): the target must be
   a declared node id AND a forward-ancestor of the sign-off (its re-run path
   must reach the sign-off again so the rejection re-parks instead of silently
   routing the approve path); raise a descriptive ValueError listing all
   offenders.
   The route itself stays in ``IRNode.data['on_reject']`` (node-data, not an
   IREdge): its typical target is UPSTREAM of the sign-off, and back-edges are
   deliberately outside the runner's live edge evaluation for un-dispatched
   nodes — ``runner/resume.py`` performs the reject re-arm directly (the R8
   reset path), so a synthesized edge would be dead weight the seeding had to
   special-case.
"""
from __future__ import annotations

from typing import Any

from ir import IREdge, IRGraph, IRNode, LoopPolicy


def compile(spec: dict[str, Any]) -> IRGraph:  # noqa: A001
    """Compile a validated spec dict to an IRGraph.

    Parameters
    ----------
    spec:
        A delivery/v1 spec dict already validated by spec_loader.load_spec or
        spec_loader.loads_spec.  Must contain ``nodes`` and ``edges`` lists.

    Returns
    -------
    IRGraph
        Fully resolved IR ready for the runner.

    Raises
    ------
    ValueError
        If any ``model: {use: alias}`` reference cannot be resolved against
        ``defaults.models`` (the message lists all (node_id, alias) pairs), or
        if any human node's ``on_reject`` names an undeclared node or a node
        that is not a forward-ancestor of the sign-off (the message lists all
        (node_id, target) pairs).
    """
    defaults: dict[str, Any] = spec.get("defaults", {})
    models_map: dict[str, str] = defaults.get("models", {})
    budget: dict[str, Any] = dict(defaults.get("budget", {}))

    metadata: dict[str, Any] = dict(spec.get("metadata", {}))
    if budget:
        metadata["budget"] = budget

    variables: dict[str, Any] = dict(spec.get("variables", {}))

    spec_nodes: list[dict[str, Any]] = spec.get("nodes", [])
    spec_edges: list[dict[str, Any]] = spec.get("edges", [])

    # -----------------------------------------------------------------------
    # First pass: collect all undefined aliases so we can raise once.
    # -----------------------------------------------------------------------
    undefined: list[tuple[str, str]] = []
    for raw_node in spec_nodes:
        node_id: str = raw_node.get("id", "<unknown>")
        raw_model = raw_node.get("model")
        alias = _extract_alias(raw_model)
        if alias is not None and alias not in models_map:
            undefined.append((node_id, alias))

    if undefined:
        pairs = ", ".join(f"({nid!r}, {alias!r})" for nid, alias in undefined)
        raise ValueError(
            f"Compiler A: undefined model aliases in spec — {pairs}. "
            f"Available aliases: {list(models_map.keys())}"
        )

    # OD-1 (R7): every on_reject route must name a declared node — a typo here
    # would otherwise surface only at reject-resume time as a ResumeError.
    declared_ids = {raw_node.get("id") for raw_node in spec_nodes}
    bad_reject_routes = [
        (raw_node.get("id", "<unknown>"), raw_node["on_reject"])
        for raw_node in spec_nodes
        if raw_node.get("on_reject") is not None
        and raw_node["on_reject"] not in declared_ids
    ]
    if bad_reject_routes:
        pairs = ", ".join(f"({nid!r}, {tgt!r})" for nid, tgt in bad_reject_routes)
        raise ValueError(
            f"Compiler A: on_reject routes name undeclared nodes — {pairs}."
        )

    # OD-1 (R7) route SHAPE: the on_reject target must be a forward-ancestor
    # of its sign-off — the reject re-arm resets the target's downstream and
    # relies on the re-run flow reaching the sign-off again (back-edge
    # re-park).  A self/downstream/sibling target never leads back through the
    # sign-off, so a rejection would silently starve (or route) the approve
    # path instead of re-asking (D10).  Reachability uses the runner's
    # positional forward-edge rule (source declared before target).
    node_index = {raw_node.get("id"): i for i, raw_node in enumerate(spec_nodes)}
    forward_adjacency: dict[str, list[str]] = {}
    for raw_edge in spec_edges:
        src = raw_edge.get("from", raw_edge.get("source", ""))
        tgt = raw_edge.get("to", raw_edge.get("target", ""))
        if (
            src in node_index
            and tgt in node_index
            and node_index[src] < node_index[tgt]
        ):
            forward_adjacency.setdefault(src, []).append(tgt)

    def _forward_reaches(start: str, goal: str) -> bool:
        seen: set[str] = set()
        stack = list(forward_adjacency.get(start, ()))
        while stack:
            nid = stack.pop()
            if nid == goal:
                return True
            if nid in seen:
                continue
            seen.add(nid)
            stack.extend(forward_adjacency.get(nid, ()))
        return False

    non_dominating: list[tuple[str, str]] = []
    for raw_node in spec_nodes:
        target = raw_node.get("on_reject")
        if target is None:
            continue
        node_id = raw_node.get("id", "<unknown>")
        if target == node_id or not _forward_reaches(target, node_id):
            non_dominating.append((node_id, target))
    if non_dominating:
        pairs = ", ".join(f"({nid!r}, {tgt!r})" for nid, tgt in non_dominating)
        raise ValueError(
            f"Compiler A: on_reject routes do not lead back to their sign-off "
            f"— {pairs}. The target must be a forward-ancestor of the node "
            "(the re-run path must reach the sign-off again so it re-parks); "
            "a self/downstream/sibling target would let a rejection silently "
            "route or starve the approve path."
        )

    # -----------------------------------------------------------------------
    # Second pass: build IRNode list.
    # -----------------------------------------------------------------------
    ir_nodes: list[IRNode] = []
    for raw_node in spec_nodes:
        node_id = raw_node["id"]
        kind = raw_node["kind"]

        # Build the data dict: everything except id/kind (which are promoted).
        data: dict[str, Any] = {
            k: v for k, v in raw_node.items() if k not in ("id", "kind")
        }

        # Resolve model alias if present.
        raw_model = data.get("model")
        alias = _extract_alias(raw_model)
        if alias is not None:
            data["model"] = models_map[alias]
        # Bare-string model (already a string) passes through as-is.

        # Parse loop policy.
        loop: LoopPolicy | None = None
        raw_loop = data.pop("loop", None)
        if raw_loop is not None:
            loop = _parse_loop(raw_loop)

        ir_nodes.append(IRNode(id=node_id, kind=kind, data=data, loop=loop))

    # -----------------------------------------------------------------------
    # Third pass: build IREdge list.
    # -----------------------------------------------------------------------
    ir_edges: list[IREdge] = []
    for raw_edge in spec_edges:
        source: str = raw_edge.get("from", raw_edge.get("source", ""))
        target: str = raw_edge.get("to", raw_edge.get("target", ""))
        when: str = raw_edge.get("when", "")
        port: str | None = raw_edge.get("port")
        ir_edges.append(IREdge(source=source, target=target, when=when, port=port))

    return IRGraph(
        nodes=ir_nodes,
        edges=ir_edges,
        variables=variables,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_alias(raw_model: Any) -> str | None:
    """Return the alias string from ``{use: alias}`` syntax, or None.

    A bare string (e.g. ``"opus"``) returns None — it passes through verbatim.
    A dict with a ``use`` key returns the alias string.
    Anything else returns None.
    """
    if isinstance(raw_model, dict):
        return raw_model.get("use")
    return None


def _parse_loop(raw: dict[str, Any]) -> LoopPolicy:
    """Parse a raw loop stanza dict into a LoopPolicy instance."""
    return LoopPolicy(
        until=raw.get("until", ""),
        stall=list(raw.get("stall", [])),
        max=int(raw.get("max", 5)),
        on_exhaust=raw.get("on_exhaust", "escalate"),
    )
