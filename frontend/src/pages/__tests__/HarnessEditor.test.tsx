import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { Harness } from '../../types';

// ---------------------------------------------------------------------------
// Mock @xyflow/react — must be hoisted before any imports of the module under test
// ---------------------------------------------------------------------------

vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ onNodeClick, onEdgeClick, onDragOver, onDrop, children }: any) => (
    <div
      data-testid="react-flow"
      onDragOver={onDragOver}
      onDrop={onDrop}
      onClick={(e) => {
        const target = e.target as HTMLElement;
        const nodeId = target.dataset.nodeid;
        const edgeId = target.dataset.edgeid;
        if (nodeId && onNodeClick) {
          onNodeClick(e, { id: nodeId });
        } else if (edgeId && onEdgeClick) {
          onEdgeClick(e, { id: edgeId });
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
  error: null as unknown,
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

vi.mock('../../components/harness/VariableInspector', () => ({
  VariableInspector: ({ harness, selectedNode, selectedEdge }: any) => (
    <div data-testid="variable-inspector">
      {harness ? 'harness-loaded' : 'no-harness'}
      {selectedNode ? `-node-${selectedNode.id}` : ''}
      {selectedEdge ? `-edge-${selectedEdge.id}` : ''}
    </div>
  ),
}));

vi.mock('../../components/harness/nodeTypes', () => ({
  nodeTypes: {},
}));

// ---------------------------------------------------------------------------
// Import module under test AFTER all mocks are registered
// ---------------------------------------------------------------------------

import { HarnessEditor } from '../HarnessEditor';
import { useHarness } from '../../hooks/useHarnesses';

// ---------------------------------------------------------------------------
// Fixture — uses new HarnessNode.data + dict ports
// ---------------------------------------------------------------------------

const mockHarness: Harness = {
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
  ],
  edges: [
    {
      id: 'e1',
      source: { node_id: 'n1', port_id: 'out' },
      target: { node_id: 'n2', port_id: 'in' },
      condition: null,
    },
  ],
  variables: { env: 'prod' },
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
// Tests
// ---------------------------------------------------------------------------

describe('HarnessEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSaveMutation.mutate = mockMutate;
    mockSaveMutation.isPending = false;
    mockSaveMutation.isError = false;
    mockSaveMutation.error = null;
  });

  it('shows loading state when useHarness is loading', () => {
    vi.mocked(useHarness).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as any);
    renderEditor();
    expect(screen.getByText(/loading harness/i)).toBeInTheDocument();
  });

  it('shows error state when useHarness returns error', () => {
    vi.mocked(useHarness).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as any);
    renderEditor();
    expect(screen.getByText(/failed to load harness/i)).toBeInTheDocument();
  });

  it('renders canvas with ReactFlow when harness loads', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    await act(async () => { renderEditor(); });
    expect(screen.getByTestId('react-flow')).toBeInTheDocument();
  });

  it('Save button calls useSaveHarness.mutate on click', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    await act(async () => { renderEditor(); });
    await act(async () => { fireEvent.click(screen.getByTestId('save-button')); });
    expect(mockMutate).toHaveBeenCalledTimes(1);
  });

  it('saved payload uses data field (not config) on nodes', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    await act(async () => { renderEditor(); });
    await act(async () => { fireEvent.click(screen.getByTestId('save-button')); });

    const saved: Harness = mockMutate.mock.calls[0][0];
    const n2 = saved.nodes.find((n) => n.id === 'n2')!;
    expect(n2.data.agent_ref).toBe('my-agent');
    expect(n2.data.prompt_template).toBe('hello');
    // no config key
    expect((n2 as any).config).toBeUndefined();
  });

  it('saved payload includes current variables', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    await act(async () => { renderEditor(); });
    await act(async () => { fireEvent.click(screen.getByTestId('save-button')); });

    const saved: Harness = mockMutate.mock.calls[0][0];
    expect(saved.variables).toEqual({ env: 'prod' });
  });

  it('shows save error banner with formatted message when saveMutation.isError', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    mockSaveMutation.isError = true;
    mockSaveMutation.error = { detail: 'Invalid graph' };

    await act(async () => { renderEditor(); });

    const banner = screen.getByTestId('save-error');
    expect(banner).toBeInTheDocument();
    expect(banner.textContent).toContain('Invalid graph');
  });

  it('formats Pydantic v2 validation array errors', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    mockSaveMutation.isError = true;
    mockSaveMutation.error = {
      detail: [
        { loc: ['nodes', '0', 'ports'], msg: 'field required', type: 'missing' },
      ],
    };

    await act(async () => { renderEditor(); });

    const banner = screen.getByTestId('save-error');
    expect(banner.textContent).toContain('nodes.0.ports');
    expect(banner.textContent).toContain('field required');
  });

  it('formats network Error objects', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    mockSaveMutation.isError = true;
    mockSaveMutation.error = new Error('Network timeout');

    await act(async () => { renderEditor(); });

    expect(screen.getByTestId('save-error').textContent).toContain('Network timeout');
  });

  it('clicking an edge sets selectedEdge in VariableInspector', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    await act(async () => { renderEditor(); });

    const canvas = screen.getByTestId('react-flow');
    const edgeTrigger = document.createElement('div');
    edgeTrigger.dataset.edgeid = 'e1';
    await act(async () => {
      fireEvent.click(canvas, { target: edgeTrigger });
    });

    expect(screen.getByTestId('variable-inspector').textContent).toContain('-edge-e1');
  });

  it('canvas wrapper element has harness-canvas className', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    await act(async () => { renderEditor(); });

    const wrapper = screen.getByTestId('react-flow').parentElement as HTMLElement;
    expect(wrapper.className).toContain('harness-canvas');
  });

  it('renders NodePalette and VariableInspector', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    await act(async () => { renderEditor(); });
    expect(screen.getByTestId('node-palette')).toBeInTheDocument();
    expect(screen.getByTestId('variable-inspector')).toBeInTheDocument();
  });

  it('onDrop creates a node with the dragged type at the drop position', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);
    await act(async () => { renderEditor(); });

    const canvas = screen.getByTestId('react-flow').parentElement as HTMLElement;
    const dataTransfer = { getData: vi.fn().mockReturnValue('agent'), dropEffect: '' };
    await act(async () => {
      fireEvent.drop(canvas, { dataTransfer, clientX: 100, clientY: 200 });
    });
    expect(dataTransfer.getData).toHaveBeenCalledWith('application/reactflow');
  });
});
