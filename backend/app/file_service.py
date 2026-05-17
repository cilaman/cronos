from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Category lookup
# ---------------------------------------------------------------------------

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}
_TEXT_EXT = {".txt", ".md", ".csv", ".log", ".env", ".ini", ".cfg", ".toml",
             ".yaml", ".yml"}
_CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".sh", ".bash",
             ".zsh", ".css", ".html", ".xml", ".sql", ".go", ".rs", ".rb",
             ".java", ".c", ".cpp", ".h", ".php", ".swift", ".kt", ".r",
             ".m", ".scala", ".clj", ".ex", ".exs"}
_DOCUMENT_EXT = {".pdf"}
_ARCHIVE_EXT = {".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".tgz", ".xz"}

# AI artifact path-prefix rules (relative paths use forward slashes)
_AI_PREFIXES: list[tuple[str, str]] = [
    (".claude/agents/", "agent"),
    (".claude/skills/", "skill"),
    (".claude/commands/", "command"),
    (".claude/context/", "context"),
    (".claude/CONTEXT.md", "context"),
]


def classify_file(rel_path: str, name: str) -> str:
    """Return a category string for a file.

    Path-prefix rules (AI artifacts) take priority; extension rules follow.
    """
    norm = rel_path.replace("\\", "/")
    for prefix, category in _AI_PREFIXES:
        if norm == prefix or norm.startswith(prefix):
            return category

    ext = Path(name).suffix.lower()
    if ext in _IMAGE_EXT:
        return "image"
    if ext in _TEXT_EXT:
        return "text"
    if ext in _CODE_EXT:
        return "code"
    if ext in _DOCUMENT_EXT:
        return "document"
    if ext in _ARCHIVE_EXT:
        return "archive"
    return "binary"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class FileEntry(BaseModel):
    name: str
    path: str        # relative to root, forward slashes
    size: int
    modified_at: str # ISO-8601
    is_dir: bool
    category: str    # see classify_file


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def list_files(
    root: Path,
    *,
    max_entries: int = 500,
    skip_prefixes: tuple[str, ...] = (),
) -> list[FileEntry]:
    """Recursively list files under *root*.

    Skipping rules (applied to each entry name):
    - Names starting with '.' are hidden UNLESS the parent path contains
      '.claude', so AI artifact dirs under .claude/ remain visible.
    - Directories whose name matches any prefix in *skip_prefixes* are skipped
      entirely (e.g. ".cronos" at the space level).
    """
    entries: list[FileEntry] = []

    def _walk(dirpath: Path, rel_prefix: str) -> None:
        if len(entries) >= max_entries:
            return
        try:
            children = sorted(dirpath.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        for child in children:
            if len(entries) >= max_entries:
                break
            name = child.name
            rel = f"{rel_prefix}{name}"

            # Hidden file/dir — skip unless we're inside .claude/
            if name.startswith(".") and ".claude" not in rel_prefix:
                continue

            # Explicitly skipped directory prefixes
            if child.is_dir() and any(name == sp or name.startswith(sp) for sp in skip_prefixes):
                continue

            is_dir = child.is_dir()
            try:
                stat = child.stat()
                size = stat.st_size if not is_dir else 0
                mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            except OSError:
                continue

            category = "directory" if is_dir else classify_file(rel, name)
            entries.append(FileEntry(
                name=name,
                path=rel,
                size=size,
                modified_at=mtime,
                is_dir=is_dir,
                category=category,
            ))

            if is_dir:
                _walk(child, f"{rel}/")

    _walk(root, "")
    return entries


async def list_git_changed_files(root: Path) -> list[FileEntry] | None:
    """Return only new/modified files in a git worktree.

    Returns None if *root* is not a git repo so the caller can fall back to
    list_files(). Deleted files are omitted (nothing to show).
    """
    if not (root / ".git").exists():
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", str(root), "status", "--porcelain", "--untracked-files=all",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
    except Exception:
        return None

    entries: list[FileEntry] = []
    for line in stdout.decode().splitlines():
        if len(line) < 4:
            continue
        xy = line[:2]
        path = line[3:]
        # Skip ignored files and deleted files
        if xy == "!!" or "D" in xy:
            continue
        # Renames: "old -> new"
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"').replace("\\", "/")

        full = root / path
        if not full.exists() or full.is_dir():
            continue
        try:
            stat = full.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            continue

        entries.append(FileEntry(
            name=full.name,
            path=path,
            size=stat.st_size,
            modified_at=mtime,
            is_dir=False,
            category=classify_file(path, full.name),
        ))

    entries.sort(key=lambda e: e.path)
    return entries


def resolve_safe(root: Path, rel_path: str) -> Path:
    """Resolve *rel_path* inside *root*, raising ValueError on traversal."""
    # Normalise to forward slashes and strip leading slash
    clean = rel_path.replace("\\", "/").lstrip("/")
    full = (root / clean).resolve()
    root_str = str(root.resolve())
    if not (str(full) == root_str or str(full).startswith(root_str + os.sep)):
        raise ValueError(f"Path traversal attempt: {rel_path!r}")
    return full


async def save_upload(
    root: Path,
    rel_subdir: str,
    upload: UploadFile,
    *,
    max_bytes: int = 52_428_800,  # 50 MB
) -> FileEntry:
    """Stream *upload* into *root/rel_subdir/filename* atomically.

    Creates intermediate directories as needed. Raises ValueError for
    traversal attempts or files that exceed *max_bytes*.
    """
    # Validate subdir
    if rel_subdir:
        target_dir = resolve_safe(root, rel_subdir)
    else:
        target_dir = root.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(upload.filename or "upload").name  # strip any path component
    dest = target_dir / filename

    # Stream to a temp file then atomically rename
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    written = 0
    try:
        with tmp.open("wb") as fh:
            while True:
                chunk = await upload.read(65_536)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError(
                        f"Upload exceeds maximum allowed size of {max_bytes} bytes"
                    )
                fh.write(chunk)
        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    stat = dest.stat()
    rel = str(dest.relative_to(root)).replace("\\", "/")
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return FileEntry(
        name=filename,
        path=rel,
        size=stat.st_size,
        modified_at=mtime,
        is_dir=False,
        category=classify_file(rel, filename),
    )
