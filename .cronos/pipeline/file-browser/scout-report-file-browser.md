---
cc_version: "1.0"
agent: pipeline-scout
slug: file-browser
phase: scout
status: done
confidence: 0.92
inputs_used:
  - frontend/src/components/FileBrowser.tsx
  - frontend/src/components/FilesPanel.tsx
  - frontend/src/types.ts
  - frontend/src/api.ts
  - backend/app/file_service.py
  - backend/app/api/tasks.py
  - backend/app/agent.py
  - frontend/src/router.tsx
  - frontend/src/App.tsx
outputs_produced:
  - .cronos/pipeline/file-browser/scout-report-file-browser.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - frontend/src/components/
    - frontend/src/pages/
    - frontend/src/api.ts
    - frontend/src/types.ts
    - backend/app/api/tasks.py
    - backend/app/file_service.py
  excluded:
    - node_modules/: Third-party dependencies
    - tests/: Unit tests
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: |
  Research the File Browser feature for Cronos. You are scouting a feature called
  "File Browser" (slug: file-browser) that will add a dedicated page for browsing
  files in the space hierarchy.
metrics:
  tool_calls: 18
  files_read: 10
  memory_hits: 0
---

## Summary

The Cronos codebase already has **task-scoped file management** fully implemented: FileBrowser and FilesPanel components, three backend REST endpoints (GET/POST/PUT), and a FileEntry classification system covering 11 file categories (agent, skill, command, context, image, text, code, document, archive, binary, directory). Files are stored under `.cronos/workspaces/{task_id}/` per task. The gap is a **space-level file browser page** (not yet wired into the router) that would let users browse and manage all files in a space root—currently only task-specific files are accessible via the task detail panel's FilesPanel sidebar.

## Coverage

### Searched
- frontend/src/components/FileBrowser.tsx (component internals)
- frontend/src/components/FilesPanel.tsx (task integration wrapper)
- frontend/src/types.ts (FileCategory, TaskFile type definitions)
- frontend/src/api.ts (taskFiles, uploadTaskFile, saveTaskFile, taskFileUrl)
- backend/app/file_service.py (FileEntry model, list_files, classify_file logic)
- backend/app/api/tasks.py (GET/POST/PUT file endpoints, _task_workspace helper)
- backend/app/agent.py (CRONOS_SUBDIR, space_dir_for function)
- frontend/src/router.tsx (route structure, page patterns)
- frontend/src/App.tsx (layout / outlet structure)

### Excluded
- backend tests: Not needed to understand API contracts
- frontend tests: Not needed for UI component interface discovery
- node_modules: Third-party dependencies

### Strategies
- memory_retrieval: 0 relevant entries found
- glob_structural: Found 16 page files; narrowed to File*.tsx components
- grep_symbol: Found taskFile, FileCategory, FileBrowser symbols
- read_targeted: Read component internals, API surface, backend models

## Findings

### 1. FileBrowser Component (frontend/src/components/FileBrowser.tsx:144–341)

**Props interface:**
```typescript
export interface FileBrowserProps {
  files: TaskFile[];
  isLoading: boolean;
  fileUrlBuilder: (path: string, download?: boolean) => string;
  onUpload?: (file: File, subdir: string) => Promise<void>;
  uploadPending?: boolean;
  onSave?: (file: TaskFile, content: string) => Promise<void>;
  savePending?: boolean;
}
```

**Rendering logic:**
- Hierarchical file list with indent-based depth visualization (line 222: `depth = file.path.split("/").length - 1`)
- Per-file actions: "Open" button (for viewable types), download arrow
- Category-based icons (11 types: agent 🤖, skill ⚡, command ⌘, context 📖, image 🖼, text 📄, code 💻, document 📑, archive 🗜, binary ⬛, directory ▸)
- Viewable categories: `["image", "text", "code", "agent", "skill", "command", "context"]` (line 37–39)
- Opens text/code/image/agent/skill/command/context files in a FileViewerModal (line 59–138)
- Markdown files (.md) open in MarkdownEditorModal instead (line 185–186)
- Documents (PDF) open in new tab; archives/binaries trigger downloads (lines 173–182)
- Upload form: optional file + optional subdirectory input (lines 290–316)
- Size formatting: `formatBytes()` utility (lines 41–46)

