import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

export interface AgentNodeData {
  label?: string;
  agent_ref?: string;
  [key: string]: unknown;
}

export function AgentNode({ data }: NodeProps) {
  const nodeData = data as AgentNodeData;
  return (
    <div className="rounded border border-hairline bg-surface-2 px-3 py-2 text-xs min-w-[120px]">
      <Handle type="target" position={Position.Top} />
      <div className="font-semibold text-ink uppercase tracking-wide mb-1">AGENT</div>
      {nodeData.label && (
        <div className="text-ink truncate">{nodeData.label}</div>
      )}
      {nodeData.agent_ref && (
        <div className="text-ink opacity-70 truncate">{nodeData.agent_ref}</div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
