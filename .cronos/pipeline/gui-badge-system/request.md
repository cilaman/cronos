GUI badge system — tone-driven Badge component (Phase 2)

Ships a single `<Badge tone=…>` component that replaces 63 raw Tailwind-palette
classes duplicated across 8+ files. Currently P1=red is defined in 4+ places and none
of these colors adapt to the neon theme. After this phase all badges are theme-aware.

**Concrete changes:**
- `Badge.tsx`: the §2.1 recipe — `inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5
  font-mono text-[10px] uppercase tracking-wide ring-1 ring-inset
  bg-{tone}/12 text-{tone} ring-{tone}/30`. Tones: running/success/info/warning/danger/
  neutral/goal/feature/fix/issue/plan/ask.
- `badgeTone.ts`: helpers mapping priority(1–5)/TaskState/type/AgentMode/run-status
  to tone strings.
- Migrate badge sites: Card.tsx (PRIORITY_BADGE_STYLES, TYPE_BADGE_STYLES, task state),
  Detail.tsx:280–352 (duplicate maps), TaskForm.tsx:9–15, FeatureForm.tsx,
  FeatureDetail.tsx (FEATURE_STATE_BADGE + type map), ConversationEntry.tsx:35–49
  (MODEL_COLOR, AGENT_TYPE_COLOR), HarnessRunsPage.tsx:14.
- Fix RunOverlay.tsx:119 raw hex `#22c55e` → `--color-running` CSS variable.
- Delete all duplicated `*_BADGE_STYLES` / `*_COLOR` objects.

**Exit criteria:** zero raw palette classes in badge logic; badges adapt correctly in
neon theme; `npm run build` + `npm test` green.

Scope: frontend/src/components/ui/Badge.tsx, frontend/src/utils/badgeTone.ts, frontend/src/components/Card.tsx, frontend/src/pages/Detail.tsx, frontend/src/components/TaskForm.tsx, frontend/src/components/FeatureForm.tsx, frontend/src/pages/FeatureDetail.tsx, frontend/src/components/ConversationEntry.tsx, frontend/src/pages/HarnessRunsPage.tsx, frontend/src/components/harness/RunOverlay.tsx
