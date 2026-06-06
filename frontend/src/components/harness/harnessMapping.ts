import type { Node as RFNode, Edge as RFEdge } from '@xyflow/react';
import type { Harness, HarnessNode, HarnessEdge } from '../../types';

/** Default ports per node type — must match the Handle id attributes rendered by each node component. */
function defaultPorts(nodeType: string): Record<string, Record<string, unknown>> {
  switch (nodeType) {
    case 'agent':       return { in: {}, out: {} };
    case 'trigger':     return { out: {} };
    case 'decision':    return { in: {}, yes: {}, no: {} };
    case 'wait':        return { in: {}, out: {} };
    case 'aggregator':  return { 'in-0': {}, 'in-1': {}, out: {} };
    default:            return {};
  }
}

/** Convert backend Harness → React Flow nodes/edges. */
export function toReactFlow(harness: Harness): { nodes: RFNode[]; edges: RFEdge[] } {
  const nodes: RFNode[] = harness.nodes.map(n => ({
    id: n.id,
    type: n.type,
    position: n.position,
    // Spread node.data directly so all backend fields are available in React Flow node data.
    data: { label: n.label, ...n.data },
  }));

  const edges: RFEdge[] = harness.edges.map(e => ({
    id: e.id,
    source: e.source.node_id,
    target: e.target.node_id,
    sourceHandle: e.source.port_id,
    targetHandle: e.target.port_id,
    // Carry condition so it survives a round-trip without a backend fetch.
    data: { condition: e.condition ?? null },
  }));

  return { nodes, edges };
}

/** Convert React Flow nodes/edges → backend Harness (preserving created_at, version, variables). */
export function fromReactFlow(
  rfNodes: RFNode[],
  rfEdges: RFEdge[],
  original: Harness,
): Harness {
  const originalNodeMap = new Map(original.nodes.map(n => [n.id, n]));

  const nodes: HarnessNode[] = rfNodes.map(n => {
    const orig = originalNodeMap.get(n.id);
    // Strip display-only label from data; everything else persists to node.data.
    const { label, ...data } = n.data as Record<string, unknown>;
    return {
      id: n.id,
      type: n.type as HarnessNode['type'],
      label: (label as string) ?? n.id,
      position: n.position,
      // Preserve existing ports; assign type-specific defaults for newly-dropped nodes.
      ports: orig?.ports ?? defaultPorts(n.type ?? ''),
      data: data,
    };
  });

  const edges: HarnessEdge[] = rfEdges.map(e => {
    const edgeData = e.data as Record<string, unknown> | undefined;
    const condition = edgeData?.condition;
    return {
      id: e.id,
      source: { node_id: e.source, port_id: e.sourceHandle ?? '' },
      target: { node_id: e.target, port_id: e.targetHandle ?? '' },
      condition: typeof condition === 'string' ? condition : null,
    };
  });

  return {
    ...original,
    nodes,
    edges,
    created_at: original.created_at,
    version: original.version,
    variables: original.variables,
  };
}
