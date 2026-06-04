import { describe, it, expect } from 'vitest';
import { toReactFlow, fromReactFlow } from '../harnessMapping';
import type { Harness } from '../../../types';

// 3-node fixture matching the design's R15 scenario:
// Trigger → Agent → Decision
const fixture: Harness = {
  name: 'test-harness',
  nodes: [
    {
      id: 'n1',
      type: 'trigger',
      label: 'Start',
      position: { x: 0, y: 0 },
      ports: [{ id: 'out', label: 'Out', port_type: 'output' }],
      config: {},
    },
    {
      id: 'n2',
      type: 'agent',
      label: 'Run',
      position: { x: 200, y: 0 },
      ports: [
        { id: 'in', label: 'In', port_type: 'input' },
        { id: 'out', label: 'Out', port_type: 'output' },
      ],
      config: { agent_ref: 'my-agent', prompt: 'hello' },
    },
    {
      id: 'n3',
      type: 'decision',
      label: 'Check',
      position: { x: 400, y: 0 },
      ports: [{ id: 'in', label: 'In', port_type: 'input' }],
      config: {},
    },
  ],
  edges: [
    { id: 'e1', source: { node_id: 'n1', port_id: 'out' }, target: { node_id: 'n2', port_id: 'in' } },
    { id: 'e2', source: { node_id: 'n2', port_id: 'out' }, target: { node_id: 'n3', port_id: 'in' } },
  ],
  variables: { env: 'prod' },
  created_at: '2024-01-01T00:00:00Z',
  version: 1,
};

describe('toReactFlow', () => {
  it('produces RF nodes with ids matching backend node ids', () => {
    const { nodes } = toReactFlow(fixture);
    expect(nodes.map(n => n.id)).toEqual(['n1', 'n2', 'n3']);
  });

  it('produces RF edge source/target as flat node_id strings (not NodeRef objects)', () => {
    const { edges } = toReactFlow(fixture);
    expect(typeof edges[0].source).toBe('string');
    expect(typeof edges[0].target).toBe('string');
    expect(edges[0].source).toBe('n1');
    expect(edges[0].target).toBe('n2');
  });

  it('maps edge sourceHandle to source.port_id', () => {
    const { edges } = toReactFlow(fixture);
    expect(edges[0].sourceHandle).toBe('out');
    expect(edges[0].targetHandle).toBe('in');
    expect(edges[1].sourceHandle).toBe('out');
    expect(edges[1].targetHandle).toBe('in');
  });

  it('React Flow edge source is a node_id string (different from backend NodeRef shape)', () => {
    const { edges } = toReactFlow(fixture);
    // Backend NodeRef would be { node_id: 'n1', port_id: 'out' }
    // RF edge source must be just the string 'n1'
    expect(edges[0].source).toBe('n1');
    expect(typeof edges[0].source).toBe('string');
    // It should NOT be an object
    expect(typeof edges[0].source).not.toBe('object');
  });
});

describe('fromReactFlow', () => {
  it('round-trip: same node ids, positions, types, and edge ids with correct nested NodeRef shape', () => {
    const { nodes: rfNodes, edges: rfEdges } = toReactFlow(fixture);
    const result = fromReactFlow(rfNodes, rfEdges, fixture);

    // Same node ids
    expect(result.nodes.map(n => n.id)).toEqual(['n1', 'n2', 'n3']);
    // Same positions
    expect(result.nodes[0].position).toEqual({ x: 0, y: 0 });
    expect(result.nodes[1].position).toEqual({ x: 200, y: 0 });
    // Same types
    expect(result.nodes[0].type).toBe('trigger');
    expect(result.nodes[1].type).toBe('agent');
    expect(result.nodes[2].type).toBe('decision');
    // Same edge ids
    expect(result.edges.map(e => e.id)).toEqual(['e1', 'e2']);
    // Edges have correct nested NodeRef shape
    expect(result.edges[0].source).toEqual({ node_id: 'n1', port_id: 'out' });
    expect(result.edges[0].target).toEqual({ node_id: 'n2', port_id: 'in' });
    expect(result.edges[1].source).toEqual({ node_id: 'n2', port_id: 'out' });
    expect(result.edges[1].target).toEqual({ node_id: 'n3', port_id: 'in' });
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
