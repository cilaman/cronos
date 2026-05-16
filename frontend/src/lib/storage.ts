// Centralized localStorage keys + helpers used across pages.

export const STORAGE_KEYS = {
  boardSpaceFilter: "cronos.boardSpaceFilter",
} as const;

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
