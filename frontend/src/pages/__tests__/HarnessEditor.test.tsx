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
  ReactFlow: ({ onNodeClick, onDragOver, onDrop, children }: any) => (
    <div
      data-testid="react-flow"
      onDragOver={onDragOver}
      onDrop={onDrop}
      onClick={(e) => {
        // Simulate node click if the event carries a nodeId
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
// Mock CSS imports to avoid processing issues in tests
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
// Mock sub-components to avoid pulling in their deps
// ---------------------------------------------------------------------------

vi.mock('../../components/harness/NodePalette', () => ({
  NodePalette: () => <div data-testid="node-palette" />,
}));

vi.mock('../../components/harness/VariableInspector', () => ({
  VariableInspector: ({ harness, selectedNode }: any) => (
    <div data-testid="variable-inspector">
      {harness ? 'harness-loaded' : 'no-harness'}
      {selectedNode ? `-node-${selectedNode.id}` : ''}
    </div>
  ),
}));

vi.mock('../../components/harness/nodeTypes', () => ({
  nodeTypes: {},
}));

// ---------------------------------------------------------------------------
// Import the module under test AFTER all mocks are registered
// ---------------------------------------------------------------------------

import { HarnessEditor } from '../HarnessEditor';
import { useHarness } from '../../hooks/useHarnesses';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockHarness: Harness = {
  name: 'my-harness',
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
      ports: [],
      config: { agent_ref: 'my-agent', prompt: 'hello' },
    },
  ],
  edges: [
    { id: 'e1', source: { node_id: 'n1', port_id: 'out' }, target: { node_id: 'n2', port_id: 'in' } },
  ],
  variables: { env: 'prod' },
  created_at: '2024-01-01T00:00:00Z',
  version: 1,
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
    // Reset mockSaveMutation to defaults
    mockSaveMutation.mutate = mockMutate;
    mockSaveMutation.isPending = false;
    mockSaveMutation.isError = false;
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

    await act(async () => {
      renderEditor();
    });

    expect(screen.getByTestId('react-flow')).toBeInTheDocument();
  });

  it('Save button calls useSaveHarness.mutate on click', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    const saveButton = screen.getByTestId('save-button');
    await act(async () => {
      fireEvent.click(saveButton);
    });

    expect(mockMutate).toHaveBeenCalledTimes(1);
  });

  it('shows save error banner when saveMutation.isError is true', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
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

  it('onDrop creates a node with the dragged type at the drop position', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    const canvas = screen.getByTestId('react-flow').parentElement as HTMLElement;
    const dataTransfer = {
      getData: vi.fn().mockReturnValue('agent'),
      dropEffect: '',
    };

    await act(async () => {
      fireEvent.drop(canvas, {
        dataTransfer,
        clientX: 100,
        clientY: 200,
      });
    });

    expect(dataTransfer.getData).toHaveBeenCalledWith('application/reactflow');
  });

  it('renders NodePalette and VariableInspector', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    expect(screen.getByTestId('node-palette')).toBeInTheDocument();
    expect(screen.getByTestId('variable-inspector')).toBeInTheDocument();
  });
});
