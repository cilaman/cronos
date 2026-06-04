import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VariableInspector } from '../VariableInspector';
import type { HarnessNode, Harness } from '../../../types';

function makeAgentNode(config: Record<string, unknown> = {}): HarnessNode {
  return {
    id: 'node-1',
    type: 'agent',
    label: 'My Agent',
    position: { x: 0, y: 0 },
    ports: [],
    config,
  };
}

function makeNonAgentNode(type: 'trigger' | 'decision' | 'wait' | 'aggregator', config: Record<string, unknown> = {}): HarnessNode {
  return {
    id: 'node-2',
    type,
    label: 'A Node',
    position: { x: 0, y: 0 },
    ports: [],
    config,
  };
}

function makeHarness(variables: Record<string, string> = {}): Harness {
  return {
    name: 'test-harness',
    nodes: [],
    edges: [],
    variables,
  };
}

describe('VariableInspector', () => {
  it('shows agent_ref and prompt fields when agent node selected', () => {
    const node = makeAgentNode({ agent_ref: 'my-agent', prompt: 'Do something' });
    const harness = makeHarness();
    render(
      <VariableInspector
        selectedNode={node}
        harness={harness}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />
    );
    expect(screen.getByLabelText('agent_ref')).toBeTruthy();
    expect(screen.getByLabelText('prompt')).toBeTruthy();
    // Check values are set
    const agentRefInput = screen.getByLabelText('agent_ref') as HTMLInputElement;
    expect(agentRefInput.value).toBe('my-agent');
    const promptTextarea = screen.getByLabelText('prompt') as HTMLTextAreaElement;
    expect(promptTextarea.value).toBe('Do something');
  });

  it('shows generic config when non-agent node selected', () => {
    const node = makeNonAgentNode('trigger', { timeout: '30s', retries: '3' });
    const harness = makeHarness();
    render(
      <VariableInspector
        selectedNode={node}
        harness={harness}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />
    );
    expect(screen.getByText('timeout:')).toBeTruthy();
    expect(screen.getByText('30s')).toBeTruthy();
    expect(screen.getByText('retries:')).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
  });

  it('shows harness variables when no node selected', () => {
    const harness = makeHarness({ ENV: 'production', TIMEOUT: '60' });
    render(
      <VariableInspector
        selectedNode={null}
        harness={harness}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />
    );
    expect(screen.getByText('ENV')).toBeTruthy();
    expect(screen.getByText('TIMEOUT')).toBeTruthy();
  });

  it('shows empty state when harness is null and no node selected', () => {
    render(
      <VariableInspector
        selectedNode={null}
        harness={null}
        onNodeChange={vi.fn()}
        onVariableChange={vi.fn()}
      />
    );
    expect(screen.getByText('No harness loaded.')).toBeTruthy();
  });

  it('calls onNodeChange when agent_ref field changes', () => {
    const node = makeAgentNode({ agent_ref: 'old-agent', prompt: 'original prompt' });
    const harness = makeHarness();
    const onNodeChange = vi.fn();
    render(
      <VariableInspector
        selectedNode={node}
        harness={harness}
        onNodeChange={onNodeChange}
        onVariableChange={vi.fn()}
      />
    );
    const input = screen.getByLabelText('agent_ref') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'new-agent' } });
    expect(onNodeChange).toHaveBeenCalledWith('node-1', {
      agent_ref: 'new-agent',
      prompt: 'original prompt',
    });
  });
});
