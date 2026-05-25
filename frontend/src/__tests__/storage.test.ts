import { describe, it, expect, beforeEach } from "vitest";
import {
  STORAGE_KEYS,
  readCardViewMode,
  writeCardViewMode,
  readTreeExpanded,
  writeTreeExpanded,
} from "../lib/storage";

describe("storage — cardViewMode", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("readCardViewMode defaults to 'full' when nothing is stored", () => {
    expect(readCardViewMode()).toBe("full");
  });

  it("readCardViewMode returns 'minimal' when stored value is 'minimal'", () => {
    window.localStorage.setItem(STORAGE_KEYS.cardViewMode, "minimal");
    expect(readCardViewMode()).toBe("minimal");
  });

  it("readCardViewMode returns 'full' when stored value is 'full'", () => {
    window.localStorage.setItem(STORAGE_KEYS.cardViewMode, "full");
    expect(readCardViewMode()).toBe("full");
  });

  it("readCardViewMode coerces unexpected stored values to 'full'", () => {
    window.localStorage.setItem(STORAGE_KEYS.cardViewMode, "weird-value");
    expect(readCardViewMode()).toBe("full");
  });

  it("readCardViewMode coerces empty string to 'full'", () => {
    window.localStorage.setItem(STORAGE_KEYS.cardViewMode, "");
    expect(readCardViewMode()).toBe("full");
  });

  it("writeCardViewMode persists 'minimal'", () => {
    writeCardViewMode("minimal");
    expect(window.localStorage.getItem(STORAGE_KEYS.cardViewMode)).toBe(
      "minimal",
    );
  });

  it("writeCardViewMode persists 'full'", () => {
    writeCardViewMode("full");
    expect(window.localStorage.getItem(STORAGE_KEYS.cardViewMode)).toBe("full");
  });

  it("write then read round-trips correctly for 'minimal'", () => {
    writeCardViewMode("minimal");
    expect(readCardViewMode()).toBe("minimal");
  });

  it("write then read round-trips correctly for 'full'", () => {
    writeCardViewMode("full");
    expect(readCardViewMode()).toBe("full");
  });

  it("writeCardViewMode overwrites previous value", () => {
    writeCardViewMode("minimal");
    writeCardViewMode("full");
    expect(readCardViewMode()).toBe("full");
  });

  it("uses the documented localStorage key", () => {
    expect(STORAGE_KEYS.cardViewMode).toBe("cronos.cardViewMode");
  });
});

describe("storage — tree expanded state", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("readTreeExpanded returns [] when nothing is stored (null spaceId)", () => {
    expect(readTreeExpanded(null)).toEqual([]);
  });

  it("readTreeExpanded returns [] when nothing is stored (named spaceId)", () => {
    expect(readTreeExpanded("space-a")).toEqual([]);
  });

  it("readTreeExpanded returns the parsed array when stored", () => {
    window.localStorage.setItem(
      "cronos:tree:expanded:_all",
      JSON.stringify(["task-1", "task-2"]),
    );

    expect(readTreeExpanded(null)).toEqual(["task-1", "task-2"]);
  });

  it("readTreeExpanded returns [] when stored value is invalid JSON", () => {
    window.localStorage.setItem(
      "cronos:tree:expanded:_all",
      "{not valid json",
    );

    expect(readTreeExpanded(null)).toEqual([]);
  });

  it("writeTreeExpanded stores the array as JSON under the _all key for null spaceId", () => {
    writeTreeExpanded(null, ["task-1", "task-2"]);

    expect(window.localStorage.getItem("cronos:tree:expanded:_all")).toBe(
      JSON.stringify(["task-1", "task-2"]),
    );
  });

  it("writeTreeExpanded stores under the space-keyed key when a spaceId is provided", () => {
    writeTreeExpanded("space-42", ["task-a"]);

    expect(window.localStorage.getItem("cronos:tree:expanded:space-42")).toBe(
      JSON.stringify(["task-a"]),
    );
  });

  it("write then read round-trips (null spaceId)", () => {
    writeTreeExpanded(null, ["a", "b", "c"]);

    expect(readTreeExpanded(null)).toEqual(["a", "b", "c"]);
  });

  it("write then read round-trips (named spaceId)", () => {
    writeTreeExpanded("space-X", ["only"]);

    expect(readTreeExpanded("space-X")).toEqual(["only"]);
  });

  it("uses the _all key when spaceId is null (reads do not see space-keyed writes)", () => {
    writeTreeExpanded("space-A", ["from-A"]);

    // The "all" view reads from a different key, so it sees nothing.
    expect(readTreeExpanded(null)).toEqual([]);
  });

  it("uses the spaceId key when provided (reads do not see _all writes)", () => {
    writeTreeExpanded(null, ["from-all"]);

    expect(readTreeExpanded("space-A")).toEqual([]);
  });

  it("different spaceIds use different localStorage keys (no cross-bleed)", () => {
    writeTreeExpanded("space-A", ["a-only"]);
    writeTreeExpanded("space-B", ["b-only"]);

    expect(readTreeExpanded("space-A")).toEqual(["a-only"]);
    expect(readTreeExpanded("space-B")).toEqual(["b-only"]);
  });

  it("writeTreeExpanded overwrites the previous value for the same key", () => {
    writeTreeExpanded("space-A", ["first"]);
    writeTreeExpanded("space-A", ["second"]);

    expect(readTreeExpanded("space-A")).toEqual(["second"]);
  });

  it("writeTreeExpanded persists an empty array (and read returns it)", () => {
    writeTreeExpanded(null, ["x"]);
    writeTreeExpanded(null, []);

    expect(readTreeExpanded(null)).toEqual([]);
    // The key still exists with the serialized empty array.
    expect(window.localStorage.getItem("cronos:tree:expanded:_all")).toBe("[]");
  });
});
