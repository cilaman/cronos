import { describe, it, expect } from 'vitest';
import {
  getTonePriority,
  getToneTaskState,
  getToneType,
  getToneMode,
  getToneRunStatus,
  getToneFeatureState,
  type Tone,
} from '../badgeTone';
import type { TaskState, FeatureState, AgentMode, TaskType } from '../../types';

// Helper: assert the returned value is a valid Tone
const VALID_TONES = new Set<string>([
  'running', 'success', 'info', 'warning', 'danger', 'neutral',
  'goal', 'feature', 'fix', 'issue', 'plan', 'ask',
]);

function assertTone(value: Tone): void {
  expect(VALID_TONES.has(value)).toBe(true);
}

// ── getTonePriority ────────────────────────────────────────────────────────────

describe('getTonePriority', () => {
  it('P1 → danger', () => {
    const result = getTonePriority(1);
    expect(result).toBe('danger');
    assertTone(result);
  });

  it('P2 → warning', () => {
    const result = getTonePriority(2);
    expect(result).toBe('warning');
    assertTone(result);
  });

  it('P3 → info', () => {
    const result = getTonePriority(3);
    expect(result).toBe('info');
    assertTone(result);
  });

  it('P4 → success', () => {
    const result = getTonePriority(4);
    expect(result).toBe('success');
    assertTone(result);
  });

  it('P5 → neutral', () => {
    const result = getTonePriority(5);
    expect(result).toBe('neutral');
    assertTone(result);
  });

  it('returns a valid Tone for all priorities', () => {
    ([1, 2, 3, 4, 5] as Array<1 | 2 | 3 | 4 | 5>).forEach((p) => {
      assertTone(getTonePriority(p));
    });
  });
});

// ── getToneTaskState ───────────────────────────────────────────────────────────

describe('getToneTaskState', () => {
  const cases: Array<[TaskState, Tone]> = [
    ['backlog', 'neutral'],
    ['active', 'running'],
    ['waiting', 'warning'],
    ['done', 'success'],
    ['archived', 'neutral'],
  ];

  for (const [state, expectedTone] of cases) {
    it(`${state} → ${expectedTone}`, () => {
      const result = getToneTaskState(state);
      expect(result).toBe(expectedTone);
      assertTone(result);
    });
  }

  it('returns a valid Tone for all TaskState values', () => {
    const allStates: TaskState[] = ['backlog', 'active', 'waiting', 'done', 'archived'];
    allStates.forEach((s) => assertTone(getToneTaskState(s)));
  });
});

// ── getToneType ────────────────────────────────────────────────────────────────

describe('getToneType', () => {
  const cases: Array<[TaskType, Tone]> = [
    ['task', 'neutral'],
    ['goal', 'goal'],
    ['feature', 'feature'],
    ['fix', 'fix'],
    ['issue', 'issue'],
  ];

  for (const [type, expectedTone] of cases) {
    it(`${type} → ${expectedTone}`, () => {
      const result = getToneType(type);
      expect(result).toBe(expectedTone);
      assertTone(result);
    });
  }

  it('returns a valid Tone for all TaskType values', () => {
    const allTypes: TaskType[] = ['task', 'goal', 'issue', 'feature', 'fix'];
    allTypes.forEach((t) => assertTone(getToneType(t)));
  });
});

// ── getToneMode ────────────────────────────────────────────────────────────────

describe('getToneMode', () => {
  const cases: Array<[AgentMode, Tone]> = [
    ['auto', 'running'],
    ['plan', 'plan'],
    ['ask', 'ask'],
  ];

  for (const [mode, expectedTone] of cases) {
    it(`${mode} → ${expectedTone}`, () => {
      const result = getToneMode(mode);
      expect(result).toBe(expectedTone);
      assertTone(result);
    });
  }

  it('returns a valid Tone for all AgentMode values', () => {
    const allModes: AgentMode[] = ['auto', 'plan', 'ask'];
    allModes.forEach((m) => assertTone(getToneMode(m)));
  });
});

// ── getToneRunStatus ───────────────────────────────────────────────────────────

describe('getToneRunStatus', () => {
  const cases: Array<[string, Tone]> = [
    ['running', 'running'],
    ['done', 'success'],
    ['success', 'success'],
    ['failed', 'danger'],
    ['error', 'danger'],
    ['cancelled', 'neutral'],
    ['waiting', 'warning'],
    ['pending', 'neutral'],
    ['blocked', 'danger'],
    ['skipped', 'neutral'],
  ];

  for (const [status, expectedTone] of cases) {
    it(`"${status}" → ${expectedTone}`, () => {
      const result = getToneRunStatus(status);
      expect(result).toBe(expectedTone);
      assertTone(result);
    });
  }

  it('returns neutral for unknown run status strings', () => {
    const result = getToneRunStatus('unknown-status');
    expect(result).toBe('neutral');
    assertTone(result);
  });

  it('returns a valid Tone for all known run statuses', () => {
    const known = ['running', 'done', 'success', 'failed', 'error', 'cancelled', 'waiting', 'pending', 'blocked', 'skipped'];
    known.forEach((s) => assertTone(getToneRunStatus(s)));
  });
});

// ── getToneFeatureState ────────────────────────────────────────────────────────

describe('getToneFeatureState', () => {
  const cases: Array<[FeatureState, Tone]> = [
    ['backlog', 'neutral'],
    ['planned', 'info'],
    ['processing', 'running'],
    ['waiting', 'warning'],
    ['done', 'success'],
  ];

  for (const [state, expectedTone] of cases) {
    it(`${state} → ${expectedTone}`, () => {
      const result = getToneFeatureState(state);
      expect(result).toBe(expectedTone);
      assertTone(result);
    });
  }

  it('returns a valid Tone for all FeatureState values', () => {
    const allStates: FeatureState[] = ['backlog', 'planned', 'processing', 'waiting', 'done'];
    allStates.forEach((s) => assertTone(getToneFeatureState(s)));
  });
});

// ── Tone union completeness ────────────────────────────────────────────────────

describe('Tone union', () => {
  it('has exactly 12 members', () => {
    expect(VALID_TONES.size).toBe(12);
  });

  it('includes all status tones', () => {
    expect(VALID_TONES.has('running')).toBe(true);
    expect(VALID_TONES.has('success')).toBe(true);
    expect(VALID_TONES.has('info')).toBe(true);
    expect(VALID_TONES.has('warning')).toBe(true);
    expect(VALID_TONES.has('danger')).toBe(true);
    expect(VALID_TONES.has('neutral')).toBe(true);
  });

  it('includes all categorical tones', () => {
    expect(VALID_TONES.has('goal')).toBe(true);
    expect(VALID_TONES.has('feature')).toBe(true);
    expect(VALID_TONES.has('fix')).toBe(true);
    expect(VALID_TONES.has('issue')).toBe(true);
    expect(VALID_TONES.has('plan')).toBe(true);
    expect(VALID_TONES.has('ask')).toBe(true);
  });
});
