import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { runStatusClassName } from './runStatus';
import type { RunStatusOverlayData } from './runStatus';

export interface WaitNodeData extends RunStatusOverlayData {
  label?: string;
  [key: string]: unknown;
}

export function WaitNode({ data }: NodeProps) {
  const nodeData = data as WaitNodeData;
  const statusClass = runStatusClassName(nodeData.runStatus);
  return (
    <div className={`rounded border border-hairline bg-surface-2 px-3 py-2 text-xs min-w-[120px]${statusClass ? ` ${statusClass}` : ''}`}>
      <Handle type="target" position={Position.Top} />
      <div className="font-semibold text-ink uppercase tracking-wide mb-1">WAIT</div>
      {nodeData.label && (
        <div className="text-ink truncate">{nodeData.label}</div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
