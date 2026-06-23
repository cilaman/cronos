import { describe, expect, test } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';

/**
 * Audit test: no raw Tailwind palette classes in badge-adjacent JSX.
 *
 * The badge migration (gui-badge-system I1-I5) replaced duplicated *_BADGE_STYLES /
 * *_COLOR objects with the <Badge tone=...> component system. This test enforces that
 * none of the 10 migrated scope files reverts to raw palette classes for badge rendering.
 *
 * Pattern matches standalone palette colour utilities such as:
 *   bg-emerald-500, text-amber-800, ring-violet-300, border-rose-400
 *
 * Modifier-prefixed variants (hover:, dark:, focus:, etc.) are excluded via negative
 * lookbehind — they are intentional state-variant classes, not badge colour overrides.
 */

// Matches raw palette colour utilities NOT preceded by a Tailwind modifier colon.
// E.g. matches  bg-emerald-500  but not  hover:bg-emerald-500  or  dark:text-amber-300
const RAW_PALETTE_PATTERN =
  /(?<![:\w])(bg|text|ring|border)-(red|orange|amber|teal|sky|emerald|violet|rose|indigo|purple)-\d+/g;

const SCOPE_FILES = [
  'src/components/ui/Badge.tsx',
  'src/utils/badgeTone.ts',
  'src/components/Card.tsx',
  'src/components/Detail.tsx',
  'src/components/TaskForm.tsx',
  'src/components/FeatureForm.tsx',
  'src/components/FeatureDetail.tsx',
  'src/components/ConversationEntry.tsx',
  'src/pages/HarnessRunsPage.tsx',
  'src/components/harness/RunOverlay.tsx',
];

describe('No raw palette classes in badge scope files', () => {
  for (const relPath of SCOPE_FILES) {
    test(`${relPath} has no raw palette badge classes`, () => {
      const fullPath = resolve(__dirname, '..', relPath);
      const content = readFileSync(fullPath, 'utf-8');
      const matches = content.match(RAW_PALETTE_PATTERN) ?? [];
      expect(matches, `Found raw palette classes in ${relPath}: ${matches.join(', ')}`).toHaveLength(0);
    });
  }
});
