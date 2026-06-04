/**
 * nodeRunStatusStyling.test.tsx
 *
 * I2 requirement: all five node components read data.runStatus and append the
 * corresponding Tailwind class from runStatusClassName().
 *
 * R8 invariant: when runStatus is absent (legacy harness fixture), the rendered
 * className must be identical to what the component produced before I2 (no diff).
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { AgentNode } from '../AgentNode';
import { TriggerNode } from '../TriggerNode';
import { DecisionNode } from '../DecisionNode';
import { AggregatorNode } from '../AggregatorNode';
import { WaitNode } from '../WaitNode';
import type { NodeRunStatus } from '../runStatus';

vi.mock('@xyflow/react', () => ({
  Handle: ({ type, position, id }: { type: string; position: string; id?: string }) =>
    <div data-testid={`handle-${type}-${id ?? position}`} />,
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
}));

// Minimal NodeProps compatible stub — reuses same pattern from nodes.test.tsx
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

// The base className all node wrappers share (no status classes appended)
const BASE_CLASS = 'rounded border border-hairline bg-surface-2 px-3 py-2 text-xs min-w-[120px]';

// Status → expected appended class fragment
const STATUS_CLASS_MAP: Record<NodeRunStatus, string> = {
  in_progress: 'animate-pulse ring-2 ring-blue-400 ring-offset-1',
  done: 'ring-2 ring-green-500 ring-offset-1',
  failed: 'grayscale ring-2 ring-red-400 ring-offset-1',
  skipped: 'opacity-40',
  pending: '',
};

// Helper: get the root wrapper div's className from a rendered node
function getRootClass(container: HTMLElement): string {
  // The first div inside container is the node wrapper
  const wrapper = container.firstElementChild as HTMLElement;
  return wrapper?.className ?? '';
}

// ──────────────────────────────────────────────────────────────────────────────
// R8 invariant: no className diff when runStatus is absent (legacy harness)
// ──────────────────────────────────────────────────────────────────────────────

describe('R8 invariant — no className diff for legacy harnesses (no runStatus)', () => {
  it('AgentNode: className unchanged when runStatus absent', () => {
    const { container } = render(
      <AgentNode {...makeProps({ label: 'Agent' })} />
    );
    expect(getRootClass(container)).toBe(BASE_CLASS);
  });

  it('TriggerNode: className unchanged when runStatus absent', () => {
    const { container } = render(
      <TriggerNode {...makeProps({ label: 'Start' })} />
    );
    expect(getRootClass(container)).toBe(BASE_CLASS);
  });

  it('DecisionNode: className unchanged when runStatus absent', () => {
    const { container } = render(
      <DecisionNode {...makeProps({ label: 'Branch?' })} />
    );
    expect(getRootClass(container)).toBe(BASE_CLASS);
  });

  it('AggregatorNode: className unchanged when runStatus absent', () => {
    const { container } = render(
      <AggregatorNode {...makeProps({ label: 'Merge' })} />
    );
    expect(getRootClass(container)).toBe(BASE_CLASS);
  });

  it('WaitNode: className unchanged when runStatus absent', () => {
    const { container } = render(
      <WaitNode {...makeProps({ label: 'Pause' })} />
    );
    expect(getRootClass(container)).toBe(BASE_CLASS);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// AgentNode status styling
// ──────────────────────────────────────────────────────────────────────────────

describe('AgentNode status styling', () => {
  it('pending: no extra class appended (same as base)', () => {
    const { container } = render(
      <AgentNode {...makeProps({ label: 'Agent', runStatus: 'pending' })} />
    );
    expect(getRootClass(container)).toBe(BASE_CLASS);
  });

  it('in_progress: appends animate-pulse ring-2 ring-blue-400 ring-offset-1', () => {
    const { container } = render(
      <AgentNode {...makeProps({ label: 'Agent', runStatus: 'in_progress' })} />
    );
    const cls = getRootClass(container);
    expect(cls).toContain('animate-pulse');
    expect(cls).toContain('ring-2');
    expect(cls).toContain('ring-blue-400');
    expect(cls).toContain('ring-offset-1');
    expect(cls).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.in_progress}`);
  });

  it('done: appends ring-2 ring-green-500 ring-offset-1', () => {
    const { container } = render(
      <AgentNode {...makeProps({ label: 'Agent', runStatus: 'done' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.done}`);
  });

  it('failed: appends grayscale ring-2 ring-red-400 ring-offset-1', () => {
    const { container } = render(
      <AgentNode {...makeProps({ label: 'Agent', runStatus: 'failed' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.failed}`);
  });

  it('skipped: appends opacity-40', () => {
    const { container } = render(
      <AgentNode {...makeProps({ label: 'Agent', runStatus: 'skipped' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.skipped}`);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// TriggerNode status styling
// ──────────────────────────────────────────────────────────────────────────────

describe('TriggerNode status styling', () => {
  it('in_progress: appends animate-pulse ring classes', () => {
    const { container } = render(
      <TriggerNode {...makeProps({ label: 'Start', runStatus: 'in_progress' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.in_progress}`);
  });

  it('done: appends green ring classes', () => {
    const { container } = render(
      <TriggerNode {...makeProps({ label: 'Start', runStatus: 'done' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.done}`);
  });

  it('failed: appends grayscale + red ring', () => {
    const { container } = render(
      <TriggerNode {...makeProps({ label: 'Start', runStatus: 'failed' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.failed}`);
  });

  it('skipped: appends opacity-40', () => {
    const { container } = render(
      <TriggerNode {...makeProps({ label: 'Start', runStatus: 'skipped' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.skipped}`);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// DecisionNode status styling
// ──────────────────────────────────────────────────────────────────────────────

describe('DecisionNode status styling', () => {
  it('in_progress: appends animate-pulse ring classes', () => {
    const { container } = render(
      <DecisionNode {...makeProps({ label: 'Branch?', runStatus: 'in_progress' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.in_progress}`);
  });

  it('done: appends green ring', () => {
    const { container } = render(
      <DecisionNode {...makeProps({ label: 'Branch?', runStatus: 'done' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.done}`);
  });

  it('failed: appends grayscale + red ring', () => {
    const { container } = render(
      <DecisionNode {...makeProps({ label: 'Branch?', runStatus: 'failed' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.failed}`);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// AggregatorNode status styling
// ──────────────────────────────────────────────────────────────────────────────

describe('AggregatorNode status styling', () => {
  it('in_progress: appends animate-pulse ring classes', () => {
    const { container } = render(
      <AggregatorNode {...makeProps({ label: 'Merge', runStatus: 'in_progress' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.in_progress}`);
  });

  it('done: appends green ring', () => {
    const { container } = render(
      <AggregatorNode {...makeProps({ label: 'Merge', runStatus: 'done' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.done}`);
  });

  it('skipped: appends opacity-40', () => {
    const { container } = render(
      <AggregatorNode {...makeProps({ label: 'Merge', runStatus: 'skipped' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.skipped}`);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// WaitNode status styling
// ──────────────────────────────────────────────────────────────────────────────

describe('WaitNode status styling', () => {
  it('in_progress: appends animate-pulse ring classes', () => {
    const { container } = render(
      <WaitNode {...makeProps({ label: 'Pause', runStatus: 'in_progress' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.in_progress}`);
  });

  it('done: appends green ring', () => {
    const { container } = render(
      <WaitNode {...makeProps({ label: 'Pause', runStatus: 'done' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.done}`);
  });

  it('failed: appends grayscale + red ring', () => {
    const { container } = render(
      <WaitNode {...makeProps({ label: 'Pause', runStatus: 'failed' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.failed}`);
  });

  it('skipped: appends opacity-40', () => {
    const { container } = render(
      <WaitNode {...makeProps({ label: 'Pause', runStatus: 'skipped' })} />
    );
    expect(getRootClass(container)).toBe(`${BASE_CLASS} ${STATUS_CLASS_MAP.skipped}`);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Cross-node: pending status produces same class as absent runStatus
// ──────────────────────────────────────────────────────────────────────────────

describe('pending status is equivalent to absent runStatus (all nodes)', () => {
  it('AgentNode: pending class === no runStatus class', () => {
    const { container: withPending } = render(
      <AgentNode {...makeProps({ label: 'A', runStatus: 'pending' })} />
    );
    const { container: withoutStatus } = render(
      <AgentNode {...makeProps({ label: 'A' })} />
    );
    expect(getRootClass(withPending)).toBe(getRootClass(withoutStatus));
  });

  it('TriggerNode: pending class === no runStatus class', () => {
    const { container: withPending } = render(
      <TriggerNode {...makeProps({ label: 'T', runStatus: 'pending' })} />
    );
    const { container: withoutStatus } = render(
      <TriggerNode {...makeProps({ label: 'T' })} />
    );
    expect(getRootClass(withPending)).toBe(getRootClass(withoutStatus));
  });
});
