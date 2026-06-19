import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VariableInspector } from '../VariableInspector';
import type { HarnessNode, HarnessEdge, Harness } from '../../../types';

// ---------------------------------------------------------------------------
// Mock api module for datalist tests
// ---------------------------------------------------------------------------
vi.mock('../../../api', () => ({
  api: {
    spaceTools: vi.fn(),
  },
}));

import { api } from '../../../api';

// ---------------------------------------------------------------------------
// Fixture helpers
// ---------------------------------------------------------------------------

function makeNode(
  type: HarnessNode['type'],
  data: Record<string, unknown> = {},
): HarnessNode {
  return {
    id: 'node-1',
    type,
    label: 'Test Node',
    position: { x: 0, y: 0 },
    ports: {},
    data,
  };
}

function makeEdge(condition?: string | null): HarnessEdge {
  return {
    id: 'edge-1',
    source: { node_id: 'n1', port_id: 'yes' },
    target: { node_id: 'n2', port_id: 'in' },
    condition: condition ?? null,
  };
}

function makeHarness(variables: Record<string, string> = {}): Harness {
  return { name: 'h', nodes: [], edges: [], variables };
}

// ---------------------------------------------------------------------------
// Agent node
// ---------------------------------------------------------------------------

describe('VariableInspector — agent node', () => {
  it('renders agent_ref and prompt_template fields', () => {
    const node = makeNode('agent', { agent_ref: 'my-agent', prompt_template: 'Do something' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('agent_ref')).toBeTruthy();
    expect(screen.getByLabelText('prompt_template')).toBeTruthy();

    expect((screen.getByLabelText('agent_ref') as HTMLInputElement).value).toBe('my-agent');
    expect((screen.getByLabelText('prompt_template') as HTMLTextAreaElement).value).toBe(
      'Do something',
    );
  });

  it('calls onNodeChange with data.agent_ref on change', () => {
    const onNodeChange = vi.fn();
    const node = makeNode('agent', { agent_ref: 'old', prompt_template: 'prompt' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={onNodeChange}
        onVariableChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText('agent_ref'), { target: { value: 'new-agent' } });
    expect(onNodeChange).toHaveBeenCalledWith('node-1', {
      agent_ref: 'new-agent',
      prompt_template: 'prompt',
    });
  });

  it('calls onNodeChange with data.prompt_template on textarea change', () => {
    const onNodeChange = vi.fn();
    const node = makeNode('agent', { agent_ref: 'ref', prompt_template: 'original' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={onNodeChange}
        onVariableChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText('prompt_template'), { target: { value: 'updated' } });
    expect(onNodeChange).toHaveBeenCalledWith('node-1', {
      agent_ref: 'ref',
      prompt_template: 'updated',
    });
  });
});

// ---------------------------------------------------------------------------
// Wait node
// ---------------------------------------------------------------------------

describe('VariableInspector — wait node', () => {
  it('renders mode dropdown defaulting to human', () => {
    const node = makeNode('wait', {});
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    const select = screen.getByLabelText('wait-mode') as HTMLSelectElement;
    expect(select.value).toBe('human');
  });

  it('renders max_wait_seconds when mode=human', () => {
    const node = makeNode('wait', { mode: 'human', max_wait_seconds: 300 });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('max_wait_seconds')).toBeTruthy();
    expect((screen.getByLabelText('max_wait_seconds') as HTMLInputElement).value).toBe('300');
  });

  it('renders duration_seconds when mode=timed', () => {
    const node = makeNode('wait', { mode: 'timed', duration_seconds: 60 });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('duration_seconds')).toBeTruthy();
  });

  it('calls onNodeChange when mode changes', () => {
    const onNodeChange = vi.fn();
    const node = makeNode('wait', { mode: 'human' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={onNodeChange}
        onVariableChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText('wait-mode'), { target: { value: 'timed' } });
    expect(onNodeChange).toHaveBeenCalledWith('node-1', { mode: 'timed' });
  });
});

// ---------------------------------------------------------------------------
// Aggregator node
// ---------------------------------------------------------------------------

describe('VariableInspector — aggregator node', () => {
  it('renders mode dropdown defaulting to all', () => {
    const node = makeNode('aggregator', {});
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect((screen.getByLabelText('aggregator-mode') as HTMLSelectElement).value).toBe('all');
  });

  it('calls onNodeChange with mode=any', () => {
    const onNodeChange = vi.fn();
    const node = makeNode('aggregator', { mode: 'all' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={onNodeChange}
        onVariableChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText('aggregator-mode'), { target: { value: 'any' } });
    expect(onNodeChange).toHaveBeenCalledWith('node-1', { mode: 'any' });
  });
});

// ---------------------------------------------------------------------------
// Trigger node
// ---------------------------------------------------------------------------

describe('VariableInspector — trigger node', () => {
  it('renders kind dropdown defaulting to cron', () => {
    const node = makeNode('trigger', {});
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect((screen.getByLabelText('trigger-kind') as HTMLSelectElement).value).toBe('cron');
  });

  it('renders cron expression field when kind=cron', () => {
    const node = makeNode('trigger', { expression: '0 * * * *' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect((screen.getByLabelText('cron-expression') as HTMLInputElement).value).toBe(
      '0 * * * *',
    );
  });

  it('renders webhook fields when kind=webhook', () => {
    const node = makeNode('trigger', { kind: 'webhook', webhook_path: '/hook', auth_token: 'secret' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('webhook-path')).toBeTruthy();
    expect(screen.getByLabelText('auth-token')).toBeTruthy();
  });

  it('renders file-change fields when kind=file-change', () => {
    const node = makeNode('trigger', { kind: 'file-change', watch_pattern: '**/*.md' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('watch-pattern')).toBeTruthy();
  });

  it('renders task-state-change field when kind=task-state-change', () => {
    const node = makeNode('trigger', { kind: 'task-state-change', watched_state: 'DONE' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect((screen.getByLabelText('watched-state') as HTMLInputElement).value).toBe('DONE');
  });
});

// ---------------------------------------------------------------------------
// Edge condition
// ---------------------------------------------------------------------------

describe('VariableInspector — edge condition', () => {
  it('renders edge-condition input when an edge is selected', () => {
    const edge = makeEdge('yes');
    render(
      <VariableInspector
        selectedNode={null}
        selectedEdge={edge}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect((screen.getByLabelText('edge-condition') as HTMLInputElement).value).toBe('yes');
  });

  it('calls onNodeChange with __edge__ prefix when condition changes', () => {
    const onNodeChange = vi.fn();
    const edge = makeEdge(null);
    render(
      <VariableInspector
        selectedNode={null}
        selectedEdge={edge}
        harness={makeHarness()}
        onNodeChange={onNodeChange}
        onVariableChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText('edge-condition'), { target: { value: 'no' } });
    expect(onNodeChange).toHaveBeenCalledWith('__edge__edge-1', { condition: 'no' });
  });

  it('sends null condition when input is cleared', () => {
    const onNodeChange = vi.fn();
    const edge = makeEdge('yes');
    render(
      <VariableInspector
        selectedNode={null}
        selectedEdge={edge}
        harness={makeHarness()}
        onNodeChange={onNodeChange}
        onVariableChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText('edge-condition'), { target: { value: '' } });
    expect(onNodeChange).toHaveBeenCalledWith('__edge__edge-1', { condition: null });
  });
});

// ---------------------------------------------------------------------------
// Variables panel
// ---------------------------------------------------------------------------

describe('VariableInspector — variables panel', () => {
  it('shows harness variables when no node/edge selected', () => {
    const harness = makeHarness({ ENV: 'prod', TIMEOUT: '60' });
    render(
      <VariableInspector
        selectedNode={null}
        harness={harness}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect(screen.getByText('ENV')).toBeTruthy();
    expect(screen.getByText('TIMEOUT')).toBeTruthy();
  });

  it('calls onVariableChange when a variable input changes', () => {
    const onVariableChange = vi.fn();
    const harness = makeHarness({ MY_VAR: 'old' });
    render(
      <VariableInspector
        selectedNode={null}
        harness={harness}
        onNodeChange={vi.fn()}
        onVariableChange={onVariableChange}
      />,
    );
    const inputs = screen.getAllByRole('textbox');
    // First input that has value 'old' is the variable input
    const varInput = inputs.find((el) => (el as HTMLInputElement).value === 'old')!;
    fireEvent.change(varInput, { target: { value: 'new' } });
    expect(onVariableChange).toHaveBeenCalledWith('MY_VAR', 'new');
  });

  it('calls onVariableAdd when Add button clicked with key + value', () => {
    const onVariableAdd = vi.fn();
    const harness = makeHarness({});
    render(
      <VariableInspector
        selectedNode={null}
        harness={harness}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
        onVariableAdd={onVariableAdd}
      />,
    );
    fireEvent.change(screen.getByLabelText('new-variable-key'), {
      target: { value: 'NEW_KEY' },
    });
    fireEvent.change(screen.getByLabelText('new-variable-value'), {
      target: { value: 'my-value' },
    });
    fireEvent.click(screen.getByLabelText('add-variable'));
    expect(onVariableAdd).toHaveBeenCalledWith('NEW_KEY', 'my-value');
  });

  it('calls onVariableRemove when remove button clicked', () => {
    const onVariableRemove = vi.fn();
    const harness = makeHarness({ DEL_ME: 'val' });
    render(
      <VariableInspector
        selectedNode={null}
        harness={harness}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
        onVariableRemove={onVariableRemove}
      />,
    );
    fireEvent.click(screen.getByLabelText('remove-variable-DEL_ME'));
    expect(onVariableRemove).toHaveBeenCalledWith('DEL_ME');
  });

  it('shows empty state when harness is null and no node/edge selected', () => {
    render(
      <VariableInspector
        selectedNode={null}
        harness={null}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );
    expect(screen.getByText('No harness loaded.')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// R6: agent_ref datalist (spaceId prop)
// ---------------------------------------------------------------------------

describe('VariableInspector — agent_ref datalist (R6)', () => {
  beforeEach(() => {
    vi.mocked(api.spaceTools).mockReset();
  });

  it('renders datalist options from api.spaceTools when spaceId is set', async () => {
    vi.mocked(api.spaceTools).mockResolvedValue({
      space_id: 'space-1',
      agents: [
        { name: 'my-agent', path: 'agents/my-agent.md', description: null, scope: 'space', modified_at: '' },
      ],
      skills: [
        { name: 'my-plugin:my-skill', path: 'skills/my-skill.md', description: null, scope: 'plugin', modified_at: '' },
      ],
      commands: [],
      context_files: [],
      hooks: [],
      permissions: [],
      has_claude_md: false,
      adopted: [],
    });

    const node = makeNode('agent', { agent_ref: '', prompt_template: '' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
        spaceId="space-1"
      />,
    );

    // Wait for the async spaceTools call to resolve and options to appear
    await waitFor(() => {
      const datalist = document.getElementById('agent-ref-options');
      expect(datalist).toBeTruthy();
      const options = datalist!.querySelectorAll('option');
      const values = Array.from(options).map((o) => o.getAttribute('value'));
      expect(values).toContain('my-agent');
      expect(values).toContain('my-plugin:my-skill');
    });
  });

  it('agent_ref input has list attribute referencing the datalist', async () => {
    vi.mocked(api.spaceTools).mockResolvedValue({
      space_id: 'space-1',
      agents: [
        { name: 'scout', path: '', description: null, scope: 'space', modified_at: '' },
      ],
      skills: [],
      commands: [],
      context_files: [],
      hooks: [],
      permissions: [],
      has_claude_md: false,
      adopted: [],
    });

    const node = makeNode('agent', { agent_ref: '', prompt_template: '' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
        spaceId="space-1"
      />,
    );

    const input = screen.getByLabelText('agent_ref') as HTMLInputElement;
    expect(input.getAttribute('list')).toBe('agent-ref-options');
  });

  it('free-text still updates agent_ref when spaceId is provided', async () => {
    vi.mocked(api.spaceTools).mockResolvedValue({
      space_id: 'space-1',
      agents: [],
      skills: [],
      commands: [],
      context_files: [],
      hooks: [],
      permissions: [],
      has_claude_md: false,
      adopted: [],
    });

    const onNodeChange = vi.fn();
    const node = makeNode('agent', { agent_ref: '', prompt_template: '' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={onNodeChange}
        onVariableChange={vi.fn()}
        spaceId="space-1"
      />,
    );

    fireEvent.change(screen.getByLabelText('agent_ref'), { target: { value: 'custom-agent' } });
    expect(onNodeChange).toHaveBeenCalledWith('node-1', {
      agent_ref: 'custom-agent',
      prompt_template: '',
    });
  });

  it('does not crash and leaves datalist empty when spaceId is undefined', () => {
    const node = makeNode('agent', { agent_ref: '', prompt_template: '' });
    render(
      <VariableInspector
        selectedNode={node}
        harness={makeHarness()}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />,
    );

    // api.spaceTools should NOT have been called
    expect(api.spaceTools).not.toHaveBeenCalled();

    // datalist should be present but empty
    const datalist = document.getElementById('agent-ref-options');
    expect(datalist).toBeTruthy();
    expect(datalist!.querySelectorAll('option').length).toBe(0);
  });
});
