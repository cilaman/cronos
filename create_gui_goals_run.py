import urllib.request, json

SPACE = "cronos-development"
ROOT_SLUG = "gui-unification"
FEATURE_BRANCH = "feature/gui-unification"

def api_post(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://backend:8000/api/tasks", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# Root goal
root = api_post({
    "space_id": SPACE, "type": "goal", "priority": 2,
    "title": "GUI Unification — Cronos UI/UX refactor",
    "brief": """Unifies and modernizes the Cronos frontend based on the full UI/UX audit at `docs/ui-ux-review/`.

## Background

The audit (docs/ui-ux-review/01-executive-summary.md) found that Cronos is 80% of the way to a
distinctive professional UI. The foundation is strong (semantic CSS-variable theme system,
three themes, custom shadow/grain/grid atmosphere, a real `components/ui/` folder) but is applied
inconsistently — several apps wearing the same paint.

The work is consolidation, not reinvention: promote the good patterns into enforced primitives
and tokens, then retire the ad-hoc copies. The operator-console aesthetic (JetBrains Mono labels,
hairline grids, phosphor-green, status-as-light) is preserved and sharpened.

## Feature branch

All work shares feature/gui-unification. Sub-goals do NOT create separate branches.
Nothing merges to main until Phase 6 (goal-finalize).

## Sub-goals (sequential)

- Phase 0 (gui-sg0-tokens-brand): Add status/categorical CSS tokens + wire brand palette + favicon/logo swap + scale docs
- Phase 1 (gui-sg1-layout-primitives): PageHeader + PageContainer components adopted on all pages
- Phase 2 (gui-sg2-badge-unification): Theme-aware Badge component; migrate 63 raw palette classes
- Phase 3 (gui-sg3-button-enforcement): Expand Button/IconButton; migrate ~160 ad-hoc buttons
- Phase 4 (gui-sg4-icons): Add lucide-react; replace 77 structural emoji + inline SVG
- Phase 5 (gui-sg5-modal-skeleton): Enforce Modal contract; add Skeleton; eliminate layout shift
- Phase 6 (gui-sg6-polish): Touch targets, Toast, component extraction, mobile refinements

## Acceptance (overall)

- Zero raw Tailwind palette classes / raw hex in .tsx badge logic
- Every page uses PageHeader/PageContainer; one title size; 2 container widths max
- Every badge renders through Badge; correct in light + dark + neon
- lucide-react is the only icon source (plus user space-avatars)
- All interactive elements have focus-visible ring and 44px hit area
- No layout shift on data load; one modal behavior
- npm run build + npm test green

## Reference

- Audit: docs/ui-ux-review/01-executive-summary.md
- Design system: docs/ui-ux-review/02-design-system.md
- Roadmap & component specs: docs/ui-ux-review/05-roadmap.md
- Brand assets: docs/ui-ux-review/brand/
- Wireframes: docs/ui-ux-review/wireframes/index.html
""",
})
ROOT_ID = root["id"]
print(f"Root goal: {ROOT_ID}  ({root['title']})")

SUBGOALS = [
    {
        "slug": "gui-sg0-tokens-brand",
        "title": "Phase 0 — Tokens & Brand integration",
        "brief_summary": """Adds the missing status and categorical CSS tokens to all three themes, wires the brand
palette from docs/ui-ux-review/brand/, swaps the favicon and sidebar wordmark to brand SVGs,
adds type/spacing/radius/z-index/motion scales to tailwind.config, and writes TOKENS.md as the
cited token reference.

What changes: frontend/src/index.css (new :root/.dark/.neon token variables),
frontend/tailwind.config.js (scale extensions), frontend/index.html (favicon),
frontend/src/App.tsx or sidebar (logo swap), frontend/src/styles/TOKENS.md (new doc file).

Zero large visual change — only the favicon and sidebar wordmark update; all other UI is
unchanged. This phase provides the token foundation every subsequent phase depends on.

Scope files: frontend/src/index.css, frontend/tailwind.config.js, frontend/index.html,
frontend/src/App.tsx, frontend/src/styles/TOKENS.md (new)

Reference:
- Design system tokens: docs/ui-ux-review/02-design-system.md sections 2.1-2.6
- Brand palette: docs/ui-ux-review/06-brand.md section 6.4, docs/ui-ux-review/brand/tokens/tokens.css
- Brand SVG assets: docs/ui-ux-review/brand/logo/, docs/ui-ux-review/brand/png/
- Roadmap Phase 0: docs/ui-ux-review/05-roadmap.md
""",
    },
    {
        "slug": "gui-sg1-layout-primitives",
        "title": "Phase 1 — Layout primitives (PageHeader + PageContainer)",
        "brief_summary": """Ships two new React components: PageHeader and PageContainer. Adopts them on all ~18 pages
by replacing each page's bespoke title markup with the new primitives.

What changes: New files frontend/src/components/ui/PageHeader.tsx and
frontend/src/components/ui/PageContainer.tsx. All page components updated to import and
use them (BoardPage, TreePage, HarnessRunsPage, HarnessListPage, SpaceToolsPage, HarnessEditor,
Dashboard, Stats, FileBrowserPage, FeaturesBoard, ArchivedPage, etc.).

Visible result: Every page top is structurally identical — one title size, breadcrumb
slot, actions slot, 2 container widths max. Eliminates the current 13px to 22px title-size drift
and four scattered container max-widths (768/1024/1280/5xl).

Component contracts (from docs/ui-ux-review/05-roadmap.md):
- PageHeader: title, breadcrumb?, subtitle?, actions?, sticky?
- PageContainer: width? 'content'(1280) or 'reading'(768), applies p-6 lg:p-8

Reference:
- Executive summary finding #2: docs/ui-ux-review/01-executive-summary.md
- Roadmap Phase 1: docs/ui-ux-review/05-roadmap.md
""",
    },
    {
        "slug": "gui-sg2-badge-unification",
        "title": "Phase 2 — Badge unification",
        "brief_summary": """Ships a theme-aware Badge tone component backed by the status/categorical tokens
from Phase 0. Migrates all duplicated badge style objects across the codebase to use it.

What changes: New frontend/src/components/ui/Badge.tsx. New helper badgeTone() function.
Badge logic replaced in: Card.tsx, Detail.tsx, TaskForm.tsx, FeatureForm.tsx,
FeatureDetail.tsx, ConversationEntry.tsx, HarnessRunsPage.tsx, RunOverlay.tsx.

Visible result: All badges render correctly in light, dark, AND neon themes (currently
broken in neon). Eliminates 63 raw Tailwind palette color classes in badge logic.
Five duplicated style-map objects deleted.

Badge tone values: running | success | info | warning | danger | neutral | goal | feature | fix | issue | plan | ask

Badge recipe (mono text, tinted fill, inset ring):
inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5
font-mono text-[10px] uppercase tracking-wide leading-none ring-1 ring-inset
bg-{tone}/12  text-{tone}  ring-{tone}/30

Reference:
- Executive summary finding #1: docs/ui-ux-review/01-executive-summary.md
- Design system section 2.1: docs/ui-ux-review/02-design-system.md
- Roadmap Phase 2: docs/ui-ux-review/05-roadmap.md
""",
    },
    {
        "slug": "gui-sg3-button-enforcement",
        "title": "Phase 3 — Button/IconButton enforcement",
        "brief_summary": """Expands the existing Button and IconButton primitives with missing variants and behavior,
then migrates ~160 ad-hoc inline-styled button elements to use them.

What changes: frontend/src/components/ui/Button.tsx and IconButton.tsx expanded
(add tertiary, link, ghost, danger variants; bake in focus-visible ring; add loading
state, leadingIcon slot, 44px minimum hit area). Migration touches shell components (App.tsx,
sidebar), board components (Card.tsx, lane headers), and all page components.

Visible result: Inline className button strings essentially gone. Focus rings
appear on all interactive elements (keyboard users keep their place). Consistent button
sizes and hit areas.

New archetypes to add: toolbar-chip, dropdown-trigger, segmented, list-row

Reference:
- Executive summary finding #3: docs/ui-ux-review/01-executive-summary.md
- Component spec Button/IconButton: docs/ui-ux-review/05-roadmap.md
- Roadmap Phase 3: docs/ui-ux-review/05-roadmap.md
""",
    },
    {
        "slug": "gui-sg4-icons",
        "title": "Phase 4 — Icon system (lucide-react)",
        "brief_summary": """Adds lucide-react as the single icon library and replaces all structural emoji and
hand-rolled inline SVG with lucide icons.

What changes: package.json (add lucide-react). New frontend/src/components/ui/Icon.tsx
wrapper with icon-sm/md/lg size tokens. All files using structural emoji or inline SVG updated
to import from Icon/lucide-react. 77 structural emoji replaced in nav, buttons, badges,
file-type indicators. User-chosen space-avatar emoji left untouched.

Visible result: One consistent stroke-based icon language across the entire app.
No structural emoji. All icon sizes consistent.

Icons to keep (emoji): User space-avatar emoji (colored circle/emoji in space cards) — these are user data.

Reference:
- Executive summary finding #4: docs/ui-ux-review/01-executive-summary.md
- Roadmap Phase 4: docs/ui-ux-review/05-roadmap.md
""",
    },
    {
        "slug": "gui-sg5-modal-skeleton",
        "title": "Phase 5 — Modal contract + Skeleton + loading states",
        "brief_summary": """Enforces a single Modal behavior contract and ships a Skeleton primitive to eliminate
layout shift on data load.

What changes (Modal): frontend/src/components/ui/Modal.tsx updated to enforce: scrim
bg-black/60 plus blur (z-scrim layer), panel z-modal layer, scale-fade animation at motion-slow,
Escape key handling, focus-trap, focus-return on close, single X close button. The 4 ad-hoc
modal re-implementations migrated: MarkdownEditorModal, file viewer modal, view-delete dialog,
CreateHarnessModal.

What changes (Skeleton): New frontend/src/components/ui/Skeleton.tsx (text/block/card
variants, shimmer animation at motion-base rate, reserves space). Spinner/text loaders
replaced with skeletons in all data-loading pages.

Visible result: One scrim opacity, one Escape behavior, one focus pattern across all modals.
No layout shift when data arrives (skeletons reserve exact space).

Reference:
- Executive summary findings #5 and #8: docs/ui-ux-review/01-executive-summary.md
- Component specs Modal/Skeleton: docs/ui-ux-review/05-roadmap.md
- Roadmap Phase 5: docs/ui-ux-review/05-roadmap.md
""",
    },
    {
        "slug": "gui-sg6-polish",
        "title": "Phase 6 — Polish (touch targets, toast, components, mobile)",
        "brief_summary": """Final polish phase: touch-target sweep, Toast provider, compound component extraction,
Stats/Dashboard visualization improvements, and mobile refinements.

What changes:
- Touch targets: all interactive elements verified 44px minimum hit area
- Toast: new frontend/src/components/ui/Toast.tsx plus useToast() hook. aria-live polite,
  user-voiced copy, auto-dismiss 3-5s, no focus steal. Error messages rewritten.
- Component extraction: Tabs, Dropdown, SegmentedControl, Tooltip, StatTile, ProgressBar
- Stats/Dashboard viz: add legends, tooltips, empty state, loading state to chart areas
- Mobile: space context in header at <768px, drawer Escape, target sizes at 393px
- Optional: ESLint rule banning raw palette classes and raw hex in .tsx files

Visible result: App fully usable with keyboard and on mobile. No raw error messages.
Consistent component language. Operator-console feel intact and sharpened.

Reference:
- Executive summary findings #6-10: docs/ui-ux-review/01-executive-summary.md
- Component specs: docs/ui-ux-review/05-roadmap.md
- Roadmap Phase 6: docs/ui-ux-review/05-roadmap.md
- Acceptance criteria (full set): docs/ui-ux-review/05-roadmap.md
""",
    },
]

prev_sg_id = None

for sg_idx, sg in enumerate(SUBGOALS):
    sg_slug = sg["slug"]
    pipeline_dir = f".cronos/pipeline/{sg_slug}"
    is_first = (sg_idx == 0)
    is_last  = (sg_idx == len(SUBGOALS) - 1)

    sg_obj = api_post({
        "space_id": SPACE, "type": "goal", "parent_id": ROOT_ID,
        "priority": 2,
        "title": sg["title"],
        "brief": sg["brief_summary"] + f"""
## Pipeline dir
{pipeline_dir}/

## Git workflow
All work on branch {FEATURE_BRANCH} — do NOT commit to main.
{"First subgoal: run /goal-branch-setup before the scout phase." if is_first else ""}
{"Last subgoal: run /goal-finalize after doc-sync." if is_last else "Run /goal-task-commit after doc-sync."}
""",
        "depends_on": [prev_sg_id] if prev_sg_id else [],
    })
    SG_ID = sg_obj["id"]
    print(f"  SubGoal {sg_idx}: {SG_ID}  ({sg['title']})")

    prev_task_id = None

    if is_first:
        gbs = api_post({
            "space_id": SPACE, "type": "task", "parent_id": SG_ID,
            "priority": 2, "agent_model": "haiku", "agent_mode": "auto",
            "title": f"goal-branch-setup – {ROOT_SLUG}",
            "brief": f"""Create and check out the shared feature branch for the entire GUI Unification goal tree.

Run /goal-branch-setup

This must be the very first task in the goal tree. It creates {FEATURE_BRANCH} from main
and checks it out in the workspace worktree so all subsequent tasks commit to it.

After the branch is set up, this task is done. The scout task will start next.
""",
        })
        prev_task_id = gbs["id"]
        print(f"    goal-branch-setup: {gbs['id']}")

    phases = [
        {
            "phase": "scout",
            "model": "haiku",
            "agent": "pipeline-scout",
            "brief_body": f"""CC-v1 scout phase for: {sg["title"]}

Do a memory-first codebase reconnaissance of all files relevant to this phase's scope.
Read the UI/UX review docs at docs/ui-ux-review/ to understand the requirements.

Agent contract: .claude/agents/pipeline-scout.md

Artifact to emit: {pipeline_dir}/scout-report-{sg_slug}.md (class=research)

Phase scope:
{sg["brief_summary"][:400]}

Then run: /pipeline-gate
""",
        },
        {
            "phase": "analyst",
            "model": "sonnet",
            "agent": "pipeline-analyst",
            "brief_body": f"""CC-v1 analyst phase for: {sg["title"]}

Read scout report: {pipeline_dir}/scout-report-{sg_slug}.md
Agent contract: .claude/agents/pipeline-analyst.md

Decompose the phase into testable requirements (R1, R2, ...). Set has_ui=true.
Reference the UI/UX review docs at docs/ui-ux-review/ for the design intent.

Artifact to emit: {pipeline_dir}/analysis-report-{sg_slug}.md (class=analysis)

Then run: /pipeline-gate
""",
        },
        {
            "phase": "architect",
            "model": "opus",
            "agent": "pipeline-architect",
            "brief_body": f"""CC-v1 architect phase for: {sg["title"]}

Read analysis report: {pipeline_dir}/analysis-report-{sg_slug}.md
Agent contract: .claude/agents/pipeline-architect.md

Design a topologically-ordered iterations[] DAG with risks[]. Each iteration must be
independently shippable and leave the app green (npm run build + npm test pass).

Reference:
- Scout report: {pipeline_dir}/scout-report-{sg_slug}.md
- UI/UX review roadmap: docs/ui-ux-review/05-roadmap.md
- Component specs: docs/ui-ux-review/05-roadmap.md (Component specs section)

Artifact to emit: {pipeline_dir}/design-report-{sg_slug}.md (class=design)

Then run: /pipeline-gate
""",
        },
        {
            "phase": "impl",
            "model": "sonnet",
            "agent": "pipeline-implementor",
            "brief_body": f"""CC-v1 implementation phase for: {sg["title"]}

Read design report: {pipeline_dir}/design-report-{sg_slug}.md
Agent contract: .claude/agents/pipeline-implementor.md

Execute the iterations[] plan from the design report.
Emit one impl-report per iteration: {pipeline_dir}/impl-report-{sg_slug}--iN.md (class=implementation)

Reference:
- Scout report: {pipeline_dir}/scout-report-{sg_slug}.md
- Analysis report: {pipeline_dir}/analysis-report-{sg_slug}.md
- UI/UX review wireframes: docs/ui-ux-review/wireframes/index.html
- Brand assets: docs/ui-ux-review/brand/
- Feature branch: {FEATURE_BRANCH} (do NOT commit to main)

Then run: /pipeline-gate (for the final iteration)
""",
        },
        {
            "phase": "test",
            "model": "sonnet",
            "agent": "tester",
            "brief_body": f"""CC-v1 test phase for: {sg["title"]}

Read impl reports in: {pipeline_dir}/
Agent contract: .claude/agents/tester.md

Run npm test (vitest) from frontend/ and pytest tests/ --cov=app from backend/.
Verify the implementation passes all existing tests and any new tests added in the impl phase.
Coverage floor: 80% backend.

Artifact to emit: {pipeline_dir}/test-report-{sg_slug}.md (class=test, slug={sg_slug})

Then run: /pipeline-gate
""",
        },
        {
            "phase": "review",
            "model": "opus",
            "agent": "pipeline-reviewer",
            "brief_body": f"""CC-v1 review phase for: {sg["title"]}

Read design report: {pipeline_dir}/design-report-{sg_slug}.md
Read impl reports in: {pipeline_dir}/
Read test report: {pipeline_dir}/test-report-{sg_slug}.md
Agent contract: .claude/agents/pipeline-reviewer.md

Audit the implementation diff against the design scope. Emit verdict: pass / needs_fix / fail.

Artifact to emit: {pipeline_dir}/review-report-{sg_slug}--attempt1.md (class=review)

Then run: /pipeline-gate
""",
        },
        {
            "phase": "doc",
            "model": "haiku",
            "agent": "pipeline-doc-sync",
            "brief_body": f"""CC-v1 doc-sync phase for: {sg["title"]}

Read review report: {pipeline_dir}/review-report-{sg_slug}--attempt1.md
Agent contract: .claude/agents/pipeline-doc-sync.md

Update docs (CLAUDE.md key modules table, TOKENS.md if Phase 0, component JSDoc, README
if needed) for every file changed in the implementation. Never edit source files.

Artifact to emit: {pipeline_dir}/doc-report-{sg_slug}.md (class=doc)

Then run: /pipeline-gate

After pipeline-gate passes: run {'goal-finalize to merge feature/gui-unification to main and clean up.' if is_last else 'goal-task-commit to push changes to ' + FEATURE_BRANCH + '.'}
""",
        },
    ]

    for ph in phases:
        task = api_post({
            "space_id": SPACE, "type": "task", "parent_id": SG_ID,
            "priority": 2,
            "agent_model": ph["model"],
            "agent_mode": "auto",
            "depends_on": [prev_task_id] if prev_task_id else [],
            "title": f"{ph['phase']} – {sg_slug}",
            "brief": ph["brief_body"],
        })
        prev_task_id = task["id"]
        print(f"    {ph['phase']:12s}: {task['id']}")

    prev_sg_id = SG_ID

print(f"\nDone! Root goal ID: {ROOT_ID}")
