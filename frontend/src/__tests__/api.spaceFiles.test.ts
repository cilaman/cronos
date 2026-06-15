import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, spaceFileUrl } from "../api";
import type { TaskFile } from "../types";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function makeFile(overrides: Partial<TaskFile> = {}): TaskFile {
  return {
    name: "notes.md",
    path: "2026-06-01-1234-some-task/notes.md",
    size: 42,
    modified_at: "2026-06-01T10:00:00Z",
    is_dir: false,
    category: "text",
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface CapturedRequest {
  url: string;
  method: string;
}

let captured: CapturedRequest[];

beforeEach(() => {
  captured = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      captured.push({ url, method });
      return jsonResponse([makeFile()]);
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// spaceFileUrl
// ---------------------------------------------------------------------------

describe("spaceFileUrl", () => {
  it("returns the correct URL without download flag", () => {
    expect(spaceFileUrl("my-space", "task-ws/report.md")).toBe(
      "/api/spaces/my-space/files/task-ws/report.md",
    );
  });

  it("encodes each path segment independently", () => {
    const url = spaceFileUrl("my-space", "task ws/file name.md");
    expect(url).toBe("/api/spaces/my-space/files/task%20ws/file%20name.md");
  });

  it("encodes special characters per segment (slashes preserved as separators)", () => {
    const url = spaceFileUrl("my-space", "a+b/c&d/e=f.txt");
    expect(url).toBe("/api/spaces/my-space/files/a%2Bb/c%26d/e%3Df.txt");
  });

  it("appends ?download=true only when download=true", () => {
    expect(spaceFileUrl("my-space", "f.md", true)).toContain("?download=true");
    expect(spaceFileUrl("my-space", "f.md", false)).not.toContain("download");
    expect(spaceFileUrl("my-space", "f.md")).not.toContain("download");
  });

  it("encodes spaceId with encodeURIComponent", () => {
    const url = spaceFileUrl("my space", "file.md");
    expect(url).toBe("/api/spaces/my%20space/files/file.md");
  });

  it("does not double-encode a clean path", () => {
    const url = spaceFileUrl("space-1", "ws-abc/subdir/note.md");
    expect(url).toBe("/api/spaces/space-1/files/ws-abc/subdir/note.md");
  });
});

// ---------------------------------------------------------------------------
// api.spaceFiles
// ---------------------------------------------------------------------------

describe("api.spaceFiles", () => {
  it("GETs /api/spaces/{spaceId}/files", async () => {
    await api.spaceFiles("cronos-dev");

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/spaces/cronos-dev/files");
    expect(captured[0].method).toBe("GET");
  });

  it("returns parsed TaskFile[]", async () => {
    const files = await api.spaceFiles("my-space");

    expect(Array.isArray(files)).toBe(true);
    expect(files[0].name).toBe("notes.md");
    expect(files[0].path).toBe("2026-06-01-1234-some-task/notes.md");
    expect(files[0].category).toBe("text");
  });

  it("returns empty array when backend returns []", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([])),
    );

    const files = await api.spaceFiles("empty-space");
    expect(files).toEqual([]);
  });

  it("propagates 404 as a thrown error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Space not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(api.spaceFiles("no-such-space")).rejects.toThrow("404");
  });

  it("propagates 500 as a thrown error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response("Internal Server Error", {
          status: 500,
          headers: { "Content-Type": "text/plain" },
        }),
      ),
    );

    await expect(api.spaceFiles("my-space")).rejects.toThrow("500");
  });

  it("URL-encodes spaceId in the request URL", async () => {
    await api.spaceFiles("my space id");

    expect(captured[0].url).toBe("/api/spaces/my%20space%20id/files");
  });
});

// ---------------------------------------------------------------------------
// R6: existing taskFiles / taskFileUrl APIs are unmodified
// ---------------------------------------------------------------------------

describe("R6: existing task file APIs remain unchanged", () => {
  it("api.taskFiles still calls /api/tasks/{taskId}/files", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        captured.push({ url, method: (init?.method ?? "GET").toUpperCase() });
        return jsonResponse([makeFile()]);
      }),
    );

    await api.taskFiles("task-123");

    expect(captured[0].url).toBe("/api/tasks/task-123/files");
  });

  it("spaceFiles and taskFiles are independent — spaceFiles does not call task endpoint", async () => {
    await api.spaceFiles("my-space");

    expect(captured[0].url).not.toContain("/api/tasks/");
    expect(captured[0].url).toContain("/api/spaces/");
  });
});
