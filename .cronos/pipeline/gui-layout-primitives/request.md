GUI layout primitives — PageHeader + PageContainer (Phase 1)

Ships two new UI primitives and adopts them on every page, instantly unifying the
product's first impression. Currently page titles range from 13px to 22px and container
max-widths are scattered across four values with no rule.

**Concrete changes:**
- `PageHeader.tsx`: new component — breadcrumb array, h1 title (text-title token),
  subtitle? ReactNode, actions slot (0–3 items; overflow → menu), optional sticky.
- `PageContainer.tsx`: new component — `width?: content(1280)|reading(768)`,
  `p-6 lg:p-8` padding, centers content.
- Adopt on all pages: Dashboard, Stats, HarnessRuns, HarnessListPage, HarnessEditor,
  TestReports, SpaceToolsPage, Memory, SpaceCreate, SpaceSettings, Features, Archived,
  FileBrowserPage — each replacing its ad-hoc title/container markup.
- Delete per-page title variants (text-[13px], text-sm, text-lg, text-[22px] drift).

**Exit criteria:** every page uses PageHeader/PageContainer; exactly one title size
(text-title from Phase 0); two container widths; `npm run build` + `npm test` green.

Scope: frontend/src/components/ui/PageHeader.tsx, frontend/src/components/ui/PageContainer.tsx, frontend/src/pages/*.tsx
