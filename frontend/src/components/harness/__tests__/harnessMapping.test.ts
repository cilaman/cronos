import { describe, it, expect } from 'vitest';
import { toReactFlow, fromReactFlow } from '../harnessMapping';
import type { Harness } from '../../../types';

// ---------------------------------------------------------------------------
// Fixture — 3-node harness with dict ports and data field (new backend shape)
// ---------------------------------------------------------------------------

const fixture: Harness = {
  name: 'test-harness',
  nodes: [
    {
      id: 'n1',
      type: 'trigger',
      label: 'Start',
      position: { x: 0, y: 0 },
      ports: { out: {} },
      data: {},
    },
    {
      id: 'n2',
      type: 'agent',
      label: 'Run',
      position: { x: 200, y: 0 },
      ports: { in: {}, out: {} },
      data: { agent_ref: 'my-agent', prompt_template: 'hello' },
    },
    {
      id: 'n3',
      type: 'decision',
      label: 'Check',
      position: { x: 400, y: 0 },
      ports: { in: {}, yes: {}, no: {} },
      data: {},
    },
  ],
  edges: [
    {
      id: 'e1',
      source: { node_id: 'n1', port_id: 'out' },
      target: { node_id: 'n2', port_id: 'in' },
      condition: null,
    },
    {
      id: 'e2',
      source: { node_id: 'n2', port_id: 'out' },
      target: { node_id: 'n3', port_id: 'in' },
      condition: 'yes',
    },
  ],
  variables: { env: 'prod' },
  created_at: '2024-01-01T00:00:00Z',
  version: '1.0',
};

// ---------------------------------------------------------------------------
// toReactFlow
// ---------------------------------------------------------------------------

describe('toReactFlow', () => {
  it('produces RF nodes with ids matching backend node ids', () => {
    const { nodes } = toReactFlow(fixture);
    expect(nodes.map(n => n.id)).toEqual(['n1', 'n2', 'n3']);
  });

  it('produces RF edge source/target as flat node_id strings', () => {
    const { edges } = toReactFlow(fixture);
    expect(typeof edges[0].source).toBe('string');
    expect(typeof edges[0].target).toBe('string');
    expect(edges[0].source).toBe('n1');
    expect(edges[0].target).toBe('n2');
  });

  it('maps edge sourceHandle and targetHandle to port_id', () => {
    const { edges } = toReactFlow(fixture);
    expect(edges[0].sourceHandle).toBe('out');
    expect(edges[0].targetHandle).toBe('in');
    expect(edges[1].sourceHandle).toBe('out');
    expect(edges[1].targetHandle).toBe('in');
  });

  it('puts node.data fields directly into RF node.data (not under config)', () => {
    const { nodes } = toReactFlow(fixture);
    const agentNode = nodes.find(n => n.id === 'n2')!;
    expect((agentNode.data as Record<string, unknown>).agent_ref).toBe('my-agent');
    expect((agentNode.data as Record<string, unknown>).prompt_template).toBe('hello');
    // no config wrapper
    expect((agentNode.data as Record<string, unknown>).config).toBeUndefined();
  });

  it('stores edge condition in RF edge.data.condition', () => {
    const { edges } = toReactFlow(fixture);
    expect((edges[0].data as Record<string, unknown>).condition).toBeNull();
    expect((edges[1].data as Record<string, unknown>).condition).toBe('yes');
  });
});

// ---------------------------------------------------------------------------
// fromReactFlow — round-trip
// ---------------------------------------------------------------------------

