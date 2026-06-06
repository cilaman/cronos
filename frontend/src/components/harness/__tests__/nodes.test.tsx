import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AgentNode } from '../AgentNode';
import { TriggerNode } from '../TriggerNode';
import { DecisionNode } from '../DecisionNode';
import { WaitNode } from '../WaitNode';
import { AggregatorNode } from '../AggregatorNode';
import { nodeTypes } from '../nodeTypes';

vi.mock('@xyflow/react', () => ({
  Handle: ({ type, position, id }: { type: string; position: string; id?: string }) =>
    <div data-testid={`handle-${type}-${id ?? position}`} />,
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
}));

// Minimal NodeProps compatible stub for tests
function makeProps(data: Record<string, unknown>) {
  return {
    id: 'test-node',
    data,
    type: 'test',
    selected: false,
    isConnectable: true,
    zIndex: 0,
    xPos: 0,
    yPos: 0,
    dragging: false,
    dragHandle: undefined,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
  } as unknown as Parameters<typeof AgentNode>[0];
}

describe('AgentNode', () => {
  it('renders with label and agent_ref', () => {
    render(<AgentNode {...makeProps({ label: 'My Agent', agent_ref: 'claude-agent' })} />);
    expect(screen.getByText('AGENT')).toBeTruthy();
    expect(screen.getByText('My Agent')).toBeTruthy();
    expect(screen.getByText('claude-agent')).toBeTruthy();
  });

  it('has input and output handles', () => {
    render(<AgentNode {...makeProps({ label: 'Agent' })} />);
    expect(screen.getByTestId('handle-target-in')).toBeTruthy();
    expect(screen.getByTestId('handle-source-out')).toBeTruthy();
  });
});

describe('TriggerNode', () => {
  it('renders with label', () => {
    render(<TriggerNode {...makeProps({ label: 'Start' })} />);
    expect(screen.getByText('TRIGGER')).toBeTruthy();
    expect(screen.getByText('Start')).toBeTruthy();
  });

  it('has only output handle (no input handle)', () => {
    render(<TriggerNode {...makeProps({ label: 'Start' })} />);
    expect(screen.getByTestId('handle-source-out')).toBeTruthy();
    expect(screen.queryByTestId('handle-target-in')).toBeNull();
  });
});

describe('DecisionNode', () => {
  it('renders with label', () => {
    render(<DecisionNode {...makeProps({ label: 'Branch?' })} />);
    expect(screen.getByText('DECISION')).toBeTruthy();
    expect(screen.getByText('Branch?')).toBeTruthy();
  });

  it('has input handle and two output handles (yes/no)', () => {
    render(<DecisionNode {...makeProps({ label: 'Branch?' })} />);
    expect(screen.getByTestId('handle-target-in')).toBeTruthy();
    expect(screen.getByTestId('handle-source-yes')).toBeTruthy();
    expect(screen.getByTestId('handle-source-no')).toBeTruthy();
  });
});

describe('WaitNode', () => {
  it('renders with label', () => {
    render(<WaitNode {...makeProps({ label: 'Pause' })} />);
    expect(screen.getByText('WAIT')).toBeTruthy();
    expect(screen.getByText('Pause')).toBeTruthy();
  });

  it('has input and output handles', () => {
    render(<WaitNode {...makeProps({ label: 'Pause' })} />);
    expect(screen.getByTestId('handle-target-in')).toBeTruthy();
    expect(screen.getByTestId('handle-source-out')).toBeTruthy();
  });
});

describe('AggregatorNode', () => {
  it('renders with label', () => {
    render(<AggregatorNode {...makeProps({ label: 'Merge' })} />);
    expect(screen.getByText('AGGREGATOR')).toBeTruthy();
    expect(screen.getByText('Merge')).toBeTruthy();
  });

  it('has multiple input handles and one output handle', () => {
    render(<AggregatorNode {...makeProps({ label: 'Merge', inputCount: 3 })} />);
    expect(screen.getByTestId('handle-target-in-0')).toBeTruthy();
    expect(screen.getByTestId('handle-target-in-1')).toBeTruthy();
    expect(screen.getByTestId('handle-target-in-2')).toBeTruthy();
    expect(screen.getByTestId('handle-source-out')).toBeTruthy();
  });
});

describe('nodeTypes', () => {
  it('exports all 5 node types', () => {
    expect(nodeTypes).toHaveProperty('agent');
    expect(nodeTypes).toHaveProperty('trigger');
    expect(nodeTypes).toHaveProperty('decision');
    expect(nodeTypes).toHaveProperty('wait');
    expect(nodeTypes).toHaveProperty('aggregator');
  });

  it('maps each key to the correct component', () => {
    expect(nodeTypes.agent).toBe(AgentNode);
    expect(nodeTypes.trigger).toBe(TriggerNode);
    expect(nodeTypes.decision).toBe(DecisionNode);
    expect(nodeTypes.wait).toBe(WaitNode);
    expect(nodeTypes.aggregator).toBe(AggregatorNode);
  });
});
