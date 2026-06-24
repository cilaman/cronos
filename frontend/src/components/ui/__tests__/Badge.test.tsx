import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from '../Badge';
import type { Tone } from '../../../utils/badgeTone';

const ALL_TONES: Tone[] = [
  'running', 'success', 'info', 'warning', 'danger', 'neutral',
  'goal', 'feature', 'fix', 'issue', 'plan', 'ask',
];

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge tone="success">Active</Badge>);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders as a span element', () => {
    const { container } = render(<Badge tone="running">Running</Badge>);
    expect(container.firstChild?.nodeName).toBe('SPAN');
  });

  it('applies base layout classes', () => {
    const { container } = render(<Badge tone="info">Info</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('inline-flex');
    expect(span.className).toContain('items-center');
    expect(span.className).toContain('rounded-sm');
    expect(span.className).toContain('ring-1');
    expect(span.className).toContain('ring-inset');
    expect(span.className).toContain('font-mono');
    expect(span.className).toContain('uppercase');
  });

  it('applies tone-specific classes for running', () => {
    const { container } = render(<Badge tone="running">R</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-running/12');
    expect(span.className).toContain('text-running');
    expect(span.className).toContain('ring-running/30');
  });

  it('applies tone-specific classes for success', () => {
    const { container } = render(<Badge tone="success">S</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-success/12');
    expect(span.className).toContain('text-success');
    expect(span.className).toContain('ring-success/30');
  });

  it('applies tone-specific classes for danger', () => {
    const { container } = render(<Badge tone="danger">D</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-danger/12');
    expect(span.className).toContain('text-danger');
    expect(span.className).toContain('ring-danger/30');
  });

  it('applies tone-specific classes for warning', () => {
    const { container } = render(<Badge tone="warning">W</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-warning/12');
    expect(span.className).toContain('text-warning');
    expect(span.className).toContain('ring-warning/30');
  });

  it('applies tone-specific classes for neutral', () => {
    const { container } = render(<Badge tone="neutral">N</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-neutral/12');
    expect(span.className).toContain('text-neutral');
    expect(span.className).toContain('ring-neutral/30');
  });

  it('applies tone-specific classes for goal', () => {
    const { container } = render(<Badge tone="goal">Goal</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-goal/12');
    expect(span.className).toContain('text-goal');
    expect(span.className).toContain('ring-goal/30');
  });

  it('applies tone-specific classes for feature', () => {
    const { container } = render(<Badge tone="feature">Feature</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-feature/12');
    expect(span.className).toContain('text-feature');
    expect(span.className).toContain('ring-feature/30');
  });

  it('applies tone-specific classes for fix', () => {
    const { container } = render(<Badge tone="fix">Fix</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-fix/12');
    expect(span.className).toContain('text-fix');
    expect(span.className).toContain('ring-fix/30');
  });

  it('applies tone-specific classes for issue', () => {
    const { container } = render(<Badge tone="issue">Issue</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-issue/12');
    expect(span.className).toContain('text-issue');
    expect(span.className).toContain('ring-issue/30');
  });

  it('applies tone-specific classes for plan', () => {
    const { container } = render(<Badge tone="plan">Plan</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-plan/12');
    expect(span.className).toContain('text-plan');
    expect(span.className).toContain('ring-plan/30');
  });

  it('applies tone-specific classes for ask', () => {
    const { container } = render(<Badge tone="ask">Ask</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-ask/12');
    expect(span.className).toContain('text-ask');
    expect(span.className).toContain('ring-ask/30');
  });

  it('applies tone-specific classes for info', () => {
    const { container } = render(<Badge tone="info">Info</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('bg-info/12');
    expect(span.className).toContain('text-info');
    expect(span.className).toContain('ring-info/30');
  });

  it('merges extra className', () => {
    const { container } = render(<Badge tone="success" className="mt-1">X</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain('mt-1');
    expect(span.className).toContain('bg-success/12');
  });

  it('renders without children', () => {
    const { container } = render(<Badge tone="neutral" />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it('renders React node children', () => {
    render(
      <Badge tone="running">
        <span data-testid="icon">•</span>
        <span>Status</span>
      </Badge>,
    );
    expect(screen.getByTestId('icon')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
  });

  it('renders with all 12 tones without error', () => {
    for (const tone of ALL_TONES) {
      const { unmount } = render(<Badge tone={tone}>{tone}</Badge>);
      expect(screen.getByText(tone)).toBeInTheDocument();
      unmount();
    }
  });

  it('TONE_CLASSES covers all 12 tones', async () => {
    // Dynamically import the module to introspect TONE_CLASSES indirectly
    // by verifying that each tone produces distinct bg/text/ring classes
    const expectedTones: Tone[] = [
      'running', 'success', 'info', 'warning', 'danger', 'neutral',
      'goal', 'feature', 'fix', 'issue', 'plan', 'ask',
    ];
    expect(expectedTones).toHaveLength(12);
    // Verify each tone produces tone-specific classes in the rendered output
    for (const tone of expectedTones) {
      const { container, unmount } = render(<Badge tone={tone}>{tone}</Badge>);
      const span = container.firstChild as HTMLElement;
      expect(span.className).toContain(`bg-${tone}/12`);
      expect(span.className).toContain(`text-${tone}`);
      unmount();
    }
  });
});
