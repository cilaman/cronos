import type { NodeType } from '../../types';

const NODE_TYPES: NodeType[] = ['agent', 'trigger', 'decision', 'wait', 'aggregator'];

function onDragStart(event: React.DragEvent, nodeType: NodeType) {
  event.dataTransfer.setData('application/reactflow', nodeType);
  event.dataTransfer.effectAllowed = 'move';
}

export function NodePalette() {
  return (
    <div className="flex flex-col gap-2 p-3 border-r border-hairline bg-surface-1 w-40 shrink-0">
      {NODE_TYPES.map((nodeType) => (
        <div
          key={nodeType}
          className="rounded border border-hairline bg-surface-2 px-3 py-2 cursor-grab text-xs font-display uppercase tracking-wider text-ink-muted"
          draggable={true}
          onDragStart={(e) => onDragStart(e, nodeType)}
        >
          {nodeType.toUpperCase()}
        </div>
      ))}
    </div>
  );
}