**Contracts:**
- Expects `files` array pre-fetched by parent
- Delegates fetch logic to parent via `fileUrlBuilder` callback
- Supports optional upload/save mutations wired from parent's React Query hooks
- Pure function—no internal data fetching

### 2. FilesPanel Component (frontend/src/components/FilesPanel.tsx:1–54)

**Purpose:** Wraps FileBrowser for task-detail integration.

**Props:**
```typescript
interface Props {
  taskId: string;
  className?: string;
}
```

**Integration:**
- Fetches task files via `api.taskFiles(taskId)` (line 16) with 10-second refetch interval (line 17)
- Wires three mutations: `uploadTaskFile(taskId, file, subdir)`, `saveTaskFile(taskId, path, content)`
- Invalidates React Query cache on success to refresh file list (lines 24, 32)
- Renders as `<aside>` container (default: hidden mobile, visible on lg+ screens with 288px width)
- Mounts as right-side panel in task detail views (not yet confirmed in Detail.tsx read)

### 3. Type Definitions (frontend/src/types.ts:280–292)

```typescript
export type FileCategory =
  | "agent" | "skill" | "command" | "context"
  | "image" | "text" | "code"
  | "document" | "archive" | "binary" | "directory";

export interface TaskFile {
  name: string;
  path: string;
  size: number;
  modified_at: string;
  is_dir: boolean;
  category: FileCategory;
}
```

**Notes:**
- Task-scoped only; no SpaceFile type exists
- Path uses forward slashes; relative to task workspace root
- Size is 0 for directories
- modified_at is ISO-8601 UTC
- category is a string derived by backend classify_file function

### 4. Frontend API Functions (frontend/src/api.ts:99–263)

**taskFileUrl builder (line 99–102):**
```typescript
export function taskFileUrl(taskId: string, filePath: string, download = false): string {
  const encoded = filePath.split("/").map(encodeURIComponent).join("/");
  return `/api/tasks/${taskId}/files/${encoded}${download ? "?download=true" : ""}`;
}
```

**API functions:**
- `api.taskFiles(taskId)` → GET `/api/tasks/{taskId}/files` → `TaskFile[]` (line 245–246)
- `api.uploadTaskFile(taskId, file, subdir)` → POST `/api/tasks/{taskId}/files?subdir={subdir}` → `TaskFile` (lines 248–255)
- `api.saveTaskFile(taskId, filePath, content)` → PUT `/api/tasks/{taskId}/files/{filePath}` + JSON body `{content: string}` → `TaskFile` (lines 257–263)

**Comment at line 104–105:**
```typescript
// Future mirror for space-level file manager:
// export function spaceFileUrl(spaceId: string, filePath: string, download = false): string { ... }
```

This is a clear **gap marker**—space-level file browsing was explicitly anticipated but not implemented.

### 5. Backend File Endpoints (backend/app/api/tasks.py:653–749)

**GET /{task_id}/files** (lines 653–666)
- Returns `list[FileEntry]`
- If workspace doesn't exist, returns `[]`
- For git worktrees (repo-linked spaces), calls `list_git_changed_files()` to show only modified/new files (not full repo)
- Fallback: calls `list_files(workspace)` for non-git workspaces

**GET /{task_id}/files/{file_path:path}** (lines 669–689)
- Stream file content or return as download
- Query param `download=true` sets `Content-Disposition: attachment` header (line 688)
- Uses `resolve_safe(workspace, file_path)` to prevent path traversal (line 681)
- Returns 404 if not found or is a directory (line 684–685)

**POST /{task_id}/files** (lines 692–713)
- Creates workspace if needed (line 703)
- Accepts multipart form: `file` + query param `subdir` (optional)
- Validates subdir via `resolve_safe()` (line 707)
- Returns `FileEntry` with HTTP 201 Created
- Calls `save_upload(workspace, subdir, file)` from file_service

