---
name: doc
description: Method for updating documentation after an implementation — doc file discovery from files_changed[], intentionally_not_updated discipline, and update depth rubric. Loaded by the doc-sync agent.
---

# doc

How to update documentation after an implementation pass. The `doc-sync` agent owns the role and the hard rules; this skill owns the method.

## 1. Memory-first preflight
Scan injected memory for doc standards, style guides, known doc debt, and prior conventions. Binding constraints: if a naming rule exists, honour it.

## 2. Discover affected doc files
From the implementation artifact's `files_changed[]`:
- For each changed source file, find all doc files that reference it (Grep for file path, module name, function names).
- Check `README.md`, `docs/`, `CHANGELOG.md`, inline docstrings, and any module-level `__doc__` strings.

Produce a candidate list: one entry per doc file discovered.

## 3. Triage the candidate list
For each candidate:
- **Update** — user-facing behaviour changed, public API changed, new endpoint, new flag, new component → update required.
- **Intentionally skip** — internal refactor only, no public API change, no new user-visible behaviour → add to `intentionally_not_updated` with reason.

## 4. Update depth rubric
| Change type | Doc update depth |
|---|---|
| New public API / endpoint / component | Full doc (description, params, example, return) |
| Changed public API signature | Update existing doc; note breaking change |
| New CLI flag or config key | Add to reference doc + update CHANGELOG |
| Internal-only refactor | Changelog entry only (or skip if trivial) |
| Bug fix (no API change) | Changelog entry only |
| New test file only | No doc update required |

## 5. Write the doc updates
Edit only `.md`, `.rst`, `.txt`, and similar plain-text documentation files. For Python docstrings: you may update docstring text within a `.py` file, but never modify functional code lines in the same pass.

## 6. Complete the delivery_status
- `docs_updated`: list of every file you wrote in this run.
- `intentionally_not_updated`: list of every candidate you triaged as skip, with reason.
- Both fields are required; empty list is valid.
