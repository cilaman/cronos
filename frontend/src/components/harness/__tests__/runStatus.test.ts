import { describe, it, expect } from 'vitest';
import type { NodeRunStatus, RunStatusOverlayData } from '../runStatus';
import { runStatusClassName } from '../runStatus';

describe('NodeRunStatus type', () => {
  it('accepts all valid status literals', () => {
    const statuses: NodeRunStatus[] = ['pending', 'in_progress', 'done', 'failed', 'skipped'];
    expect(statuses).toHaveLength(5);
  });
});

describe('RunStatusOverlayData interface', () => {
  it('allows all fields to be optional (no overlay data)', () => {
    const empty: RunStatusOverlayData = {};
    expect(empty.runStatus).toBeUndefined();
    expect(empty.startedAt).toBeUndefined();
    expect(empty.endedAt).toBeUndefined();
    expect(empty.childTaskId).toBeUndefined();
  });

  it('accepts a fully populated overlay data object', () => {
    const full: RunStatusOverlayData = {
      runStatus: 'in_progress',
      startedAt: '2026-06-04T10:00:00Z',
      endedAt: '2026-06-04T10:05:00Z',
      childTaskId: 'task-abc-123',
    };
    expect(full.runStatus).toBe('in_progress');
    expect(full.startedAt).toBe('2026-06-04T10:00:00Z');
    expect(full.endedAt).toBe('2026-06-04T10:05:00Z');
    expect(full.childTaskId).toBe('task-abc-123');
  });

  it('field names are exactly: runStatus, startedAt, endedAt, childTaskId', () => {
    const overlay: RunStatusOverlayData = {
      runStatus: 'done',
      startedAt: '2026-06-04T09:00:00Z',
      endedAt: '2026-06-04T09:30:00Z',
      childTaskId: 'task-xyz-999',
    };
    // Ensure exact field names (downstream iterations depend on these being stable)
    expect(Object.keys(overlay).sort()).toEqual(
      ['childTaskId', 'endedAt', 'runStatus', 'startedAt']
    );
  });
});

describe('runStatusClassName', () => {
  it('returns pulse + ring class for in_progress', () => {
    const cls = runStatusClassName('in_progress');
    expect(cls).toContain('animate-pulse');
    expect(cls).toContain('ring-2');
    expect(cls.length).toBeGreaterThan(0);
  });

  it('returns ring class for done (green)', () => {
    const cls = runStatusClassName('done');
    expect(cls).toContain('ring-2');
    expect(cls).toContain('ring-green-500');
    expect(cls).not.toContain('animate-pulse');
  });

  it('returns desaturate + ring class for failed', () => {
    const cls = runStatusClassName('failed');
    expect(cls).toContain('grayscale');
    expect(cls).toContain('ring-2');
    expect(cls).toContain('ring-red-400');
  });

  it('returns opacity class for skipped', () => {
    const cls = runStatusClassName('skipped');
    expect(cls).toContain('opacity-40');
  });

  it('returns empty string for pending', () => {
    const cls = runStatusClassName('pending');
    expect(cls).toBe('');
  });

  it('returns empty string for undefined', () => {
    const cls = runStatusClassName(undefined);
    expect(cls).toBe('');
  });

  it('returns a string for all defined statuses (no exceptions)', () => {
    const statuses: NodeRunStatus[] = ['pending', 'in_progress', 'done', 'failed', 'skipped'];
    for (const s of statuses) {
      expect(typeof runStatusClassName(s)).toBe('string');
    }
  });

  it('in_progress and done return different classes', () => {
    expect(runStatusClassName('in_progress')).not.toBe(runStatusClassName('done'));
  });

  it('failed desaturation class is different from done class', () => {
    const failedCls = runStatusClassName('failed');
    const doneCls = runStatusClassName('done');
    expect(failedCls).not.toBe(doneCls);
    expect(failedCls).toContain('grayscale');
    expect(doneCls).not.toContain('grayscale');
  });
});
