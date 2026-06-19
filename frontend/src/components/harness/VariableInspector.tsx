import { useState, useEffect } from 'react';
import type { HarnessNode, HarnessEdge, Harness } from '../../types';
import { api } from '../../api';

interface VariableInspectorProps {
  selectedNode: HarnessNode | null;
  selectedEdge?: HarnessEdge | null;
  harness: Harness | null;
  onNodeChange: (nodeId: string, data: Record<string, unknown>) => void;
  onVariableChange: (key: string, value: string) => void;
  onVariableAdd?: (key: string, value: string) => void;
  onVariableRemove?: (key: string) => void;
  spaceId?: string;
}

// ---------------------------------------------------------------------------
// Shared label + input/textarea helpers
// ---------------------------------------------------------------------------

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

const INPUT_CLS =
  'border border-hairline rounded px-2 py-1 text-xs bg-surface-2 text-ink';
const SELECT_CLS =
  'border border-hairline rounded px-2 py-1 text-xs bg-surface-2 text-ink';

// ---------------------------------------------------------------------------
// Per-node-type config sections
// ---------------------------------------------------------------------------

const AGENT_REF_DATALIST_ID = 'agent-ref-options';

function AgentConfig({
  nodeId,
  data,
  onNodeChange,
  spaceId,
}: {
  nodeId: string;
  data: Record<string, unknown>;
  onNodeChange: (id: string, d: Record<string, unknown>) => void;
  spaceId?: string;
}) {
  const agentRef = typeof data.agent_ref === 'string' ? data.agent_ref : '';
  const promptTemplate =
    typeof data.prompt_template === 'string' ? data.prompt_template : '';

  const [agentOptions, setAgentOptions] = useState<string[]>([]);

  useEffect(() => {
    if (!spaceId) return;
    let cancelled = false;
    api.spaceTools(spaceId).then((resp) => {
      if (cancelled) return;
      const agentNames = resp.agents.map((a) => a.name);
      const skillNames = resp.skills.map((s) => s.name);
      setAgentOptions([...agentNames, ...skillNames]);
    }).catch(() => {
      // Graceful degradation: leave datalist empty on error
    });
    return () => { cancelled = true; };
  }, [spaceId]);

  return (
    <div className="flex flex-col gap-2">
      <datalist id={AGENT_REF_DATALIST_ID}>
        {agentOptions.map((name) => (
          <option key={name} value={name} />
        ))}
      </datalist>
      <Field label="agent_ref">
        <input
          aria-label="agent_ref"
          className={INPUT_CLS}
          list={AGENT_REF_DATALIST_ID}
          value={agentRef}
          onChange={(e) =>
            onNodeChange(nodeId, { ...data, agent_ref: e.target.value })
          }
        />
      </Field>
      <Field label="prompt_template">
        <textarea
          aria-label="prompt_template"
          className={`${INPUT_CLS} resize-none`}
          rows={4}
          value={promptTemplate}
          onChange={(e) =>
            onNodeChange(nodeId, { ...data, prompt_template: e.target.value })
          }
        />
      </Field>
    </div>
  );
}

function WaitConfig({
  nodeId,
  data,
  onNodeChange,
}: {
  nodeId: string;
  data: Record<string, unknown>;
  onNodeChange: (id: string, d: Record<string, unknown>) => void;
}) {
  const mode = typeof data.mode === 'string' ? data.mode : 'human';
  const maxWait =
    typeof data.max_wait_seconds === 'number' ? data.max_wait_seconds : '';
  const duration =
    typeof data.duration_seconds === 'number' ? data.duration_seconds : '';

  return (
    <div className="flex flex-col gap-2">
      <Field label="mode">
        <select
          aria-label="wait-mode"
          className={SELECT_CLS}
          value={mode}
          onChange={(e) => onNodeChange(nodeId, { ...data, mode: e.target.value })}
        >
          <option value="human">human</option>
          <option value="timed">timed</option>
        </select>
      </Field>
      {mode === 'human' && (
        <Field label="max_wait_seconds">
          <input
            aria-label="max_wait_seconds"
            type="number"
            className={INPUT_CLS}
            value={maxWait}
            onChange={(e) =>
              onNodeChange(nodeId, {
                ...data,
                max_wait_seconds: e.target.value ? Number(e.target.value) : undefined,
              })
            }
          />
        </Field>
      )}
      {mode === 'timed' && (
        <Field label="duration_seconds">
          <input
            aria-label="duration_seconds"
            type="number"
            className={INPUT_CLS}
            value={duration}
            onChange={(e) =>
              onNodeChange(nodeId, {
                ...data,
                duration_seconds: e.target.value ? Number(e.target.value) : undefined,
              })
            }
          />
        </Field>
      )}
    </div>
  );
}

