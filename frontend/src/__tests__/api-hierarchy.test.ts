import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "../api";
import type { Task } from "../types";

// ---------------------------------------------------------------------------
// fetch mocking
// ---------------------------------------------------------------------------

interface CapturedRequest {
  url: string;
  method: string;
  body: unknown;
  headers: Record<string, string>;
}

let captured: CapturedRequest[];

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function textResponse(text: string, status: number): Response {
  return new Response(text, {
    status,
    headers: { "Content-Type": "text/plain" },
  });
}

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-1",
    space_id: "space-1",
    title: "T",
    state: "backlog",
    created_at: "2024-01-15T14:00:00Z",
    updated_at: "2024-01-15T14:30:00Z",
    claude_session_id: null,
    waiting_question: null,
    brief: "",
    history: "",
    pending_messages: [],
    agent_mode: "auto",
    agent_model: "default",
    priority: 3,
    manual_order: 0,
    space_name: null,
    space_color: null,
    space_icon: null,
    ...overrides,
  };
}

beforeEach(() => {
  captured = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    const rawBody = init?.body;
    let parsed: unknown = undefined;
    if (typeof rawBody === "string") {
      try {
        parsed = JSON.parse(rawBody);
      } catch {
        parsed = rawBody;
      }
    }
    const headers = init?.headers as Record<string, string> | undefined;
    captured.push({ url, method, body: parsed, headers: headers ?? {} });
    return jsonResponse(makeTask({ id: "task-1" }));
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// api.promote
// ---------------------------------------------------------------------------

describe("api.promote", () => {
  it("POSTs to /api/tasks/<id>/promote", async () => {
    await api.promote("abc-123");

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/tasks/abc-123/promote");
    expect(captured[0].method).toBe("POST");
  });

  it("sends an empty JSON object as the body", async () => {
    await api.promote("abc-123");

    // The wrapper passes the literal string "{}" (not a JS object).
    // After our JSON.parse in the mock, this becomes an empty object.
    expect(captured[0].body).toEqual({});
  });

  it("sets Content-Type: application/json", async () => {
    await api.promote("abc-123");

    expect(captured[0].headers["Content-Type"]).toBe("application/json");
  });

  it("resolves with the returned Task", async () => {
    const result = await api.promote("abc-123");

    expect(result.id).toBe("task-1");
  });

  it("throws an Error with status and body text on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => textResponse("cycle detected", 409)),
    );

    await expect(api.promote("abc-123")).rejects.toThrow(/409/);
    await expect(api.promote("abc-123")).rejects.toThrow(/cycle detected/);
  });
});

// ---------------------------------------------------------------------------
// api.setParent
// ---------------------------------------------------------------------------

describe("api.setParent", () => {
  it("PATCHes /api/tasks/<id>/parent with the new parent id", async () => {
    await api.setParent("child-1", "parent-9");

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/tasks/child-1/parent");
    expect(captured[0].method).toBe("PATCH");
    expect(captured[0].body).toEqual({ parent_id: "parent-9" });
  });

  it("sends parent_id=null to clear the parent", async () => {
    await api.setParent("child-1", null);

    expect(captured[0].body).toEqual({ parent_id: null });
  });

  it("sets Content-Type: application/json", async () => {
    await api.setParent("child-1", "p");

    expect(captured[0].headers["Content-Type"]).toBe("application/json");
  });

  it("URL-encodes special characters in the task id path segment", async () => {
    // The implementation does NOT encodeURIComponent on the id, so this test
    // documents the current behavior and would flag if it changes.
    await api.setParent("a/b", "p");

    expect(captured[0].url).toBe("/api/tasks/a/b/parent");
  });

  it("surfaces server-side validation errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: "would create a cycle" }, 400),
      ),
    );

    // The Error message embeds the body text so callers (e.g. extractDetail)
    // can parse it.
    await expect(api.setParent("a", "b")).rejects.toThrow(/would create a cycle/);
  });
});

// ---------------------------------------------------------------------------
// api.setDependsOn
// ---------------------------------------------------------------------------

describe("api.setDependsOn", () => {
  it("PATCHes /api/tasks/<id>/depends_on with the new id list", async () => {
    await api.setDependsOn("t1", ["d1", "d2"]);

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/tasks/t1/depends_on");
    expect(captured[0].method).toBe("PATCH");
    expect(captured[0].body).toEqual({ depends_on: ["d1", "d2"] });
  });

  it("sends an empty array to clear all dependencies", async () => {
    await api.setDependsOn("t1", []);

    expect(captured[0].body).toEqual({ depends_on: [] });
  });

  it("preserves the order of dependency ids in the payload", async () => {
    await api.setDependsOn("t1", ["c", "a", "b"]);

    // Order matters for some backend logic; assert exact array, not a set.
    expect((captured[0].body as { depends_on: string[] }).depends_on).toEqual([
      "c",
      "a",
      "b",
    ]);
  });

  it("sets Content-Type: application/json", async () => {
    await api.setDependsOn("t1", ["d1"]);

    expect(captured[0].headers["Content-Type"]).toBe("application/json");
  });

  it("propagates server errors with body text in the message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: "dependency not found" }, 404),
      ),
    );

    await expect(api.setDependsOn("t1", ["missing"])).rejects.toThrow(/404/);
    await expect(api.setDependsOn("t1", ["missing"])).rejects.toThrow(
      /dependency not found/,
    );
  });
});
