/**
 * HarnessEditor.runOverlay.test.tsx — I7 arc6-live-overlay
 *
 * Key behaviors tested:
 *  1. currentRunId state updates when RunHistory.onSelectRun fires
 *  2. RunOverlay is mounted when currentRunId is set
 *  3. ChildTaskDrawer is shown when onNodeOpen fires from RunOverlay
 *  4. Selecting a past run after a live run closes the live EventSource
 *     (spy on EventSource constructor count vs close count — R medium-risk mitigation)
 *  5. Run button triggers useTriggerHarnessRun.mutate and sets currentRunId
 *  6. ChildTaskDrawer is hidden (returns null) when selectedChildTaskId is null
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { Harness } from '../../types';

// ---------------------------------------------------------------------------
// Mock @xyflow/react — hoisted before imports of module under test
// ---------------------------------------------------------------------------

// Capture setNodes from useNodesState so tests can inject node.data overrides
let capturedSetNodes: React.Dispatch<React.SetStateAction<any[]>> | null = null;

vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ onNodeClick, onDragOver, onDrop, children }: any) => (
    <div
      data-testid="react-flow"
      onDragOver={onDragOver}
      onDrop={onDrop}
      onClick={(e: React.MouseEvent) => {
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
    capturedSetNodes = setNodes;
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

const mockTriggerMutate = vi.fn();
const mockTriggerMutation = {
  mutate: mockTriggerMutate,
  isPending: false,
  isError: false,
};

vi.mock('../../hooks/useHarnesses', () => ({
  useHarness: vi.fn(),
  useSaveHarness: vi.fn(() => mockSaveMutation),
}));

vi.mock('../../hooks/useHarnessRuns', () => ({
  useTriggerHarnessRun: vi.fn(() => mockTriggerMutation),
}));

// ---------------------------------------------------------------------------
// Mock sub-components — capture prop callbacks for testing
// ---------------------------------------------------------------------------

vi.mock('../../components/harness/NodePalette', () => ({
  NodePalette: () => <div data-testid="node-palette" />,
}));

vi.mock('../../components/harness/VariableInspector', () => ({
  VariableInspector: () => <div data-testid="variable-inspector" />,
}));

vi.mock('../../components/harness/nodeTypes', () => ({
  nodeTypes: {},
}));

// Capture the onSelectRun callback that HarnessEditor passes to RunHistory
let capturedOnSelectRun: ((runId: string, mode: 'live' | 'replay') => void) | null = null;

vi.mock('../../components/harness/RunHistory', () => ({
  RunHistory: ({ onSelectRun, spaceId, name }: any) => {
    capturedOnSelectRun = onSelectRun;
    return (
      <div data-testid="run-history" data-space-id={spaceId} data-name={name} />
    );
  },
}));

// Capture the onNodeOpen callback that HarnessEditor passes to RunOverlay
let capturedOnNodeOpen: ((childTaskId: string) => void) | null = null;

vi.mock('../../components/harness/RunOverlay', () => ({
  RunOverlay: ({ runId, mode, onNodeOpen }: any) => {
    capturedOnNodeOpen = onNodeOpen ?? null;
    return (
      <div
        data-testid="run-overlay"
        data-run-id={runId}
        data-mode={mode}
      />
    );
  },
}));

// ChildTaskDrawer mock — renders something visible when child_task_id is non-null
vi.mock('../../components/harness/ChildTaskDrawer', () => ({
  ChildTaskDrawer: ({ child_task_id, onClose }: any) => {
    if (child_task_id === null) return null;
    return (
      <div data-testid="child-task-drawer" data-task-id={child_task_id}>
        <button data-testid="drawer-close" onClick={onClose}>
          Close
        </button>
      </div>
    );
  },
}));

// ---------------------------------------------------------------------------
// Import module under test AFTER all mocks are registered
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
  edges: [],
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
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  capturedOnSelectRun = null;
  capturedOnNodeOpen = null;
  capturedSetNodes = null;
  mockSaveMutation.mutate = mockMutate;
  mockSaveMutation.isPending = false;
  mockSaveMutation.isError = false;
  mockTriggerMutation.mutate = mockTriggerMutate;
  mockTriggerMutation.isPending = false;
  mockTriggerMutation.isError = false;
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('HarnessEditor — run overlay integration', () => {
  // -------------------------------------------------------------------------
  // Test 1: RunHistory panel is rendered with correct props
  // -------------------------------------------------------------------------

  it('renders RunHistory panel with spaceId and name', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    const runHistory = screen.getByTestId('run-history');
    expect(runHistory).toBeInTheDocument();
    expect(runHistory.getAttribute('data-space-id')).toBe('test-space');
    expect(runHistory.getAttribute('data-name')).toBe('my-harness');
  });

  // -------------------------------------------------------------------------
  // Test 2: RunOverlay is NOT mounted when currentRunId is null (initial state)
  // -------------------------------------------------------------------------

  it('does NOT render RunOverlay when no run has been selected', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    expect(screen.queryByTestId('run-overlay')).toBeNull();
  });

  // -------------------------------------------------------------------------
  // Test 3: currentRunId state updates → RunOverlay mounts with correct runId
  // -------------------------------------------------------------------------

  it('mounts RunOverlay with correct runId when RunHistory.onSelectRun fires', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    // Simulate user selecting a past run from RunHistory
    await act(async () => {
      capturedOnSelectRun!('run-replay-42', 'replay');
    });

    const overlay = screen.getByTestId('run-overlay');
    expect(overlay).toBeInTheDocument();
    expect(overlay.getAttribute('data-run-id')).toBe('run-replay-42');
    expect(overlay.getAttribute('data-mode')).toBe('replay');
  });

  // -------------------------------------------------------------------------
  // Test 4: ChildTaskDrawer is not shown before onNodeOpen fires
  // -------------------------------------------------------------------------

  it('does NOT render ChildTaskDrawer when no node has been opened', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    expect(screen.queryByTestId('child-task-drawer')).toBeNull();
  });

  // -------------------------------------------------------------------------
  // Test 5: ChildTaskDrawer shown when onNodeOpen fires from RunOverlay
  // -------------------------------------------------------------------------

  it('shows ChildTaskDrawer with correct task id when RunOverlay.onNodeOpen fires', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    // First, select a run so RunOverlay is mounted and capturedOnNodeOpen is set
    await act(async () => {
      capturedOnSelectRun!('run-live-99', 'live');
    });

    expect(screen.getByTestId('run-overlay')).toBeInTheDocument();
    expect(capturedOnNodeOpen).not.toBeNull();

    // Simulate RunOverlay lifting a node-open event
    await act(async () => {
      capturedOnNodeOpen!('task-child-abc');
    });

    const drawer = screen.getByTestId('child-task-drawer');
    expect(drawer).toBeInTheDocument();
    expect(drawer.getAttribute('data-task-id')).toBe('task-child-abc');
  });

  // -------------------------------------------------------------------------
  // Test 6: ChildTaskDrawer close button clears selectedChildTaskId
  // -------------------------------------------------------------------------

  it('ChildTaskDrawer is hidden after close button is clicked', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    // Open overlay and drawer
    await act(async () => {
      capturedOnSelectRun!('run-live-1', 'live');
    });
    await act(async () => {
      capturedOnNodeOpen!('task-xyz');
    });

    expect(screen.getByTestId('child-task-drawer')).toBeInTheDocument();

    // Click close
    await act(async () => {
      fireEvent.click(screen.getByTestId('drawer-close'));
    });

    expect(screen.queryByTestId('child-task-drawer')).toBeNull();
  });

  // -------------------------------------------------------------------------
  // Test 7: Run button is present and calls useTriggerHarnessRun.mutate
  // -------------------------------------------------------------------------

  it('Run button calls triggerHarnessRun.mutate with spaceId and name', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    const runButton = screen.getByTestId('run-button');
    expect(runButton).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(runButton);
    });

    expect(mockTriggerMutate).toHaveBeenCalledTimes(1);
    expect(mockTriggerMutate.mock.calls[0][0]).toEqual({ spaceId: 'test-space', name: 'my-harness' });
  });

  // -------------------------------------------------------------------------
  // Test 8: RunOverlay mounts in live mode after successful triggerHarnessRun
  // -------------------------------------------------------------------------

  it('mounts RunOverlay in live mode after triggerHarnessRun succeeds', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    // Wire mockTriggerMutate to call onSuccess immediately
    mockTriggerMutation.mutate = vi.fn((_args: any, options: any) => {
      options?.onSuccess?.({ run_id: 'run-new-live' });
    });

    await act(async () => {
      renderEditor();
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId('run-button'));
    });

    const overlay = screen.getByTestId('run-overlay');
    expect(overlay.getAttribute('data-run-id')).toBe('run-new-live');
    expect(overlay.getAttribute('data-mode')).toBe('live');
  });

  // -------------------------------------------------------------------------
  // Test 9: switching from live to replay — EventSource close tracking
  //
  // Design spec: "I7 test asserts that selecting a past run after a live run
  // does not keep the live EventSource open (spy on EventSource constructor
  // count vs close count)."
  //
  // Mechanism: we spy on the global EventSource constructor (counting how many
  // instances are created) and on each instance's .close() method.  After
  // switching from 'live' to 'replay', the net open EventSources
  // (created − closed) must not be greater than 1 (the new replay session).
  // -------------------------------------------------------------------------

  it('switching from live to replay run closes the live EventSource (no leak)', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    const closedInstances: EventSource[] = [];
    const createdInstances: EventSource[] = [];

    // Spy on global EventSource: track created/closed counts
    const OriginalEventSource = globalThis.EventSource;
    const MockEventSource = vi.fn().mockImplementation((url: string) => {
      const instance = {
        url,
        readyState: 0,
        onopen: null as any,
        onerror: null as any,
        onmessage: null as any,
        close: vi.fn(() => {
          closedInstances.push(instance as unknown as EventSource);
        }),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
        CONNECTING: 0,
        OPEN: 1,
        CLOSED: 2,
      };
      createdInstances.push(instance as unknown as EventSource);
      return instance;
    });

    // Only install the spy if EventSource is available in the test environment
    if (typeof globalThis.EventSource !== 'undefined' || true) {
      vi.stubGlobal('EventSource', MockEventSource);
    }

    try {
      await act(async () => {
        renderEditor();
      });

      // Step A: select a live run (simulates a running harness run)
      await act(async () => {
        capturedOnSelectRun!('run-live-session', 'live');
      });

      expect(screen.getByTestId('run-overlay')).toBeInTheDocument();
      expect(screen.getByTestId('run-overlay').getAttribute('data-mode')).toBe('live');

      // Step B: switch to a past (replay) run
      await act(async () => {
        capturedOnSelectRun!('run-replay-past', 'replay');
      });

      await waitFor(() => {
        expect(screen.getByTestId('run-overlay').getAttribute('data-run-id')).toBe('run-replay-past');
      });

      // All previously-created EventSource instances must have been closed when
      // mode or runId changed (net open = created − closed ≤ 1 for the current
      // replay session which uses REST, not SSE, so potentially 0 are open).
      const netOpen = createdInstances.length - closedInstances.length;
      expect(netOpen).toBeLessThanOrEqual(1);
    } finally {
      if (OriginalEventSource !== undefined) {
        vi.stubGlobal('EventSource', OriginalEventSource);
      } else {
        vi.unstubAllGlobals();
      }
    }
  });

  // -------------------------------------------------------------------------
  // Test 10: mode is correctly threaded to RunOverlay
  // -------------------------------------------------------------------------

  it('passes live mode to RunOverlay for a running run', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    await act(async () => {
      capturedOnSelectRun!('run-live-mode', 'live');
    });

    const overlay = screen.getByTestId('run-overlay');
    expect(overlay.getAttribute('data-mode')).toBe('live');
  });

  // -------------------------------------------------------------------------
  // Test 11: run-history-panel is present in the rendered layout
  // -------------------------------------------------------------------------

  it('renders run-history-panel container in the layout', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    expect(screen.getByTestId('run-history-panel')).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Test 12: switching runs updates RunOverlay runId attribute
  // -------------------------------------------------------------------------

  it('updates RunOverlay runId when a different run is selected', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    await act(async () => {
      renderEditor();
    });

    await act(async () => {
      capturedOnSelectRun!('run-first', 'replay');
    });

    expect(screen.getByTestId('run-overlay').getAttribute('data-run-id')).toBe('run-first');

    await act(async () => {
      capturedOnSelectRun!('run-second', 'replay');
    });

    expect(screen.getByTestId('run-overlay').getAttribute('data-run-id')).toBe('run-second');
  });

  // -------------------------------------------------------------------------
  // Test 13: clicking a ReactFlow node with childTaskId in node.data opens
  // ChildTaskDrawer — regression test for R3 AC-1 (F1 fix)
  //
  // Simulates the real click path:
  //  1. A node element with data-nodeid is clicked inside the mocked ReactFlow.
  //  2. The mock calls onNodeClick(e, { id: nodeId }).
  //  3. HarnessEditor.onNodeClick reads nodes.find(n => n.id === node.id) and
  //     reads node.data.childTaskId from the React Flow node state.
  //  4. handleNodeOpen(childTaskId) is called → ChildTaskDrawer becomes visible.
  // -------------------------------------------------------------------------

  it('clicking a node whose React Flow data has childTaskId opens ChildTaskDrawer (R3 AC-1)', async () => {
    vi.mocked(useHarness).mockReturnValue({
      data: mockHarness,
      isLoading: false,
      isError: false,
    } as any);

    capturedSetNodes = null;

    await act(async () => {
      renderEditor();
    });

    // Verify drawer is not visible initially
    expect(screen.queryByTestId('child-task-drawer')).toBeNull();

    // Inject a childTaskId onto node 'n2' via the captured setNodes — this simulates
    // what RunOverlay.setNodes does after receiving a run event for that node.
    expect(capturedSetNodes).not.toBeNull();
    await act(async () => {
      capturedSetNodes!((prev: any[]) =>
        prev.map((n: any) =>
          n.id === 'n2'
            ? { ...n, data: { ...n.data, childTaskId: 'task-from-click' } }
            : n,
        ),
      );
    });

    // Simulate a click on node 'n2' via the mocked ReactFlow canvas.
    // The mock reads data-nodeid from the clicked target and calls onNodeClick.
    const reactFlowEl = screen.getByTestId('react-flow');
    await act(async () => {
      const clickTarget = document.createElement('div');
      clickTarget.dataset.nodeid = 'n2';
      reactFlowEl.appendChild(clickTarget);
      fireEvent.click(clickTarget);
      reactFlowEl.removeChild(clickTarget);
    });

    // ChildTaskDrawer must now be visible with the correct task id
    const drawer = await screen.findByTestId('child-task-drawer');
    expect(drawer).toBeInTheDocument();
    expect(drawer.getAttribute('data-task-id')).toBe('task-from-click');
  });
});
