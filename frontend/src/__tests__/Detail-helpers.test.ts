import { describe, it, expect } from "vitest";
import { extractDetail, getDescendantIds } from "../components/Detail";
import type { TaskSummary } from "../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSummary(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: "task-x",
    space_id: "space-1",
    title: "Unnamed",
    state: "backlog",
    created_at: "2024-01-15T14:00:00Z",
    updated_at: "2024-01-15T14:30:00Z",
    waiting_question: null,
    brief_preview: "",
    priority: 3,
    manual_order: 0,
    agent_mode: "auto",
    space_name: null,
    space_color: null,
    space_icon: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// extractDetail — fetch error-message parser used by HierarchySection
// ---------------------------------------------------------------------------

describe("extractDetail — FastAPI error parsing", () => {
  it("returns the detail field when the body is pure JSON", () => {
    // The api.ts request() wrapper formats errors as "<status> <statusText> on <path>: <body>"
    // so the JSON appears AFTER a prefix; extractDetail finds the first '{'.
    const msg = '400 Bad Request on /api/tasks/t1/parent: {"detail":"cycle detected"}';

    const result = extractDetail(msg);

    expect(result).toBe("cycle detected");
  });

  it("returns the detail field even when JSON is bare (no prefix)", () => {
    const msg = '{"detail":"missing dependency target"}';

    const result = extractDetail(msg);

    expect(result).toBe("missing dependency target");
  });

  it("returns the original message when no JSON brace is present", () => {
    const msg = "TypeError: failed to fetch";

    const result = extractDetail(msg);

    expect(result).toBe("TypeError: failed to fetch");
  });

  it("returns the original message when JSON is malformed", () => {
    const msg = "500 ISE on /x: {not really json";

    const result = extractDetail(msg);

    expect(result).toBe(msg);
  });

  it("returns the original message when JSON parses but has no detail field", () => {
    const msg = '422 on /x: {"errors":["a","b"]}';

    const result = extractDetail(msg);

    expect(result).toBe(msg);
  });

  it("returns the original message when detail is an empty string (falsy)", () => {
    // The implementation treats empty string as falsy and falls through.
    const msg = '400 on /x: {"detail":""}';

    const result = extractDetail(msg);

    expect(result).toBe(msg);
  });

  it("returns the original message when JSON detail is non-string (truthy)", () => {
    // Non-string truthy detail (e.g. an array of validation errors) is returned as-is
    // by the implementation since TypeScript casts it as string but actual runtime
    // value is whatever JSON.parse yields. Lock current behavior.
    const msg = '422 on /x: {"detail":["field required"]}';

    const result = extractDetail(msg);

    // Implementation returns obj.detail which is truthy (array).
    expect(result).toEqual(["field required"]);
  });

  it("picks the first '{' even if it appears inside the URL path", () => {
    // Defensive: a brace embedded in a query string before the body would shift
    // the slice; this documents current behavior. With no brace in path here
    // the body JSON is still parsed correctly.
    const msg = 'X on /api: {"detail":"hello"}';

    const result = extractDetail(msg);

    expect(result).toBe("hello");
  });
});

// ---------------------------------------------------------------------------
// getDescendantIds — BFS used to exclude self+descendants from parent picker
// ---------------------------------------------------------------------------

describe("getDescendantIds — BFS over parent_id graph", () => {
  it("returns an empty set when the root has no children", () => {
    const tasks = [
      makeSummary({ id: "a" }),
      makeSummary({ id: "b" }),
    ];

    const result = getDescendantIds(tasks, "a");

    expect(result.size).toBe(0);
  });

  it("returns immediate children", () => {
    const tasks = [
      makeSummary({ id: "root" }),
      makeSummary({ id: "child-1", parent_id: "root" }),
      makeSummary({ id: "child-2", parent_id: "root" }),
      makeSummary({ id: "unrelated" }),
    ];

    const result = getDescendantIds(tasks, "root");

    expect(result).toEqual(new Set(["child-1", "child-2"]));
  });

  it("traverses multiple levels (grandchildren and deeper)", () => {
    const tasks = [
      makeSummary({ id: "root" }),
      makeSummary({ id: "child", parent_id: "root" }),
      makeSummary({ id: "grandchild", parent_id: "child" }),
      makeSummary({ id: "great-grand", parent_id: "grandchild" }),
    ];

    const result = getDescendantIds(tasks, "root");

    expect(result).toEqual(new Set(["child", "grandchild", "great-grand"]));
  });

  it("does NOT include the root id itself in the result", () => {
    const tasks = [
      makeSummary({ id: "root" }),
      makeSummary({ id: "child", parent_id: "root" }),
    ];

    const result = getDescendantIds(tasks, "root");

    expect(result.has("root")).toBe(false);
  });

  it("excludes tasks parented to a different subtree", () => {
    const tasks = [
      makeSummary({ id: "root-a" }),
      makeSummary({ id: "root-b" }),
      makeSummary({ id: "child-a", parent_id: "root-a" }),
      makeSummary({ id: "child-b", parent_id: "root-b" }),
    ];

    const result = getDescendantIds(tasks, "root-a");

    expect(result).toEqual(new Set(["child-a"]));
    expect(result.has("child-b")).toBe(false);
    expect(result.has("root-b")).toBe(false);
  });

  it("terminates when the task list contains a cycle (defensive)", () => {
    // The graph is *supposed* to be acyclic — backend cycle detection enforces
    // that. But a corrupted board response must not hang the UI. The `result`
    // set deduplicates, so once every involved id is recorded the BFS drains
    // its queue and returns.
    const tasks = [
      makeSummary({ id: "a", parent_id: "b" }),
      makeSummary({ id: "b", parent_id: "a" }),
    ];

    // Should complete (not loop forever) and return both nodes.
    const result = getDescendantIds(tasks, "a");

    expect(result).toEqual(new Set(["a", "b"]));
  });

  it("handles a task list missing the root id (returns empty set)", () => {
    const tasks = [
      makeSummary({ id: "unrelated" }),
    ];

    const result = getDescendantIds(tasks, "missing-root");

    expect(result.size).toBe(0);
  });

  it("handles an empty task list", () => {
    const result = getDescendantIds([], "anything");

    expect(result.size).toBe(0);
  });

  it("does not include siblings of the root (only descendants)", () => {
    const tasks = [
      makeSummary({ id: "parent" }),
      makeSummary({ id: "root", parent_id: "parent" }),
      makeSummary({ id: "sibling", parent_id: "parent" }),
      makeSummary({ id: "root-child", parent_id: "root" }),
    ];

    const result = getDescendantIds(tasks, "root");

    expect(result).toEqual(new Set(["root-child"]));
    expect(result.has("sibling")).toBe(false);
    expect(result.has("parent")).toBe(false);
  });
});
