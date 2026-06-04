import React, { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { ReactFlow, useNodesState, useEdgesState, addEdge, useReactFlow, ReactFlowProvider } from '@xyflow/react';
import type { Connection, Node as RFNode, Edge as RFEdge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import '../components/harness/reactflow-overrides.css';
import { nodeTypes } from '../components/harness/nodeTypes';
import { NodePalette } from '../components/harness/NodePalette';
import { VariableInspector } from '../components/harness/VariableInspector';
import { useHarness, useSaveHarness } from '../hooks/useHarnesses';
import { toReactFlow, fromReactFlow } from '../components/harness/harnessMapping';
import type { HarnessNode } from '../types';

function HarnessEditorInner() {
  const { spaceId = '', name = '' } = useParams<{ spaceId: string; name: string }>();
  const { data: harness, isLoading, isError } = useHarness(spaceId, name);
  const saveMutation = useSaveHarness(spaceId, name);
  const { screenToFlowPosition } = useReactFlow();

  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);
  const [selectedNode, setSelectedNode] = useState<HarnessNode | null>(null);

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
      </header>

      {/* Canvas area */}
      <div className="flex flex-1 overflow-hidden">
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
        </div>
        <VariableInspector
          selectedNode={selectedNode}
          harness={harness}
          onNodeChange={handleNodeChange}
          onVariableChange={() => {}}
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
