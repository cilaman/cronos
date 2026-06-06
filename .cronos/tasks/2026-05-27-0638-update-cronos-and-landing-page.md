---
agent_mode: auto
agent_model: default
claude_session_id: 015c5831-3336-4ee6-b4f9-b10db416de5b
created_at: '2026-05-27T06:38:35Z'
depends_on: []
id: 2026-05-27-0638-update-cronos-and-landing-page
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: archived
title: update Cronos and landing page
type: task
updated_at: '2026-06-03T07:33:36Z'
waiting_question: null
---

# Brief

Cronos was originally running on ULTC.at domain but was moved to my personal domain cilaman.com. Please remove all references to ULTC and update the landing page, so it will be legit for corporate web filters.

# History

```
2026-05-27T06:53:01Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=explore
I'll search for all references to "ULTC" across the codebase first.

Let me read all the source files that need updating.

Now I have a complete picture. I'll update all 5 source files, replacing "ULTC" with "Cilaman" and "cronos.ultc.at" with "cronos.cilaman.com". I'll do all files in parallel.

Now update about.html:

Now update terms.html and privacy.html in parallel:

Now update the app's index.html:

Now update the noscript content in index.html:

Now update the VPS_SETUP.md reference:

Now let me verify no ULTC references remain in the source files (not dist):

Two more files — `sitemap.xml` and `robots.txt`.

Now let's do a final check across all source files:

All source files are clean. The `dist/` files are build artifacts and will be regenerated on next build. Let me commit these changes:

All ULTC references have been removed from every source file. Here's a summary of what changed:

**Files updated (8):**
- `frontend/public/landing.html` — hero badge, all body copy, meta tags, JSON-LD, title, footer copyright
- `frontend/public/about.html` — subtitle, who-operates-it section, access section, meta tags, footer
- `frontend/public/terms.html` — all 7 sections replaced "ULTC" with neutral language, meta tags, footer
- `frontend/public/privacy.html` — who-applies-to, data-retention, data-sharing, contact sections, meta tags, footer
- `frontend/index.html` — meta description, canonical URL, OG tags, JSON-LD, title, noscript content
- `frontend/public/sitemap.xml` — all 4 URLs updated to `cronos.cilaman.com`
- `frontend/public/robots.txt` — sitemap URL updated
- `deploy/VPS_SETUP.md` — example hostname updated

**Key changes for corporate web filter compatibility:**
- "Internal · ULTC" badge → "Self-hosted · AI-powered"
- "Authorized ULTC team members only" → "Authorized users only"
- "Built by ULTC, for ULTC" → "Built for developers, by developers"
- All references to an unknown organization ("ULTC") removed
- Copyright updated to "© 2026 Cilaman"

STATUS: DONE
```
