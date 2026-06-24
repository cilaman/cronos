import type { TaskState, FeatureState, AgentMode, TaskType } from '../types';

export type Tone =
  | 'running' | 'success' | 'info' | 'warning' | 'danger' | 'neutral'
  | 'goal' | 'feature' | 'fix' | 'issue' | 'plan' | 'ask';

export function getTonePriority(p: 1 | 2 | 3 | 4 | 5): Tone {
  // P1=danger, P2=warning, P3=info, P4=success, P5=neutral
  const map: Record<number, Tone> = { 1: 'danger', 2: 'warning', 3: 'info', 4: 'success', 5: 'neutral' };
  return map[p] ?? 'neutral';
}

export function getToneTaskState(s: TaskState): Tone {
  const map: Record<string, Tone> = {
    backlog: 'neutral',
    active: 'running',
    waiting: 'warning',
    done: 'success',
    archived: 'neutral',
  };
  return (map[s] as Tone) ?? 'neutral';
}

export function getToneType(t: TaskType): Tone {
  const map: Record<string, Tone> = {
    task: 'neutral',
    goal: 'goal',
    feature: 'feature',
    fix: 'fix',
    issue: 'issue',
    plan: 'plan',
    ask: 'ask',
  };
  return (map[t] as Tone) ?? 'neutral';
}

export function getToneMode(m: AgentMode): Tone {
  const map: Record<string, Tone> = {
    auto: 'running',
    plan: 'plan',
    ask: 'ask',
  };
  return (map[m] as Tone) ?? 'neutral';
}

export function getToneRunStatus(s: string): Tone {
  const map: Record<string, Tone> = {
    running: 'running',
    done: 'success',
    success: 'success',
    failed: 'danger',
    error: 'danger',
    cancelled: 'neutral',
    waiting: 'warning',
    pending: 'neutral',
    blocked: 'danger',
    skipped: 'neutral',
  };
  return (map[s] as Tone) ?? 'neutral';
}

export function getToneFeatureState(s: FeatureState): Tone {
  const map: Record<string, Tone> = {
    backlog: 'neutral',
    planned: 'info',
    processing: 'running',
    waiting: 'warning',
    done: 'success',
  };
  return (map[s] as Tone) ?? 'neutral';
}
