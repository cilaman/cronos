import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

export interface AggregatorNodeData {
  label?: string;
  inputCount?: number;
  [key: string]: unknown;
}

export function AggregatorNode({ data }: NodeProps) {
  const nodeData = data as AggregatorNodeData;
  const inputCount = nodeData.inputCount ?? 2;
  return (
    <div className="rounded border border-hairline bg-surface-2 px-3 py-2 text-xs min-w-[120px]">
      {Array.from({ length: inputCount }).map((_, i) => (
        <Handle
          key={i}
          type="target"
          position={Position.Top}
          id={`in-${i}`}
          style={{ left: `${((i + 1) / (inputCount + 1)) * 100}%` }}
        />
      ))}
      <div className="font-semibold text-ink uppercase tracking-wide mb-1">AGGREGATOR</div>
      {nodeData.label && (
        <div className="text-ink truncate">{nodeData.label}</div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