**PUT /{task_id}/files/{file_path:path}** (lines 716–749)
- Overwrites file with new content
- Request body: `{content: string}` via UpdateFileBody schema
- Atomic write: writes to `.tmp` file, then renames (lines 733–736)
- Returns updated `FileEntry`

**Helper:**
```python
def _task_workspace(task: Task) -> Path:
    return space_dir_for(task.space_id) / CRONOS_SUBDIR / "workspaces" / task.id
```

### 6. Backend FileEntry Model (backend/app/file_service.py:63–70)

```python
class FileEntry(BaseModel):
    name: str
    path: str        # relative to root, forward slashes
    size: int
    modified_at: str # ISO-8601
    is_dir: bool
    category: str    # see classify_file
```

**Mirrors frontend TaskFile exactly** (same 6 fields, same types).

### 7. File Classification System (backend/app/file_service.py:35–56)

**Category precedence:**
1. Path-prefix rules (AI artifacts take priority):
   - `.claude/agents/` → "agent"
   - `.claude/skills/` → "skill"
   - `.claude/commands/` → "command"
   - `.claude/context/` → "context"
   - `.claude/CONTEXT.md` → "context"

2. Extension-based rules (fallback):
   - `_IMAGE_EXT`: {.png, .jpg, .jpeg, .gif, .svg, .webp, .bmp, .ico}
   - `_TEXT_EXT`: {.txt, .md, .csv, .log, .env, .ini, .cfg, .toml, .yaml, .yml}
   - `_CODE_EXT`: {.py, .js, .ts, .tsx, .jsx, .json, .sh, .bash, .zsh, .css, .html, .xml, .sql, .go, .rs, .rb, .java, .c, .cpp, .h, .php, .swift, .kt, .r, .m, .scala, .clj, .ex, .exs}
   - `_DOCUMENT_EXT`: {.pdf}
   - `_ARCHIVE_EXT`: {.zip, .tar, .gz, .bz2, .7z, .rar, .tgz, .xz}

3. Default: "binary"

**Directories:** category = "directory"

### 8. File Listing Logic (backend/app/file_service.py:76–136)

**list_files(root, max_entries=500, skip_prefixes=())**
- Recursively walks root, returns up to 500 FileEntry objects
- Hidden files (prefix `.`) hidden UNLESS parent path contains `.claude/`
- Skips directories matching skip_prefixes (e.g., `.cronos`)
- Sorts by (is_dir descending, name case-insensitive)
- Returns directories with size=0

**list_git_changed_files(root) → FileEntry[] | None**
- For git worktrees only: returns only new/modified files (not deleted)
- Runs `git status --porcelain --untracked-files=all`
- Returns None if not a git repo (caller falls back to list_files)

### 9. Frontend Routing (frontend/src/router.tsx)

**Current pages (17 pages):**
- Dashboard (/)
- Board (/board)
- Features (/features)
- Harnesses (/harnesses)
- Archived (/archived)
- Tools (/tools)
- Memory (/memory)
- Stats (/stats)
- Spaces (CRUD)
- Trees (/spaces/:spaceId/tree)
- Settings (/spaces/:spaceId/settings)
- Space Tools (/spaces/:spaceId/tools)
- Harness Editor (/spaces/:spaceId/harnesses/:name/edit)
- Harness Runs (/spaces/:spaceId/harnesses/:name/runs)
- Harness List (/spaces/:spaceId/harnesses)

**Pattern for new page:**
1. Create new file in `frontend/src/pages/FileBrowserPage.tsx`
2. Import at top of router.tsx
3. Add route: `<Route path="spaces/:spaceId/files" element={<FileBrowserPage />} />`
4. Add sidebar navigation link in Sidebar.tsx (pattern: `NavLink to={...}`)

**Space-scoped routes follow pattern:** `/spaces/:spaceId/{feature}`

### 10. Directory Layout

**Task file storage:**
```
/data/spaces/{space_id}/
  .cronos/
    workspaces/
      {task_id}/          ← Task workspace (workspace root)
        [user files]
        [uploaded files]
        [agent-generated outputs]
```

**Space-level files (proposed for new feature):**
```
/data/spaces/{space_id}/
  [repo files, if linked]
  .cronos/
    workspaces/
      {task_id}/
```

