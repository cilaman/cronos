import React, { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  addEdge,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import type { Connection, Node as RFNode, Edge as RFEdge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import '../components/harness/reactflow-overrides.css';
import { nodeTypes } from '../components/harness/nodeTypes';
import { NodePalette } from '../components/harness/NodePalette';
import { VariableInspector } from '../components/harness/VariableInspector';
import { RunOverlay } from '../components/harness/RunOverlay';
import { RunHistory } from '../components/harness/RunHistory';
import { ChildTaskDrawer } from '../components/harness/ChildTaskDrawer';
import { useHarness, useSaveHarness } from '../hooks/useHarnesses';
import { useTriggerHarnessRun } from '../hooks/useHarnessRuns';
import { toReactFlow, fromReactFlow } from '../components/harness/harnessMapping';
import type { HarnessNode, HarnessEdge, NodeType, Position } from '../types';
import type { OverlayMode } from '../hooks/useRunStateOverlay';

// ---------------------------------------------------------------------------
// Error formatting for 422 / network failures
// ---------------------------------------------------------------------------

interface PydanticError {
  loc: string[];
  msg: string;
  type: string;
}

function formatSaveError(error: unknown): string {
  if (!error) return 'Save failed.';

  // (a) Network / transport error — has .message
  if (error instanceof Error) return error.message;

  // (b) Pydantic v2 validation array — { detail: [{loc, msg, type}] }
  if (typeof error === 'object' && error !== null) {
    const obj = error as Record<string, unknown>;
    if (Array.isArray(obj.detail)) {
      const lines = (obj.detail as PydanticError[]).map(
        (e) => `${e.loc.join('.')}: ${e.msg}`,
      );
      return lines.join('\n');
    }
    // (c) HTTPException with string detail
    if (typeof obj.detail === 'string') return obj.detail;
    // fallback
    if (typeof obj.message === 'string') return obj.message;
  }

  return 'Save failed — check the graph for errors.';
}

// ---------------------------------------------------------------------------
// Selected-item state machine
// ---------------------------------------------------------------------------

type SelectedItem =
  | { kind: 'none' }
  | { kind: 'node'; id: string }
  | { kind: 'edge'; id: string };

// ---------------------------------------------------------------------------
// Inner component (must live inside ReactFlowProvider)
// ---------------------------------------------------------------------------

function HarnessEditorInner() {
  const { spaceId = '', name = '' } = useParams<{ spaceId: string; name: string }>();
  const { data: harness, isLoading, isError } = useHarness(spaceId, name);
  const saveMutation = useSaveHarness(spaceId, name);
  const triggerMutation = useTriggerHarnessRun();
  const { screenToFlowPosition } = useReactFlow();

  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);

  // Single selected-item state machine (node | edge | none)
  const [selectedItem, setSelectedItem] = useState<SelectedItem>({ kind: 'none' });

  // Harness-level variables as local state so edits are reflected before save
  const [variables, setVariables] = useState<Record<string, string>>({});

  // Run overlay state
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('live');
  const [selectedChildTaskId, setSelectedChildTaskId] = useState<string | null>(null);

  // Initialize canvas + variables from loaded harness
  React.useEffect(() => {
    if (harness) {
      const { nodes: rfNodes, edges: rfEdges } = toReactFlow(harness);
      setNodes(rfNodes);
      setEdges(rfEdges);
      setVariables(harness.variables ?? {});
    }
  }, [harness, setNodes, setEdges]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges],
  );

  const handleNodeOpen = useCallback((childTaskId: string) => {
    setSelectedChildTaskId(childTaskId);
  }, []);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: { id: string }) => {
      setSelectedItem({ kind: 'node', id: node.id });
      // Open ChildTaskDrawer for nodes with a child task (populated by RunOverlay)
      const rfNode = nodes.find((n) => n.id === node.id);
      const childTaskId = (
        rfNode?.data as Record<string, unknown> | undefined
      )?.childTaskId as string | undefined;
      if (childTaskId) handleNodeOpen(childTaskId);
    },
    [nodes, handleNodeOpen],
  );

  const onEdgeClick = useCallback((_: React.MouseEvent, edge: { id: string }) => {
    setSelectedItem({ kind: 'edge', id: edge.id });
  }, []);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData('application/reactflow');
      if (!nodeType) return;
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      const newNode: RFNode = {
        id: `${nodeType}-${Date.now()}`,
        type: nodeType,
        position,
        data: { label: nodeType },
      };
      setNodes((nds) => [...nds, newNode]);
    },
    [screenToFlowPosition, setNodes],
  );

  // Handle node data changes (from VariableInspector) and edge condition changes
  const handleNodeChange = useCallback(
    (nodeId: string, data: Record<string, unknown>) => {
      if (nodeId.startsWith('__edge__')) {
        // Edge condition update — mutate the edge's RF data
        const edgeId = nodeId.slice('__edge__'.length);
        setEdges((eds) =>
          eds.map((e) =>
            e.id === edgeId
              ? { ...e, data: { ...(e.data as Record<string, unknown> ?? {}), ...data } }
              : e,
          ),
        );
        return;
      }
      setNodes((nds) =>
        nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n)),
      );
    },
    [setNodes, setEdges],
  );

  // Variables mutations
  const handleVariableChange = useCallback((key: string, value: string) => {
    setVariables((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleVariableAdd = useCallback((key: string, value: string) => {
    setVariables((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleVariableRemove = useCallback((key: string) => {
    setVariables((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const handleSave = useCallback(() => {
    if (!harness) return;
    const updated = fromReactFlow(nodes, edges, { ...harness, variables });
    saveMutation.mutate(updated);
  }, [harness, nodes, edges, variables, saveMutation]);

  const handleTriggerRun = useCallback(() => {
    triggerMutation.mutate(
      { spaceId, name },
      {
        onSuccess: (data) => {
          setCurrentRunId(data.run_id);
          setOverlayMode('live');
          setSelectedChildTaskId(null);
        },
      },
    );
  }, [triggerMutation, spaceId, name]);

  const handleSelectRun = useCallback((runId: string, mode: 'live' | 'replay') => {
    setCurrentRunId(runId);
    setOverlayMode(mode);
    setSelectedChildTaskId(null);
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setSelectedChildTaskId(null);
  }, []);

  // Derive selectedNode and selectedEdge from selectedItem state machine.
  // Falls back to live RF nodes for unsaved (freshly-dropped) nodes not yet in harness.
  const selectedNode: HarnessNode | null =
    selectedItem.kind === 'node'
      ? (() => {
          const saved = harness?.nodes.find((n) => n.id === selectedItem.id) ?? null;
          if (saved) return saved;
          const rfNode = nodes.find((n) => n.id === selectedItem.id);
          if (!rfNode) return null;
          const { label, ...data } = rfNode.data as Record<string, unknown>;
          return {
            id: rfNode.id,
            type: rfNode.type as NodeType,
            label: (label as string) ?? rfNode.type ?? '',
            position: rfNode.position as Position,
            ports: {} as Record<string, Record<string, unknown>>,
            data: data as Record<string, unknown>,
          };
        })()
      : null;

  const selectedEdge: HarnessEdge | null =
    selectedItem.kind === 'edge'
      ? (() => {
          const rfEdge = edges.find((e) => e.id === selectedItem.id);
          if (!rfEdge) return null;
          const edgeData = rfEdge.data as Record<string, unknown> | undefined;
          return {
            id: rfEdge.id,
            source: { node_id: rfEdge.source, port_id: rfEdge.sourceHandle ?? '' },
            target: { node_id: rfEdge.target, port_id: rfEdge.targetHandle ?? '' },
            condition:
              typeof edgeData?.condition === 'string' ? edgeData.condition : null,
          };
        })()
      : null;

  // Sync node changes back to harness for selectedNode lookups
  // (e.g., after onNodeChange mutates React Flow state, we need the inspector
  // to reflect the new data without waiting for a save+reload cycle)
  const liveSelectedNode: HarnessNode | null = selectedNode
    ? (() => {
        const rfNode = nodes.find((n) => n.id === selectedNode.id);
        if (!rfNode) return selectedNode;
        const { label, ...data } = rfNode.data as Record<string, unknown>;
        return {
          ...selectedNode,
          label: (label as string) ?? selectedNode.label,
          data: data as Record<string, unknown>,
        };
      })()
    : null;

  if (isLoading) return <div className="p-6 text-ink-faint">Loading harness…</div>;
  if (isError) return <div className="p-6 text-danger">Failed to load harness.</div>;
  if (!harness) return null;

  // Format the error message (may be a network error, HTTPException, or Pydantic array)
  const saveErrorMessage = saveMutation.isError
    ? formatSaveError(saveMutation.error)
    : null;

  const liveHarness = { ...harness, variables };

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center gap-4 border-b border-hairline px-4 py-2">
        <h1 className="font-display text-sm font-semibold uppercase tracking-wider text-ink">
          {name}
        </h1>
        <div className="flex-1" />
        {saveMutation.isError && (
          <span
            className="max-w-xs truncate text-xs text-danger"
            data-testid="save-error"
            title={saveErrorMessage ?? ''}
          >
            {saveErrorMessage}
          </span>
        )}
        <button
          type="button"
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="rounded border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent-bright transition hover:bg-accent/20 disabled:opacity-60"
          data-testid="save-button"
        >
          {saveMutation.isPending ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          onClick={handleTriggerRun}
          disabled={triggerMutation.isPending}
          className="rounded border border-green-400/40 bg-green-50 px-3 py-1 text-xs font-medium text-green-700 transition hover:bg-green-100 disabled:opacity-60"
          data-testid="run-button"
        >
          {triggerMutation.isPending ? 'Starting…' : 'Run'}
        </button>
      </header>

      {/* Canvas area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: RunHistory */}
        <div
          className="flex w-48 flex-col border-r border-hairline bg-surface-1 overflow-y-auto"
          data-testid="run-history-panel"
        >
          <div className="border-b border-hairline px-3 py-1.5">
            <span className="font-display text-[10px] font-semibold uppercase tracking-[0.24em] text-ink-faint">
              Run History
            </span>
          </div>
          <RunHistory spaceId={spaceId} name={name} onSelectRun={handleSelectRun} />
        </div>

        <NodePalette />
        <div className="harness-canvas relative flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onDragOver={onDragOver}
            onDrop={onDrop}
            nodeTypes={nodeTypes}
            fitView
          />
          {currentRunId !== null && (
            <RunOverlay
              runId={currentRunId}
              mode={overlayMode}
              onNodeOpen={handleNodeOpen}
            />
          )}
        </div>
        <VariableInspector
          selectedNode={liveSelectedNode}
          selectedEdge={selectedEdge}
          harness={liveHarness}
          onNodeChange={handleNodeChange}
          onVariableChange={handleVariableChange}
          onVariableAdd={handleVariableAdd}
          onVariableRemove={handleVariableRemove}
        />
        {/* Right panel: ChildTaskDrawer */}
        <ChildTaskDrawer
          child_task_id={selectedChildTaskId}
          onClose={handleCloseDrawer}
        />
      </div>
    </div>
  );
}

export function HarnessEditor() {
  return (
    <ReactFlowProvider>
      <HarnessEditorInner />
    </ReactFlowProvider>
  );
}
