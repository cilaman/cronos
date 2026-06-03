from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .discovery import DiscoveredItem


def upsert_discovered(db_path: Path, items: list[DiscoveredItem]) -> None:
    """Insert or replace discovered items, stamping last_seen to now (UTC)."""
    now = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(db_path)
    try:
        for item in items:
            con.execute(
                "INSERT OR REPLACE INTO discovered_tools"
                " (source_url, source_slug, kind, name, relative_path, description, source_sha, last_seen)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.source_url,
                    item.source_slug,
                    item.kind,
                    item.name,
                    item.relative_path,
                    item.description,
                    item.source_sha,
                    now,
                ),
            )
        con.commit()
    finally:
        con.close()


def prune_stale(db_path: Path, source_slug: str, cutoff: datetime) -> int:
    """Delete rows for source_slug with last_seen older than cutoff. Returns deleted count."""
    cutoff_str = cutoff.isoformat()
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            "DELETE FROM discovered_tools WHERE source_slug = ? AND last_seen < ?",
            (source_slug, cutoff_str),
        )
        con.commit()
        return cur.rowcount
    finally:
        con.close()


def list_discovered(
    db_path: Path,
    kind: str | None = None,
    source_slug: str | None = None,
) -> list[DiscoveredItem]:
    """Return discovered tools, optionally filtered, in stable order."""
    query = (
        "SELECT source_url, source_slug, kind, name, relative_path, description, source_sha"
        " FROM discovered_tools"
    )
    params: list[str] = []
    conditions: list[str] = []

    if kind is not None:
        conditions.append("kind = ?")
        params.append(kind)
    if source_slug is not None:
        conditions.append("source_slug = ?")
        params.append(source_slug)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY source_slug, kind, name"

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(query, params).fetchall()
    finally:
        con.close()

    return [
        DiscoveredItem(
            source_url=row[0],
            source_slug=row[1],
            kind=row[2],
            name=row[3],
            relative_path=row[4],
            description=row[5],
            source_sha=row[6],
        )
        for row in rows
    ]
