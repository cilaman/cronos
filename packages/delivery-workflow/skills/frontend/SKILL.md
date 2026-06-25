---
name: frontend
description: Method for producing a frontend spec — component inventory from the analysis report, mockup format conventions, FE-spec structure (component tree, props, state, endpoints). Loaded by the frontend-designer agent.
---

# frontend

How to design the frontend for a feature. The `frontend-designer` agent owns the role and the hard rules; this skill owns the method.

## 1. Memory-first preflight
Scan injected memory for design-system conventions, existing component patterns, naming rules, accessibility standards, and prior UI decisions. Binding constraints go first.

## 2. Component inventory (from analysis)
From the analysis artifact, extract any named UI components, pages, or interactions. Catalogue what already exists in the codebase (read `frontend/src/components/`, `frontend/src/pages/`) to avoid re-inventing or colliding with existing names.

## 3. Produce ASCII mockups (supplementary)
For each major view or state:
```
+------------------------------+
| Page Title                   |
| [Action Button]              |
| ┌──────────────────────────┐ |
| │  ComponentX               │ |
| └──────────────────────────┘ |
+------------------------------+
```
Keep mockups illustrative, not pixel-precise. One mockup per distinct view state is sufficient.

## 4. Write the FE spec
For each component:
- **Name** — PascalCase, matching analysis artifact names where given.
- **Props** — typed interface (`name: type`, one per line).
- **State** — local state fields with types.
- **Queries** — React Query hooks or data-fetch calls needed.
- **Endpoints** — API paths and HTTP methods consumed.
- **A11y notes** — ARIA roles, keyboard interactions, contrast requirements.

## 5. Routing and layout
Describe page routing changes (new routes, params, guards). Describe layout: where in the existing shell the new view appears, sidebar links, breadcrumbs.

## 6. Validation checklist
Before emitting:
- [ ] Every component named in the analysis artifact appears in the FE spec.
- [ ] Every API endpoint in the spec is either existing (verified in `api.ts`) or explicitly new.
- [ ] `has_ui: true` is set in delivery_status.
- [ ] No existing source files were modified.
