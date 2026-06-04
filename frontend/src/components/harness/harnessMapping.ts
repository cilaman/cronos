import type { Node as RFNode, Edge as RFEdge } from '@xyflow/react';
import type { Harness, HarnessNode, HarnessEdge } from '../../types';

// Convert backend Harness → React Flow nodes/edges
export function toReactFlow(harness: Harness): { nodes: RFNode[]; edges: RFEdge[] } {
  const nodes: RFNode[] = harness.nodes.map(n => ({
    id: n.id,
    type: n.type,
    position: n.position,
    data: { label: n.label, ...n.config, _ports: n.ports },
  }));
  const edges: RFEdge[] = harness.edges.map(e => ({
    id: e.id,
    source: e.source.node_id,
    target: e.target.node_id,
    sourceHandle: e.source.port_id,
    targetHandle: e.target.port_id,
    label: e.label,
  }));
  return { nodes, edges };
}

// Convert React Flow nodes/edges → backend Harness (preserving created_at, version, variables)
export function fromReactFlow(
  rfNodes: RFNode[],
  rfEdges: RFEdge[],
  original: Harness,
): Harness {
  // Build a lookup from original nodes to preserve ports
  const originalNodeMap = new Map(original.nodes.map(n => [n.id, n]));

  const nodes: HarnessNode[] = rfNodes.map(n => {
    const orig = originalNodeMap.get(n.id);
    const { label, _ports, ...config } = n.data as Record<string, unknown>;
    return {
      id: n.id,
      type: n.type as HarnessNode['type'],
      label: (label as string) ?? n.id,
      position: n.position,
      ports: orig?.ports ?? [],
      config: config,
    };
  });

  const edges: HarnessEdge[] = rfEdges.map(e => ({
    id: e.id,
    source: { node_id: e.source, port_id: e.sourceHandle ?? '' },
    target: { node_id: e.target, port_id: e.targetHandle ?? '' },
    label: e.label as string | undefined,
  }));

  return {
    ...original,
    nodes,
    edges,
    // Preserve these fields from original
    created_at: original.created_at,
    version: original.version,
    variables: original.variables,
  };
}
