import React, { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { ReactFlow, useNodesState, useEdgesState, addEdge, useReactFlow, ReactFlowProvider } from '@xyflow/react';
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
import type { HarnessNode } from '../types';
import type { OverlayMode } from '../hooks/useRunStateOverlay';

function HarnessEditorInner() {
  const { spaceId = '', name = '' } = useParams<{ spaceId: string; name: string }>();
  const { data: harness, isLoading, isError } = useHarness(spaceId, name);
  const saveMutation = useSaveHarness(spaceId, name);
  const triggerMutation = useTriggerHarnessRun();
  const { screenToFlowPosition } = useReactFlow();

  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);
  const [selectedNode, setSelectedNode] = useState<HarnessNode | null>(null);

  // Run overlay state
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('live');
  const [selectedChildTaskId, setSelectedChildTaskId] = useState<string | null>(null);

  // Initialize canvas from loaded harness
  React.useEffect(() => {
    if (harness) {
      const { nodes: rfNodes, edges: rfEdges } = toReactFlow(harness);
      setNodes(rfNodes);
      setEdges(rfEdges);
    }
  }, [harness, setNodes, setEdges]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges(eds => addEdge(connection, eds)),
    [setEdges],
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: { id: string }) => {
    if (!harness) return;
    const found = harness.nodes.find(n => n.id === node.id) ?? null;
    setSelectedNode(found);
  }, [harness]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    const nodeType = event.dataTransfer.getData('application/reactflow');
    if (!nodeType) return;
    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const newNode = {
      id: `${nodeType}-${Date.now()}`,
      type: nodeType,
      position,
      data: { label: nodeType },
    };
    setNodes(nds => [...nds, newNode]);
  }, [screenToFlowPosition, setNodes]);

  const handleSave = useCallback(() => {
    if (!harness) return;
    const updated = fromReactFlow(nodes, edges, harness);
    saveMutation.mutate(updated);
  }, [harness, nodes, edges, saveMutation]);

  const handleNodeChange = useCallback((nodeId: string, config: Record<string, unknown>) => {
    setNodes(nds => nds.map(n => n.id === nodeId ? { ...n, data: { ...n.data, ...config } } : n));
  }, [setNodes]);

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

  const handleNodeOpen = useCallback((childTaskId: string) => {
    setSelectedChildTaskId(childTaskId);
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setSelectedChildTaskId(null);
  }, []);

  if (isLoading) return <div className="p-6 text-ink-faint">Loading harness…</div>;
  if (isError) return <div className="p-6 text-danger">Failed to load harness.</div>;
  if (!harness) return null;

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center gap-4 border-b border-hairline px-4 py-2">
        <h1 className="font-display text-sm font-semibold uppercase tracking-wider text-ink">
          {name}
        </h1>
        <div className="flex-1" />
        {saveMutation.isError && (
          <span className="text-xs text-danger" data-testid="save-error">
            Save failed — check the graph for errors.
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
        <div className="harness-canvas relative flex-1" onDragOver={onDragOver} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
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
          selectedNode={selectedNode}
          harness={harness}
          onNodeChange={handleNodeChange}
          onVariableChange={() => {}}
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
