// Centralized localStorage keys + helpers used across pages.

export const STORAGE_KEYS = {
  boardSpaceFilter: "cronos.boardSpaceFilter",
  cardViewMode: "cronos.cardViewMode",
  boardSortMode: "cronos.boardSortMode",
} as const;

// Tree expand/collapse state — keyed per space (or "_all" for the all-spaces view)
export function readTreeExpanded(spaceId: string | null): string[] {
  const key = `cronos:tree:expanded:${spaceId ?? "_all"}`;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    return JSON.parse(raw) as string[];
  } catch {
    return [];
  }
}

export function writeTreeExpanded(spaceId: string | null, ids: string[]): void {
  const key = `cronos:tree:expanded:${spaceId ?? "_all"}`;
  try {
    localStorage.setItem(key, JSON.stringify(ids));
  } catch {
    // localStorage unavailable — silently fall back
  }
}

export function readBoardSpaceFilter(): string | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.boardSpaceFilter);
    if (!raw) return null;
    return raw === "all" ? null : raw;
  } catch {
    return null;
  }
}

export function writeBoardSpaceFilter(spaceId: string | null): void {
  try {
    window.localStorage.setItem(
      STORAGE_KEYS.boardSpaceFilter,
      spaceId ?? "all",
    );
  } catch {
    // localStorage unavailable (private mode) — silently fall back.
  }
}

export type CardViewMode = "full" | "minimal";

export function readCardViewMode(): CardViewMode {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.cardViewMode);
    return raw === "minimal" ? "minimal" : "full";
  } catch {
    return "full";
  }
}

export function writeCardViewMode(mode: CardViewMode): void {
  try {
    window.localStorage.setItem(STORAGE_KEYS.cardViewMode, mode);
  } catch {
    // localStorage unavailable (private mode) — silently fall back.
  }
}

export type BoardSortMode = "manual" | "priority";

export function readBoardSortMode(): BoardSortMode {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.boardSortMode);
    return raw === "priority" ? "priority" : "manual";
  } catch {
    return "manual";
  }
}

export function writeBoardSortMode(mode: BoardSortMode): void {
  try {
    window.localStorage.setItem(STORAGE_KEYS.boardSortMode, mode);
  } catch {
    // localStorage unavailable (private mode) — silently fall back.
  }
}