The space root directory itself (outside `.cronos/`) is where a space-level file browser would show files—either the linked Git repo (if linked) or a designated space-level working directory.

## Gaps Analysis

### G1: No space-level file browser page
- **Current state:** Only task-specific files visible via FilesPanel sidebar in task detail
- **Missing:** Dedicated page at `/spaces/:spaceId/files` with space-level file browser
- **Backend work:** Likely need a new endpoint `GET /api/spaces/{space_id}/files` that lists files in space root (outside .cronos/) or linked repo working tree
- **Frontend work:** New FileBrowserPage + router entry + sidebar nav link

### G2: No space-level file API endpoints
- **Current:** File endpoints all task-scoped
- **Missing:** 
  - `GET /api/spaces/{space_id}/files` (list space files)
  - `GET /api/spaces/{space_id}/files/{file_path}` (download space file)
  - `POST /api/spaces/{space_id}/files` (upload to space)
  - `PUT /api/spaces/{space_id}/files/{file_path}` (save space file)

### G3: FileBrowser designed for task context only
- **Current:** FileBrowser expects task-scoped file URLs via `fileUrlBuilder` prop
- **Refactoring needed:** Accept a generic file URL builder to support both task and space contexts
- **Risk:** Low—props already abstract URL construction; minimal changes needed

### G4: File classification assumes task workspace as root
- **Context:** `classify_file(rel_path, name)` logic in file_service.py
- **Issue:** Uses relative path to detect `.claude/` artifacts
- **Gap:** If space-level browser lists files from space root, `.claude/` detection still works (it's universal)
- **No blocker:** Existing classify_file logic is path-agnostic and reusable

### G5: No space-level directory structure design
- **Current:** .cronos/workspaces/{task_id}/ is clear
- **Missing:** Should space-level browser point to space root? Or a designated space files dir (e.g., `.cronos/files/`)?
- **Design question:** Where do user-uploaded space-level files live?

## Assumptions

- The brief intends a **dedicated page** (not just a panel) for space-level file browsing, similar to how FeaturesPage, MemoryPage, etc. are standalone pages rather than task-detail panels.
- FileBrowser component is **not** tightly coupled to tasks and can be refactored to accept a generic fileUrlBuilder.
- Space-level files should be stored in the **space root directory** (outside `.cronos/`) if the space is unlinked, or the linked **repo working tree** if linked to Git.
- The analyst/architect will decide on exact API design (whether to list space files from repo root or a subdirectory like `.cronos/files/`).

## Open questions

- Should the space-level file browser show the **entire space root** (including `.cronos/`, which is currently hidden in task view)? Or filter it out?
- If a space is linked to a Git repo, should the space-level browser show only **changed files** (like task view does) or **all files** in the working tree?
- What is the intended **UX for uploading space-level files**? Should they go to space root or a designated folder?
- Should there be **permissions/access control** for space-level file management (currently not in place for task files)?

## Next consumer brief

**Analysis phase (pipeline-analyst):**

Read these sections first:
1. **## Summary** — understand the task-scoped file system is complete; gap is space-level
2. **## Findings → section 4** — note the comment at api.ts:104–105 ("Future mirror for space-level file manager")
3. **## Findings → section 9–10** — routing pattern and directory structure
4. **## Gaps** — the five gaps are mutually dependent; G2 (API) and G1 (page) are blocking

**Traceability seeds for requirements discovery:**
- R1: User can navigate to space-level file browser page at `/spaces/:spaceId/files`
- R2: File browser displays directory tree of space root (or repo working tree if linked)
- R3: User can upload files to space root
- R4: User can view/download files (same categories as task browser)
- R5: User can edit text/code/markdown files in-browser (same as task browser)
- R6: For Git-linked spaces, browser shows only changed files (parity with task browser)
- R7: FileBrowser component is refactored to accept generic fileUrlBuilder (reusable between task and space contexts)

**Unresolved blockers:**
- No consensus yet on where space-level files physically live on disk (space root vs. `.cronos/files/` subdirectory)
- No API contract yet for space-level file endpoints
- Sidebar navigation link not yet added (frontend only—no backend work)
