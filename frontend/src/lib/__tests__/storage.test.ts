import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  STORAGE_KEYS,
  readBoardSpaceFilter,
  writeBoardSpaceFilter,
  readCardViewMode,
  writeCardViewMode,
  readBoardSortMode,
  writeBoardSortMode,
} from "../storage";

// jsdom provides a real localStorage — clear it between tests.
beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

describe("STORAGE_KEYS", () => {
  it("exports expected key names", () => {
    expect(STORAGE_KEYS.boardSpaceFilter).toBe("cronos.boardSpaceFilter");
    expect(STORAGE_KEYS.cardViewMode).toBe("cronos.cardViewMode");
    expect(STORAGE_KEYS.boardSortMode).toBe("cronos.boardSortMode");
  });
});

describe("readBoardSpaceFilter", () => {
  it("returns null when nothing is stored", () => {
    expect(readBoardSpaceFilter()).toBeNull();
  });

  it("returns null when the stored value is 'all'", () => {
    localStorage.setItem(STORAGE_KEYS.boardSpaceFilter, "all");
    expect(readBoardSpaceFilter()).toBeNull();
  });

  it("returns the stored space ID when one is present", () => {
    localStorage.setItem(STORAGE_KEYS.boardSpaceFilter, "space-abc");
    expect(readBoardSpaceFilter()).toBe("space-abc");
  });
});

describe("writeBoardSpaceFilter", () => {
  it("stores the space ID and can be read back", () => {
    writeBoardSpaceFilter("space-1");
    expect(localStorage.getItem(STORAGE_KEYS.boardSpaceFilter)).toBe("space-1");
    expect(readBoardSpaceFilter()).toBe("space-1");
  });

  it("stores 'all' when spaceId is null", () => {
    writeBoardSpaceFilter(null);
    expect(localStorage.getItem(STORAGE_KEYS.boardSpaceFilter)).toBe("all");
    expect(readBoardSpaceFilter()).toBeNull();
  });
});

describe("readCardViewMode", () => {
  it("returns 'full' when nothing is stored", () => {
    expect(readCardViewMode()).toBe("full");
  });

  it("returns 'minimal' when 'minimal' is stored", () => {
    localStorage.setItem(STORAGE_KEYS.cardViewMode, "minimal");
    expect(readCardViewMode()).toBe("minimal");
  });

  it("returns 'full' for any unrecognised value", () => {
    localStorage.setItem(STORAGE_KEYS.cardViewMode, "unknown");
    expect(readCardViewMode()).toBe("full");
  });
});

describe("writeCardViewMode", () => {
  it("stores the view mode and can be read back", () => {
    writeCardViewMode("minimal");
    expect(readCardViewMode()).toBe("minimal");

    writeCardViewMode("full");
    expect(readCardViewMode()).toBe("full");
  });
});

describe("readBoardSortMode", () => {
  it("returns 'manual' when nothing is stored", () => {
    expect(readBoardSortMode()).toBe("manual");
  });

  it("returns 'priority' when 'priority' is stored", () => {
    localStorage.setItem(STORAGE_KEYS.boardSortMode, "priority");
    expect(readBoardSortMode()).toBe("priority");
  });

  it("returns 'manual' for any unrecognised value", () => {
    localStorage.setItem(STORAGE_KEYS.boardSortMode, "unknown");
    expect(readBoardSortMode()).toBe("manual");
  });
});

describe("writeBoardSortMode", () => {
  it("stores the sort mode and can be read back", () => {
    writeBoardSortMode("priority");
    expect(readBoardSortMode()).toBe("priority");

    writeBoardSortMode("manual");
    expect(readBoardSortMode()).toBe("manual");
  });
});
