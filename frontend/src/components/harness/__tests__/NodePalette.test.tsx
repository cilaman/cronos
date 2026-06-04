import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { fireEvent } from '@testing-library/react';
import { NodePalette } from '../NodePalette';

describe('NodePalette', () => {
  it('renders all 5 palette entries', () => {
    render(<NodePalette />);
    expect(screen.getByText('AGENT')).toBeTruthy();
    expect(screen.getByText('TRIGGER')).toBeTruthy();
    expect(screen.getByText('DECISION')).toBeTruthy();
    expect(screen.getByText('WAIT')).toBeTruthy();
    expect(screen.getByText('AGGREGATOR')).toBeTruthy();
  });

  it('calls dataTransfer.setData with application/reactflow and nodeType on dragstart for each type', () => {
    render(<NodePalette />);

    const nodeTypes = ['agent', 'trigger', 'decision', 'wait', 'aggregator'];

    for (const nodeType of nodeTypes) {
      const entry = screen.getByText(nodeType.toUpperCase());
      const setData = vi.fn();
      const dataTransfer = { setData, effectAllowed: '' };

      fireEvent.dragStart(entry, { dataTransfer });

      expect(setData).toHaveBeenCalledWith('application/reactflow', nodeType);
    }
  });

  it('sets effectAllowed to move on dragstart', () => {
    render(<NodePalette />);

    const entry = screen.getByText('AGENT');
    const setData = vi.fn();
    const dataTransfer = { setData, effectAllowed: '' };

    fireEvent.dragStart(entry, { dataTransfer });

    expect(dataTransfer.effectAllowed).toBe('move');
  });
});