function AggregatorConfig({
  nodeId,
  data,
  onNodeChange,
}: {
  nodeId: string;
  data: Record<string, unknown>;
  onNodeChange: (id: string, d: Record<string, unknown>) => void;
}) {
  const mode = typeof data.mode === 'string' ? data.mode : 'all';
  return (
    <Field label="mode">
      <select
        aria-label="aggregator-mode"
        className={SELECT_CLS}
        value={mode}
        onChange={(e) => onNodeChange(nodeId, { ...data, mode: e.target.value })}
      >
        <option value="all">all</option>
        <option value="any">any</option>
      </select>
    </Field>
  );
}

type TriggerKind = 'cron' | 'webhook' | 'file-change' | 'task-state-change';

function TriggerConfig({
  nodeId,
  data,
  onNodeChange,
}: {
  nodeId: string;
  data: Record<string, unknown>;
  onNodeChange: (id: string, d: Record<string, unknown>) => void;
}) {
  // cron triggers have no `kind` field; event triggers have kind
  const kind: TriggerKind =
    typeof data.kind === 'string' ? (data.kind as TriggerKind) : 'cron';

  function setKind(newKind: TriggerKind) {
    // Strip old per-kind fields and set the new kind
    const { expression, timezone, webhook_path, auth_token, watch_pattern, debounce_seconds, watched_state, ...rest } = data;
    void expression; void timezone; void webhook_path; void auth_token;
    void watch_pattern; void debounce_seconds; void watched_state;
    onNodeChange(nodeId, newKind === 'cron' ? { ...rest } : { ...rest, kind: newKind });
  }

  return (
    <div className="flex flex-col gap-2">
      <Field label="kind">
        <select
          aria-label="trigger-kind"
          className={SELECT_CLS}
          value={kind}
          onChange={(e) => setKind(e.target.value as TriggerKind)}
        >
          <option value="cron">cron</option>
          <option value="webhook">webhook</option>
          <option value="file-change">file-change</option>
          <option value="task-state-change">task-state-change</option>
        </select>
      </Field>

      {kind === 'cron' && (
        <>
          <Field label="expression">
            <input
              aria-label="cron-expression"
              className={INPUT_CLS}
              placeholder="0 * * * *"
              value={typeof data.expression === 'string' ? data.expression : ''}
              onChange={(e) =>
                onNodeChange(nodeId, { ...data, expression: e.target.value })
              }
            />
          </Field>
          <Field label="timezone (optional)">
            <input
              aria-label="cron-timezone"
              className={INPUT_CLS}
              placeholder="UTC"
              value={typeof data.timezone === 'string' ? data.timezone : ''}
              onChange={(e) =>
                onNodeChange(nodeId, { ...data, timezone: e.target.value })
              }
            />
          </Field>
        </>
      )}

      {kind === 'webhook' && (
        <>
          <Field label="webhook_path">
            <input
              aria-label="webhook-path"
              className={INPUT_CLS}
              value={typeof data.webhook_path === 'string' ? data.webhook_path : ''}
              onChange={(e) =>
                onNodeChange(nodeId, { ...data, webhook_path: e.target.value })
              }
            />
          </Field>
          <Field label="auth_token">
            <input
              aria-label="auth-token"
              className={INPUT_CLS}
              type="password"
              value={typeof data.auth_token === 'string' ? data.auth_token : ''}
              onChange={(e) =>
                onNodeChange(nodeId, { ...data, auth_token: e.target.value })
              }
            />
          </Field>
        </>
      )}

      {kind === 'file-change' && (
        <>
          <Field label="watch_pattern">
            <input
              aria-label="watch-pattern"
              className={INPUT_CLS}
              placeholder=".cronos/tasks/*.md"
              value={typeof data.watch_pattern === 'string' ? data.watch_pattern : ''}
              onChange={(e) =>
                onNodeChange(nodeId, { ...data, watch_pattern: e.target.value })
              }
            />
          </Field>
          <Field label="debounce_seconds (optional)">
            <input
              aria-label="debounce-seconds"
              type="number"
              className={INPUT_CLS}
              placeholder="0.5"
              value={
                typeof data.debounce_seconds === 'number'
                  ? data.debounce_seconds
                  : ''
              }
              onChange={(e) =>
                onNodeChange(nodeId, {
                  ...data,
                  debounce_seconds: e.target.value ? Number(e.target.value) : undefined,
                })
              }
            />
          </Field>
        </>
      )}

      {kind === 'task-state-change' && (
        <Field label="watched_state (optional)">
          <input
            aria-label="watched-state"
            className={INPUT_CLS}
            placeholder="DONE"
            value={typeof data.watched_state === 'string' ? data.watched_state : ''}
            onChange={(e) =>
              onNodeChange(nodeId, { ...data, watched_state: e.target.value })
            }
          />
        </Field>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Edge condition section (shown when a Decision-out edge is selected)
// ---------------------------------------------------------------------------

function EdgeConditionConfig({
  edge,
  onEdgeConditionChange,
}: {
  edge: HarnessEdge;
  onEdgeConditionChange: (edgeId: string, condition: string | null) => void;
}) {
  const condition = edge.condition ?? '';
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-display uppercase tracking-wider text-ink-muted mb-1">
        Edge Condition
      </div>
      <Field label="condition (yes / no / empty = default)">
        <input
          aria-label="edge-condition"
          className={INPUT_CLS}
          value={condition}
          placeholder="yes / no / (empty)"
          onChange={(e) =>
            onEdgeConditionChange(edge.id, e.target.value || null)
          }
        />
      </Field>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Variables section
// ---------------------------------------------------------------------------

function VariablesSection({
  variables,
  onVariableChange,
  onVariableAdd,
  onVariableRemove,
}: {
  variables: Record<string, string>;
  onVariableChange: (key: string, value: string) => void;
  onVariableAdd?: (key: string, value: string) => void;
  onVariableRemove?: (key: string) => void;
}) {
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');

  function handleAdd() {
    if (!newKey.trim()) return;
    onVariableAdd?.(newKey.trim(), newValue);
    setNewKey('');
    setNewValue('');
  }

  return (
    <div className="flex flex-col gap-2">
      {Object.keys(variables).length === 0 ? (
        <div className="text-xs text-ink-muted italic">No variables.</div>
      ) : (
        Object.entries(variables).map(([key, val]) => (
          <div key={key} className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-ink-muted">{key}</span>
              {onVariableRemove && (
                <button
                  type="button"
                  aria-label={`remove-variable-${key}`}
                  className="text-xs text-danger hover:text-danger-bright leading-none px-1"
                  onClick={() => onVariableRemove(key)}
                >
                  ✕
                </button>
              )}
            </div>
            <input
              className={INPUT_CLS}
              value={val}
              onChange={(e) => onVariableChange(key, e.target.value)}
            />
          </div>
        ))
      )}

      {onVariableAdd && (
        <div className="flex flex-col gap-1 pt-1 border-t border-hairline">
          <span className="text-xs text-ink-muted">Add variable</span>
          <input
            aria-label="new-variable-key"
            className={INPUT_CLS}
            placeholder="KEY"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
          />
          <input
            aria-label="new-variable-value"
            className={INPUT_CLS}
            placeholder="value"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
          />
          <button
            type="button"
            aria-label="add-variable"
            className="rounded border border-hairline bg-surface-2 px-2 py-1 text-xs text-ink hover:bg-accent/10"
            onClick={handleAdd}
          >
            Add
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function VariableInspector({
  selectedNode,
  selectedEdge,
  harness,
  onNodeChange,
  onVariableChange,
  onVariableAdd,
  onVariableRemove,
  spaceId,
}: VariableInspectorProps) {
  const panelCls =
    'p-3 border-l border-hairline bg-surface-1 w-56 shrink-0 overflow-y-auto';
  const headerCls =
    'text-xs font-display uppercase tracking-wider text-ink-muted mb-2';

  if (!harness && !selectedNode && !selectedEdge) {
    return (
      <div className={panelCls}>
        <div className="text-xs text-ink-muted italic">No harness loaded.</div>
      </div>
    );
  }

  // Edge selected (decision condition editing)
  if (selectedEdge && !selectedNode) {
    return (
      <div className={panelCls}>
        <EdgeConditionConfig
          edge={selectedEdge}
          onEdgeConditionChange={(edgeId, condition) => {
            // Surface the condition change via a synthetic node-change-like callback;
            // HarnessEditor handles this by mutating the edge state directly.
            // We call onNodeChange with a special __edge__ prefix so the editor
            // can distinguish it from a node change.
            onNodeChange(`__edge__${edgeId}`, { condition });
          }}
        />
      </div>
    );
  }

  // Node selected
  if (selectedNode) {
    const { type, id, data } = selectedNode;

    const titleMap: Record<string, string> = {
      agent: 'Agent Config',
      wait: 'Wait Config',
      aggregator: 'Aggregator Config',
      trigger: 'Trigger Config',
      decision: 'Decision Config',
    };

    return (
      <div className={panelCls}>
        <div className={headerCls}>{titleMap[type] ?? 'Node Config'}</div>
        {type === 'agent' && (
          <AgentConfig nodeId={id} data={data} onNodeChange={onNodeChange} spaceId={spaceId} />
        )}
        {type === 'wait' && (
          <WaitConfig nodeId={id} data={data} onNodeChange={onNodeChange} />
        )}
        {type === 'aggregator' && (
          <AggregatorConfig nodeId={id} data={data} onNodeChange={onNodeChange} />
        )}
        {type === 'trigger' && (
          <TriggerConfig nodeId={id} data={data} onNodeChange={onNodeChange} />
        )}
        {type === 'decision' && (
          <div className="text-xs text-ink-muted italic">
            Select a decision-out edge to edit its condition.
          </div>
        )}
      </div>
    );
  }

  // No node/edge selected — show harness-level variables
  return (
    <div className={panelCls}>
      <div className={headerCls}>Variables</div>
      <VariablesSection
        variables={harness!.variables}
        onVariableChange={onVariableChange}
        onVariableAdd={onVariableAdd}
        onVariableRemove={onVariableRemove}
      />
    </div>
  );
}
