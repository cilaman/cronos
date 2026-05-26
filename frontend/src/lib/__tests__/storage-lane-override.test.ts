import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  readBoardLaneOverride,
  writeBoardLaneOverride,
} from "../storage";
import type { TaskState } from "../../types";

// ---------------------------------------------------------------------------
// localStorage shim
// ---------------------------------------------------------------------------
// The jsdom build wired into this Vitest env exposes `window.localStorage`
// without the Storage prototype methods (setItem/getItem/removeItem/clear are
// all undefined). This breaks the pre-existing storage.test.ts top-level
// beforeEach. To keep the new helpers under test, we install a Map-backed
// shim per-test in this file.

let originalLocalStorage: Storage | undefined;
let store: Map<string, string>;

beforeEach(() => {
  originalLocalStorage = Object.getOwnPropertyDescriptor(
    window,
    "localStorage",
  )?.value;
  store = new Map();
  const shim: Storage = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null;
    },
    key(i: number) {
      return [...store.keys()][i] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: shim,
  });
});

afterEach(() => {
  if (originalLocalStorage) {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: originalLocalStorage,
    });
  }
});

// ---------------------------------------------------------------------------
// readBoardLaneOverride
// Key format: cronos:board:lanes:{spaceId ?? "_all"}:{viewId ?? "_default"}
// ---------------------------------------------------------------------------

describe("readBoardLaneOverride", () => {
  it("returns null when no override is stored", () => {
    expect(readBoardLaneOverride("space-1", null)).toBeNull();
  });

  it("uses '_all' as the space segment when spaceId is null", () => {
    localStorage.setItem(
      "cronos:board:lanes:_all:_default",
      JSON.stringify(["active"]),
    );
    expect(readBoardLaneOverride(null, null)).toEqual(["active"]);
    // A different (space, view) key must not collide with the all-spaces key.
    expect(readBoardLaneOverride("space-1", null)).toBeNull();
  });

  it("uses '_default' as the view segment when viewId is null", () => {
    localStorage.setItem(
      "cronos:board:lanes:space-1:_default",
      JSON.stringify(["backlog", "active"]),
    );
    expect(readBoardLaneOverride("space-1", null)).toEqual([
      "backlog",
      "active",
    ]);
  });

  it("uses the provided viewId in the key when set", () => {
    localStorage.setItem(
      "cronos:board:lanes:space-1:focus",
      JSON.stringify(["active", "waiting"]),
    );
    expect(readBoardLaneOverride("space-1", "focus")).toEqual([
      "active",
      "waiting",
    ]);
    // The same space with a different view must read its own key.
    expect(readBoardLaneOverride("space-1", "other")).toBeNull();
  });

  it("filters out unknown lane state values", () => {
    localStorage.setItem(
      "cronos:board:lanes:space-1:_default",
      JSON.stringify(["backlog", "made-up", "active", "fnord"]),
    );
    expect(readBoardLaneOverride("space-1", null)).toEqual([
      "backlog",
      "active",
    ]);
  });

  it("filters out non-string values inside the array", () => {
    localStorage.setItem(
      "cronos:board:lanes:space-1:_default",
      JSON.stringify(["backlog", 42, null, "active", { state: "done" }]),
    );
    expect(readBoardLaneOverride("space-1", null)).toEqual([
      "backlog",
      "active",
    ]);
  });

  it("returns null when the stored value is not valid JSON", () => {
    localStorage.setItem("cronos:board:lanes:space-1:_default", "{not json");
    expect(readBoardLaneOverride("space-1", null)).toBeNull();
  });

  it("returns null when the parsed JSON is not an array", () => {
    localStorage.setItem(
      "cronos:board:lanes:space-1:_default",
      JSON.stringify({ lanes: ["active"] }),
    );
    expect(readBoardLaneOverride("space-1", null)).toBeNull();
  });

  it("returns an empty array when the stored array contains only invalid values (zero-lane override)", () => {
    localStorage.setItem(
      "cronos:board:lanes:space-1:_default",
      JSON.stringify(["nope", "still nope"]),
    );
    expect(readBoardLaneOverride("space-1", null)).toEqual([]);
  });

  it("accepts all known lane states including archived", () => {
    const all: TaskState[] = [
      "backlog",
      "active",
      "waiting",
      "done",
      "archived",
    ];
    localStorage.setItem(
      "cronos:board:lanes:space-1:_default",
      JSON.stringify(all),
    );
    expect(readBoardLaneOverride("space-1", null)).toEqual(all);
  });
});

// ---------------------------------------------------------------------------
// writeBoardLaneOverride
// ---------------------------------------------------------------------------

describe("writeBoardLaneOverride", () => {
  it("round-trips a non-null lane list", () => {
    writeBoardLaneOverride("space-1", null, ["active", "waiting"]);
    expect(readBoardLaneOverride("space-1", null)).toEqual([
      "active",
      "waiting",
    ]);
  });

  it("deletes the key when called with null", () => {
    writeBoardLaneOverride("space-1", null, ["active"]);
    expect(
      localStorage.getItem("cronos:board:lanes:space-1:_default"),
    ).not.toBeNull();

    writeBoardLaneOverride("space-1", null, null);
    expect(
      localStorage.getItem("cronos:board:lanes:space-1:_default"),
    ).toBeNull();
    expect(readBoardLaneOverride("space-1", null)).toBeNull();
  });

  it("writes to the spaceId-and-viewId-specific key only", () => {
    writeBoardLaneOverride("space-1", "focus", ["active"]);
    expect(localStorage.getItem("cronos:board:lanes:space-1:focus")).toBe(
      JSON.stringify(["active"]),
    );
    // Sibling keys are unaffected.
    expect(
      localStorage.getItem("cronos:board:lanes:space-1:_default"),
    ).toBeNull();
    expect(localStorage.getItem("cronos:board:lanes:_all:focus")).toBeNull();
  });

  it("writes an empty array verbatim (caller's responsibility to decide null vs empty)", () => {
    writeBoardLaneOverride("space-1", null, []);
    // Stored as JSON "[]", not removed.
    expect(localStorage.getItem("cronos:board:lanes:space-1:_default")).toBe(
      "[]",
    );
    expect(readBoardLaneOverride("space-1", null)).toEqual([]);
  });

  it("overwrites a previous value at the same key", () => {
    writeBoardLaneOverride("space-1", null, ["backlog"]);
    writeBoardLaneOverride("space-1", null, ["active", "done"]);
    expect(readBoardLaneOverride("space-1", null)).toEqual([
      "active",
      "done",
    ]);
  });

  it("uses _all/_default segments when both arguments are null", () => {
    writeBoardLaneOverride(null, null, ["waiting"]);
    expect(localStorage.getItem("cronos:board:lanes:_all:_default")).toBe(
      JSON.stringify(["waiting"]),
    );
  });
});
