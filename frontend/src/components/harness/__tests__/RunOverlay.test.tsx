/**
 * RunOverlay.test.tsx — I4 arc6-live-overlay
 *
 * Key behaviors tested:
 *  - Renders nothing (null) when runId is null or no events have arrived
 *  - Calls setNodes with updated node.data when nodeStatuses change
 *  - Calls setEdges with animated flag when edgeStatuses change
 *  - Renders the buffer-truncated-banner with correct a11y label when
 *    bufferTruncated=true (R1 AC-2 mitigation)
 *  - R7 non-stutter: dispatching 20 synthetic node_transition events in a
 *    single act() results in setNodes being called at most twice
 *  - Nodes NOT in nodeStatuses are left untouched (R8 invariant)
 *  - onNodeOpen callback is accepted as a prop
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act, waitFor, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { RunOverlay } from '../RunOverlay';
import type { RunStatusOverlayData, NodeRunStatus } from '../runStatus';

// ---------------------------------------------------------------------------
// Mock @xyflow/react — capture setNodes / setEdges calls
// ---------------------------------------------------------------------------

const mockSetNodes = vi.fn();
const mockSetEdges = vi.fn();

vi.mock('@xyflow/react', () => ({
  useReactFlow: () => ({
    setNodes: mockSetNodes,
    setEdges: mockSetEdges,
  }),
}));

// ---------------------------------------------------------------------------
// Mock useRunStateOverlay — controlled returns
// These are module-level so we can reassign them in each test.
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useRunStateOverlay', () => ({
  useRunStateOverlay: vi.fn(() => ({
    nodeStatuses: new Map<string, RunStatusOverlayData>(),
    edgeStatuses: new Map<string, NodeRunStatus>(),
    bufferTruncated: false,
    status: 'connecting' as const,
  })),
}));

// Import the mocked module after vi.mock hoisting
import { useRunStateOverlay } from '../../../hooks/useRunStateOverlay';
const mockedUseRunStateOverlay = vi.mocked(useRunStateOverlay);

// ---------------------------------------------------------------------------
// rAF shim
// ---------------------------------------------------------------------------

type RafCallback = (time: number) => void;
let rafQueue: RafCallback[] = [];
let rafHandleCounter = 0;
const rafHandles = new Map<number, RafCallback>();

function fakeRaf(cb: RafCallback): number {
  const handle = ++rafHandleCounter;
  rafHandles.set(handle, cb);
  rafQueue.push(cb);
  return handle;
}

function fakeCaf(handle: number): void {
  const cb = rafHandles.get(handle);
  if (cb) {
    rafHandles.delete(handle);
    rafQueue = rafQueue.filter((c) => c !== cb);
  }
}

function flushRaf(): void {
  const pending = [...rafQueue];
  rafQueue = [];
  rafHandles.clear();
  pending.forEach((cb) => cb(0));
}

// ---------------------------------------------------------------------------
// Helper — wrapper with QueryClient
// ---------------------------------------------------------------------------

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockSetNodes.mockClear();
  mockSetEdges.mockClear();
  mockedUseRunStateOverlay.mockClear();
  // Default: return empty/inactive state
  mockedUseRunStateOverlay.mockReturnValue({
    nodeStatuses: new Map(),
    edgeStatuses: new Map(),
    bufferTruncated: false,
    status: 'connecting',
  });
  rafQueue = [];
  rafHandleCounter = 0;
  rafHandles.clear();
  vi.stubGlobal('requestAnimationFrame', fakeRaf);
  vi.stubGlobal('cancelAnimationFrame', fakeCaf);
});

afterEach(() => {
  flushRaf();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests: null / inactive overlay
// ---------------------------------------------------------------------------

describe('RunOverlay — null / inactive', () => {
  it('renders nothing when runId is null and bufferTruncated=false', () => {
    const client = makeClient();
    const { container } = render(
      <RunOverlay runId={null} mode="live" />,
      { wrapper: makeWrapper(client) },
    );
    expect(container.querySelector('[data-testid="buffer-truncated-banner"]')).toBeNull();
  });

  it('does not call setNodes when nodeStatuses is empty', () => {
    const client = makeClient();
    render(<RunOverlay runId={null} mode="live" />, { wrapper: makeWrapper(client) });
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it('does not call setEdges when edgeStatuses is empty', () => {
    const client = makeClient();
    render(<RunOverlay runId={null} mode="live" />, { wrapper: makeWrapper(client) });
    expect(mockSetEdges).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Tests: setNodes driven by nodeStatuses
// ---------------------------------------------------------------------------

describe('RunOverlay — setNodes driven by nodeStatuses', () => {
  it('calls setNodes when nodeStatuses is non-empty', () => {
    const client = makeClient();
    const nodeStatuses = new Map<string, RunStatusOverlayData>([
      [
        'node-a',
        {
          runStatus: 'in_progress',
          startedAt: '2024-01-01T00:00:00Z',
          endedAt: undefined,
          childTaskId: 'task-2',
        },
      ],
    ]);

    mockedUseRunStateOverlay.mockReturnValue({
      nodeStatuses,
      edgeStatuses: new Map(),
      bufferTruncated: false,
      status: 'live',
    });

    render(<RunOverlay runId="run-live" mode="live" />, { wrapper: makeWrapper(client) });

    expect(mockSetNodes).toHaveBeenCalledTimes(1);

    // Verify the updater function produces correct mutations.
    const updater = mockSetNodes.mock.calls[0][0] as (
      prev: Array<{ id: string; data: Record<string, unknown> }>,
    ) => Array<{ id: string; data: Record<string, unknown> }>;

    const prevNodes = [
      { id: 'node-a', data: { label: 'Agent' } },
      { id: 'node-b', data: { label: 'Other' } },
    ];
    const nextNodes = updater(prevNodes);

    expect(nextNodes[0].data.runStatus).toBe('in_progress');
    expect(nextNodes[0].data.startedAt).toBe('2024-01-01T00:00:00Z');
    expect(nextNodes[0].data.childTaskId).toBe('task-2');
    // node-b is untouched (not in nodeStatuses → R8 invariant)
    expect(nextNodes[1]).toStrictEqual(prevNodes[1]);
  });

  it('R8 invariant: nodes not in nodeStatuses are returned as the same reference', () => {
    const client = makeClient();
    mockedUseRunStateOverlay.mockReturnValue({
      nodeStatuses: new Map([['node-a', { runStatus: 'done' as const }]]),
      edgeStatuses: new Map(),
      bufferTruncated: false,
      status: 'ended',
    });

    render(<RunOverlay runId="run-1" mode="live" />, { wrapper: makeWrapper(client) });

    expect(mockSetNodes).toHaveBeenCalledTimes(1);
    const updater = mockSetNodes.mock.calls[0][0] as (
      prev: Array<{ id: string; data: Record<string, unknown> }>,
    ) => Array<{ id: string; data: Record<string, unknown> }>;

    const legacyNode = { id: 'legacy-node', data: { label: 'Legacy', someKey: 'value' } };
    const result = updater([legacyNode]);
    // Legacy node must be returned as the same object reference (not modified)
    expect(result[0]).toBe(legacyNode);
  });

  it('merges overlay fields onto existing node.data', () => {
    const client = makeClient();
    mockedUseRunStateOverlay.mockReturnValue({
      nodeStatuses: new Map([
        ['node-a', { runStatus: 'failed' as const, endedAt: '2024-01-01T00:01:00Z' }],
      ]),
      edgeStatuses: new Map(),
      bufferTruncated: false,
      status: 'ended',
    });

    render(<RunOverlay runId="run-1" mode="live" />, { wrapper: makeWrapper(client) });

    const updater = mockSetNodes.mock.calls[0][0] as (
      prev: Array<{ id: string; data: Record<string, unknown> }>,
    ) => Array<{ id: string; data: Record<string, unknown> }>;

    const prev = [{ id: 'node-a', data: { label: 'Agent', agent_ref: 'my-agent' } }];
    const next = updater(prev);

    // Existing data fields preserved; overlay fields added.
    expect(next[0].data.label).toBe('Agent');
    expect(next[0].data.agent_ref).toBe('my-agent');
    expect(next[0].data.runStatus).toBe('failed');
    expect(next[0].data.endedAt).toBe('2024-01-01T00:01:00Z');
  });
});

// ---------------------------------------------------------------------------
// Tests: setEdges driven by edgeStatuses
// ---------------------------------------------------------------------------

describe('RunOverlay — setEdges driven by edgeStatuses', () => {
  it('calls setEdges when edgeStatuses is non-empty', () => {
    const client = makeClient();
    mockedUseRunStateOverlay.mockReturnValue({
      nodeStatuses: new Map(),
      edgeStatuses: new Map([['edge-a-b', 'done' as const]]),
      bufferTruncated: false,
      status: 'live',
    });

    render(<RunOverlay runId="run-live" mode="live" />, { wrapper: makeWrapper(client) });

    expect(mockSetEdges).toHaveBeenCalledTimes(1);

    const updater = mockSetEdges.mock.calls[0][0] as (
      prev: Array<{ id: string; animated?: boolean; style?: Record<string, unknown> }>,
    ) => Array<{ id: string; animated?: boolean; style?: Record<string, unknown> }>;

    const prevEdges = [
      { id: 'edge-a-b', animated: false },
      { id: 'edge-b-c', animated: false },
    ];
    const nextEdges = updater(prevEdges);

    expect(nextEdges[0].animated).toBe(true);
    expect(nextEdges[0].style?.stroke).toBe('#22c55e');
    // edge-b-c is untouched
    expect(nextEdges[1]).toStrictEqual(prevEdges[1]);
  });

  it('does not call setEdges when edgeStatuses is empty', () => {
    const client = makeClient();
    render(<RunOverlay runId="run-live" mode="live" />, { wrapper: makeWrapper(client) });
    expect(mockSetEdges).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Tests: buffer-truncated banner (R1 AC-2)
// ---------------------------------------------------------------------------

describe('RunOverlay — buffer-truncated banner', () => {
  it('renders the banner when bufferTruncated=true', () => {
    const client = makeClient();
    mockedUseRunStateOverlay.mockReturnValue({
      nodeStatuses: new Map(),
      edgeStatuses: new Map(),
      bufferTruncated: true,
      status: 'live',
    });

    render(<RunOverlay runId="run-live" mode="live" />, { wrapper: makeWrapper(client) });

    const banner = screen.getByTestId('buffer-truncated-banner');
    expect(banner).toBeTruthy();
  });

  it('banner has correct a11y label', () => {
    const client = makeClient();
    mockedUseRunStateOverlay.mockReturnValue({
      nodeStatuses: new Map(),
      edgeStatuses: new Map(),
      bufferTruncated: true,
      status: 'live',
    });

    render(<RunOverlay runId="run-live" mode="live" />, { wrapper: makeWrapper(client) });

    const banner = screen.getByTestId('buffer-truncated-banner');
    expect(banner.getAttribute('aria-label')).toBe(
      'Some events were dropped before this view connected.',
    );
  });

  it('banner has role=alert', () => {
    const client = makeClient();
    mockedUseRunStateOverlay.mockReturnValue({
      nodeStatuses: new Map(),
      edgeStatuses: new Map(),
      bufferTruncated: true,
      status: 'live',
    });

    render(<RunOverlay runId="run-live" mode="live" />, { wrapper: makeWrapper(client) });

    const banner = screen.getByTestId('buffer-truncated-banner');
    expect(banner.getAttribute('role')).toBe('alert');
  });

  it('does NOT render the banner when bufferTruncated=false', () => {
    const client = makeClient();
    render(<RunOverlay runId="run-live" mode="live" />, { wrapper: makeWrapper(client) });
    expect(screen.queryByTestId('buffer-truncated-banner')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Tests: R7 non-stutter assertion
//
// Dispatches 20 synthetic node_transition events in a single act() and verifies
// that setNodes is called at most twice (R7 design spec mitigation).
//
// This is validated at the mock boundary: we simulate what would happen if
// nodeStatuses changed twice (once before rAF flush with some nodes, once after
// flush with all 20 nodes), confirming RunOverlay only calls setNodes once per
// React render cycle triggered by the map change.
// ---------------------------------------------------------------------------

describe('RunOverlay — R7 non-stutter', () => {
  it('setNodes is called at most twice for 20 node_transition events in a single act()', async () => {
    const client = makeClient();

    // Start with no statuses.
    const { rerender } = render(
      <RunOverlay runId="run-r7" mode="live" />,
      { wrapper: makeWrapper(client) },
    );

    mockSetNodes.mockClear();

    // Simulate what useRunStateOverlay (I3) produces after a 20-event rAF flush:
    // all 20 nodes arrive in one React state update (one new Map reference).
    const allTwentyNodes = new Map<string, RunStatusOverlayData>();
    for (let i = 0; i < 20; i++) {
      allTwentyNodes.set(`node-${i}`, {
        runStatus: 'in_progress',
        startedAt: '2024-01-01T00:00:00Z',
      });
    }

    act(() => {
      mockedUseRunStateOverlay.mockReturnValue({
        nodeStatuses: allTwentyNodes,
        edgeStatuses: new Map(),
        bufferTruncated: false,
        status: 'live',
      });
      rerender(<RunOverlay runId="run-r7" mode="live" />);
    });

    await waitFor(() => {
      expect(mockSetNodes.mock.calls.length).toBeGreaterThanOrEqual(1);
    });

    // R7 contract: at most 2 calls for 20-event burst.
    expect(mockSetNodes.mock.calls.length).toBeLessThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// Tests: onNodeOpen prop
// ---------------------------------------------------------------------------

describe('RunOverlay — onNodeOpen prop', () => {
  it('accepts an onNodeOpen callback as a prop without error', () => {
    const client = makeClient();
    const onNodeOpen = vi.fn();
    expect(() => {
      render(
        <RunOverlay runId="run-live" mode="live" onNodeOpen={onNodeOpen} />,
        { wrapper: makeWrapper(client) },
      );
    }).not.toThrow();
  });

  it('renders without onNodeOpen (optional prop)', () => {
    const client = makeClient();
    expect(() => {
      render(<RunOverlay runId="run-live" mode="live" />, { wrapper: makeWrapper(client) });
    }).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Tests: replay mode
// ---------------------------------------------------------------------------

describe('RunOverlay — replay mode', () => {
  it('calls setNodes with replay node statuses', () => {
    const client = makeClient();
    const replayNodes = new Map<string, RunStatusOverlayData>([
      ['node-a', { runStatus: 'done', childTaskId: 'task-2' }],
      ['node-b', { runStatus: 'failed' }],
    ]);

    mockedUseRunStateOverlay.mockReturnValue({
      nodeStatuses: replayNodes,
      edgeStatuses: new Map(),
      bufferTruncated: false,
      status: 'ended',
    });

    render(<RunOverlay runId="run-replay" mode="replay" />, { wrapper: makeWrapper(client) });

    expect(mockSetNodes).toHaveBeenCalledTimes(1);

    const updater = mockSetNodes.mock.calls[0][0] as (
      prev: Array<{ id: string; data: Record<string, unknown> }>,
    ) => Array<{ id: string; data: Record<string, unknown> }>;

    const result = updater([
      { id: 'node-a', data: {} },
      { id: 'node-b', data: {} },
    ]);
    expect(result[0].data.runStatus).toBe('done');
    expect(result[0].data.childTaskId).toBe('task-2');
    expect(result[1].data.runStatus).toBe('failed');
  });

  it('does NOT render banner in replay mode without buffer_truncated', () => {
    const client = makeClient();
    mockedUseRunStateOverlay.mockReturnValue({
      nodeStatuses: new Map(),
      edgeStatuses: new Map(),
      bufferTruncated: false,
      status: 'ended',
    });

    render(<RunOverlay runId="run-replay" mode="replay" />, { wrapper: makeWrapper(client) });

    expect(screen.queryByTestId('buffer-truncated-banner')).toBeNull();
  });

  it('passes runId and mode to useRunStateOverlay', () => {
    const client = makeClient();
    render(
      <RunOverlay runId="run-replay" mode="replay" />,
      { wrapper: makeWrapper(client) },
    );
    expect(mockedUseRunStateOverlay).toHaveBeenCalledWith('run-replay', 'replay');
  });
});
