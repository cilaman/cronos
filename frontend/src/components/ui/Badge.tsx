import React from 'react';
import { Tone } from '../../utils/badgeTone';

const TONE_CLASSES: Record<Tone, string> = Object.freeze({
  running:  'bg-running/12 text-running ring-running/30',
  success:  'bg-success/12 text-success ring-success/30',
  info:     'bg-info/12 text-info ring-info/30',
  warning:  'bg-warning/12 text-warning ring-warning/30',
  danger:   'bg-danger/12 text-danger ring-danger/30',
  neutral:  'bg-neutral/12 text-neutral ring-neutral/30',
  goal:     'bg-goal/12 text-goal ring-goal/30',
  feature:  'bg-feature/12 text-feature ring-feature/30',
  fix:      'bg-fix/12 text-fix ring-fix/30',
  issue:    'bg-issue/12 text-issue ring-issue/30',
  plan:     'bg-plan/12 text-plan ring-plan/30',
  ask:      'bg-ask/12 text-ask ring-ask/30',
});

interface BadgeProps {
  tone: Tone;
  children?: React.ReactNode;
  className?: string;
}

export function Badge({ tone, children, className }: BadgeProps) {
  const toneClasses = TONE_CLASSES[tone];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ring-1 ring-inset ${toneClasses}${className ? ` ${className}` : ''}`}
    >
      {children}
    </span>
  );
}
