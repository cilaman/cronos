import type { HarnessNode, Harness } from '../../types';

interface VariableInspectorProps {
  selectedNode: HarnessNode | null;
  harness: Harness | null;
  onNodeChange: (nodeId: string, config: Record<string, unknown>) => void;
  onVariableChange: (key: string, value: string) => void;
}

export function VariableInspector({
  selectedNode,
  harness,
  onNodeChange,
  onVariableChange,
}: VariableInspectorProps) {
  // Empty state when harness is null and no node selected
  if (!harness && !selectedNode) {
    return (
      <div className="p-3 border-l border-hairline bg-surface-1 w-56 shrink-0 overflow-y-auto">
        <div className="text-xs text-ink-muted italic">No harness loaded.</div>
      </div>
    );
  }

  // When agent node is selected: show editable agent_ref + prompt fields
  if (selectedNode && selectedNode.type === 'agent') {
    const config = selectedNode.config;
    const agentRef = typeof config.agent_ref === 'string' ? config.agent_ref : '';
    const prompt = typeof config.prompt === 'string' ? config.prompt : '';

    return (
      <div className="p-3 border-l border-hairline bg-surface-1 w-56 shrink-0 overflow-y-auto">
        <div className="text-xs font-display uppercase tracking-wider text-ink-muted mb-2">Agent Config</div>
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-ink-muted">agent_ref</span>
            <input
              aria-label="agent_ref"
              className="border border-hairline rounded px-2 py-1 text-xs bg-surface-2 text-ink"
              value={agentRef}
              onChange={(e) =>
                onNodeChange(selectedNode.id, { ...config, agent_ref: e.target.value })
              }
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-ink-muted">prompt</span>
            <textarea
              aria-label="prompt"
              className="border border-hairline rounded px-2 py-1 text-xs bg-surface-2 text-ink resize-none"
              rows={4}
              value={prompt}
              onChange={(e) =>
                onNodeChange(selectedNode.id, { ...config, prompt: e.target.value })
              }
            />
          </label>
        </div>
      </div>
    );
  }

  // When non-agent node is selected: show generic key/value list from config
  if (selectedNode) {
    const config = selectedNode.config;
    return (
      <div className="p-3 border-l border-hairline bg-surface-1 w-56 shrink-0 overflow-y-auto">
        <div className="text-xs font-display uppercase tracking-wider text-ink-muted mb-2">Node Config</div>
        {Object.keys(config).length === 0 ? (
          <div className="text-xs text-ink-muted italic">No config.</div>
        ) : (
          <div className="flex flex-col gap-1">
            {Object.entries(config).map(([key, val]) => (
              <div key={key} className="flex gap-1 text-xs">
                <span className="text-ink-muted font-medium">{key}:</span>
                <span className="text-ink truncate">{String(val)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // No node selected: show harness-level variables
  const variables = harness!.variables;
  return (
    <div className="p-3 border-l border-hairline bg-surface-1 w-56 shrink-0 overflow-y-auto">
      <div className="text-xs font-display uppercase tracking-wider text-ink-muted mb-2">Variables</div>
      {Object.keys(variables).length === 0 ? (
        <div className="text-xs text-ink-muted italic">No variables.</div>
      ) : (
        <div className="flex flex-col gap-2">
          {Object.entries(variables).map(([key, val]) => (
            <label key={key} className="flex flex-col gap-1">
              <span className="text-xs text-ink-muted">{key}</span>
              <input
                className="border border-hairline rounded px-2 py-1 text-xs bg-surface-2 text-ink"
                value={val}
                onChange={(e) => onVariableChange(key, e.target.value)}
              />
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
