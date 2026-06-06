/**
 * HarnessEditor acceptance tests — R15 scenario
 *
 * Higher-level integration tests covering:
 *   - Full save/load round-trip with 3-node fixture harness
 *   - Agent node config editing via VariableInspector
 *   - Drag-drop creates a node on canvas
 *   - 422 error surfaces in the UI via save-error banner
 *   - harness-canvas wrapper class present
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { Harness } from '../../types';

// ---------------------------------------------------------------------------
// Mock @xyflow/react — hoisted before imports of module under test
// ---------------------------------------------------------------------------

vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ onNodeClick, onDragOver, onDrop, children }: any) => (
    <div
      data-testid="react-flow"
      onDragOver={onDragOver}
      onDrop={onDrop}
      onClick={(e) => {
        const target = e.target as HTMLElement;
        const nodeId = target.dataset.nodeid;
        if (nodeId && onNodeClick) {
          onNodeClick(e, { id: nodeId });
        }
      }}
    >
      {children}
    </div>
  ),
  ReactFlowProvider: ({ children }: any) => <>{children}</>,
  useNodesState: (init: any[]) => {
    const [nodes, setNodes] = React.useState(init);
    const onNodesChange = vi.fn();
    return [nodes, setNodes, onNodesChange];
  },
  useEdgesState: (init: any[]) => {
    const [edges, setEdges] = React.useState(init);
    const onEdgesChange = vi.fn();
    return [edges, setEdges, onEdgesChange];
  },
  useReactFlow: () => ({ screenToFlowPosition: (p: any) => p }),
  addEdge: vi.fn((c: any, eds: any[]) => [...eds, c]),
  Handle: ({ type }: any) => <div data-testid={`handle-${type}`} />,
  Position: { Top: 'top', Bottom: 'bottom' },
}));

// ---------------------------------------------------------------------------
// Mock CSS imports
// ---------------------------------------------------------------------------

vi.mock('@xyflow/react/dist/style.css', () => ({}));
vi.mock('../../components/harness/reactflow-overrides.css', () => ({}));

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

const mockMutate = vi.fn();
const mockSaveMutation = {
  mutate: mockMutate,
  isPending: false,
  isError: false,
};

vi.mock('../../hooks/useHarnesses', () => ({
  useHarness: vi.fn(),
  useSaveHarness: vi.fn(() => mockSaveMutation),
}));

// ---------------------------------------------------------------------------
// Mock sub-components
// ---------------------------------------------------------------------------

vi.mock('../../components/harness/NodePalette', () => ({
  NodePalette: () => <div data-testid="node-palette" />,
}));

// VariableInspector mock captures onNodeChange for agent-config tests
let capturedOnNodeChange: ((nodeId: string, config: Record<string, unknown>) => void) | null = null;

vi.mock('../../components/harness/VariableInspector', () => ({
  VariableInspector: ({ selectedNode, onNodeChange }: any) => {
    capturedOnNodeChange = onNodeChange;
    if (selectedNode && selectedNode.type === 'agent') {
      return (
        <div data-testid="variable-inspector">
          <input aria-label="agent_ref" defaultValue={selectedNode.data.agent_ref ?? ''} />
          <textarea aria-label="prompt_template" defaultValue={selectedNode.data.prompt_template ?? ''} />
        </div>
      );
    }
    return <div data-testid="variable-inspector">no-agent-selected</div>;
  },
}));

vi.mock('../../components/harness/nodeTypes', () => ({
  nodeTypes: {},
}));

// ---------------------------------------------------------------------------
// Import under test AFTER mocks
// ---------------------------------------------------------------------------

import { HarnessEditor } from '../HarnessEditor';
import { useHarness } from '../../hooks/useHarnesses';

// ---------------------------------------------------------------------------
// R15 acceptance fixture — 3-node harness with 2 edges
// ---------------------------------------------------------------------------

const fixture: Harness = {
  name: 'my-harness',
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
    { id: 'e1', source: { node_id: 'n1', port_id: 'out' }, target: { node_id: 'n2', port_id: 'in' } },
    { id: 'e2', source: { node_id: 'n2', port_id: 'out' }, target: { node_id: 'n3', port_id: 'in' } },
  ],
  variables: {},
  created_at: '2024-01-01T00:00:00Z',
  version: '1.0',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderEditor(path = '/spaces/test-space/harnesses/my-harness/edit') {
  const client = makeClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/spaces/:spaceId/harnesses/:name/edit" element={<HarnessEditor />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// R15 acceptance scenarios
// ---------------------------------------------------------------------------

describe('HarnessEditor acceptance (R15)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedOnNodeChange = null;
    mockSaveMutation.mutate = mockMutate;
    mockSaveMutation.isPending = false;
    mockSaveMutation.isError = false;
  });

  // -------------------------------------------------------------------------
  // 1. Full save/load round-trip
  // -------------------------------------------------------------------------

  it('full save/load round-trip: 3-node harness loads, save preserves created_at and node ids', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: fixture,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    // Canvas renders
    expect(screen.getByTestId('react-flow')).toBeInTheDocument();

    // Click Save
    const saveButton = screen.getByTestId('save-button');
    await act(async () => {
      fireEvent.click(saveButton);
    });

    // mutate was called once
    expect(mockMutate).toHaveBeenCalledTimes(1);

    const savedPayload: Harness = mockMutate.mock.calls[0][0];

    // created_at preserved
    expect(savedPayload.created_at).toBe('2024-01-01T00:00:00Z');

    // All 3 node ids present in saved payload
    const savedNodeIds = savedPayload.nodes.map(n => n.id);
    expect(savedNodeIds).toContain('n1');
    expect(savedNodeIds).toContain('n2');
    expect(savedNodeIds).toContain('n3');

    // Both edges preserved
    const savedEdgeIds = savedPayload.edges.map(e => e.id);
    expect(savedEdgeIds).toContain('e1');
    expect(savedEdgeIds).toContain('e2');
  });

  // -------------------------------------------------------------------------
  // 2. Agent node config editing
  // -------------------------------------------------------------------------

  it('agent node config: selecting agent node exposes config fields, onNodeChange updates state', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: fixture,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    // Simulate clicking on agent node n2 inside the ReactFlow canvas
    const canvas = screen.getByTestId('react-flow');
    const agentNodeTrigger = document.createElement('div');
    agentNodeTrigger.dataset.nodeid = 'n2';
    await act(async () => {
      fireEvent.click(canvas, { target: agentNodeTrigger });
    });

    // VariableInspector shows agent_ref input for agent node
    expect(screen.getByLabelText('agent_ref')).toBeInTheDocument();
    expect(screen.getByLabelText('prompt_template')).toBeInTheDocument();

    // Invoke onNodeChange directly (simulates the inspector calling back)
    await act(async () => {
      capturedOnNodeChange!('n2', { agent_ref: 'new-agent', prompt_template: 'hello' });
    });

    // After onNodeChange, the save payload should reflect the updated config
    const saveButton = screen.getByTestId('save-button');
    await act(async () => {
      fireEvent.click(saveButton);
    });

    expect(mockMutate).toHaveBeenCalledTimes(1);
    const savedPayload: Harness = mockMutate.mock.calls[0][0];
    const savedN2 = savedPayload.nodes.find(n => n.id === 'n2');
    expect(savedN2).toBeDefined();
    expect(savedN2!.data.agent_ref).toBe('new-agent');
  });

  // -------------------------------------------------------------------------
  // 3. Drag-drop creates a node on canvas
  // -------------------------------------------------------------------------

  it('drag-drop: dropping application/reactflow=agent on canvas adds an agent node', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: fixture,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    // ReactFlow component handles onDrop directly
    const reactFlowCanvas = screen.getByTestId('react-flow');
    const dataTransfer = {
      getData: vi.fn().mockReturnValue('agent'),
      dropEffect: '',
    };

    await act(async () => {
      fireEvent.drop(reactFlowCanvas, {
        dataTransfer,
        clientX: 150,
        clientY: 250,
      });
    });

    // getData was called with the correct key
    expect(dataTransfer.getData).toHaveBeenCalledWith('application/reactflow');

    // After drop, click Save — new node should appear in saved payload
    const saveButton = screen.getByTestId('save-button');
    await act(async () => {
      fireEvent.click(saveButton);
    });

    expect(mockMutate).toHaveBeenCalledTimes(1);
    const savedPayload: Harness = mockMutate.mock.calls[0][0];
    // Original 3 nodes + 1 new agent node = 4
    expect(savedPayload.nodes.length).toBe(4);
    const newNode = savedPayload.nodes.find(n => !['n1', 'n2', 'n3'].includes(n.id));
    expect(newNode).toBeDefined();
    expect(newNode!.type).toBe('agent');
  });

  // -------------------------------------------------------------------------
  // 4. 422 error surfaces in the UI
  // -------------------------------------------------------------------------

  it('save error banner appears when useSaveHarness returns isError=true', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: fixture,
      isLoading: false,
      isError: false,
    } as any);
    mockSaveMutation.isError = true;

    await act(async () => {
      renderEditor();
    });

    expect(screen.getByTestId('save-error')).toBeInTheDocument();
    expect(screen.getByText(/save failed/i)).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // 5. harness-canvas wrapper class present
  // -------------------------------------------------------------------------

  it('canvas wrapper element has harness-canvas className', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: fixture,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    const canvasWrapper = screen.getByTestId('react-flow').parentElement as HTMLElement;
    expect(canvasWrapper.className).toContain('harness-canvas');
  });
});