describe('fromReactFlow round-trip', () => {
  it('preserves node ids, positions, types, and edge ids', () => {
    const { nodes: rfNodes, edges: rfEdges } = toReactFlow(fixture);
    const result = fromReactFlow(rfNodes, rfEdges, fixture);

    expect(result.nodes.map(n => n.id)).toEqual(['n1', 'n2', 'n3']);
    expect(result.nodes[0].position).toEqual({ x: 0, y: 0 });
    expect(result.nodes[1].position).toEqual({ x: 200, y: 0 });
    expect(result.nodes[0].type).toBe('trigger');
    expect(result.nodes[1].type).toBe('agent');
    expect(result.nodes[2].type).toBe('decision');
    expect(result.edges.map(e => e.id)).toEqual(['e1', 'e2']);
  });

  it('produces backend NodeRef shape for edge source/target', () => {
    const { nodes: rfNodes, edges: rfEdges } = toReactFlow(fixture);
    const result = fromReactFlow(rfNodes, rfEdges, fixture);

    expect(result.edges[0].source).toEqual({ node_id: 'n1', port_id: 'out' });
    expect(result.edges[0].target).toEqual({ node_id: 'n2', port_id: 'in' });
    expect(result.edges[1].source).toEqual({ node_id: 'n2', port_id: 'out' });
    expect(result.edges[1].target).toEqual({ node_id: 'n3', port_id: 'in' });
  });

  it('round-trips edge condition', () => {
    const { nodes: rfNodes, edges: rfEdges } = toReactFlow(fixture);
    const result = fromReactFlow(rfNodes, rfEdges, fixture);

    expect(result.edges[0].condition).toBeNull();
    expect(result.edges[1].condition).toBe('yes');
  });

  it('persists node.data fields (not as config)', () => {
    const { nodes: rfNodes, edges: rfEdges } = toReactFlow(fixture);
    const result = fromReactFlow(rfNodes, rfEdges, fixture);

    const n2 = result.nodes.find(n => n.id === 'n2')!;
    expect(n2.data.agent_ref).toBe('my-agent');
    expect(n2.data.prompt_template).toBe('hello');
    // no config key
    expect((n2 as unknown as Record<string, unknown>).config).toBeUndefined();
  });

  it('preserves ports as dict from original', () => {
    const { nodes: rfNodes, edges: rfEdges } = toReactFlow(fixture);
    const result = fromReactFlow(rfNodes, rfEdges, fixture);

    expect(result.nodes[0].ports).toEqual({ out: {} });
    expect(result.nodes[1].ports).toEqual({ in: {}, out: {} });
    expect(result.nodes[2].ports).toEqual({ in: {}, yes: {}, no: {} });
  });

  it('preserves created_at from original', () => {
    const { nodes: rfNodes, edges: rfEdges } = toReactFlow(fixture);
    const result = fromReactFlow(rfNodes, rfEdges, fixture);
    expect(result.created_at).toBe('2024-01-01T00:00:00Z');
  });

  it('preserves variables from original', () => {
    const { nodes: rfNodes, edges: rfEdges } = toReactFlow(fixture);
    const result = fromReactFlow(rfNodes, rfEdges, fixture);
    expect(result.variables).toEqual({ env: 'prod' });
  });
});

// ---------------------------------------------------------------------------
// fromReactFlow — default ports for new (palette-dropped) nodes
// ---------------------------------------------------------------------------

describe('fromReactFlow default ports for new nodes', () => {
  const emptyHarness: Harness = {
    name: 'empty',
    nodes: [],
    edges: [],
    variables: {},
  };

  function dropNode(type: string) {
    const rfNode = {
      id: `new-${type}`,
      type,
      position: { x: 0, y: 0 },
      data: { label: type },
    };
    return fromReactFlow([rfNode as any], [], emptyHarness).nodes[0];
  }

  it('agent → { in: {}, out: {} }', () => {
    expect(dropNode('agent').ports).toEqual({ in: {}, out: {} });
  });

  it('trigger → { out: {} }', () => {
    expect(dropNode('trigger').ports).toEqual({ out: {} });
  });

  it('decision → { in: {}, yes: {}, no: {} }', () => {
    expect(dropNode('decision').ports).toEqual({ in: {}, yes: {}, no: {} });
  });

  it('wait → { in: {}, out: {} }', () => {
    expect(dropNode('wait').ports).toEqual({ in: {}, out: {} });
  });

  it('aggregator → { in-0: {}, in-1: {}, out: {} }', () => {
    expect(dropNode('aggregator').ports).toEqual({ 'in-0': {}, 'in-1': {}, out: {} });
  });
});
