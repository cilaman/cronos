import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "../api";
import type { Harness } from "../types";

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

function makeHarness(overrides: Partial<Harness> = {}): Harness {
  return {
    name: "my-harness",
    description: "A test harness",
    nodes: [],
    edges: [],
    variables: {},
    created_at: "2024-01-15T14:00:00Z",
    updated_at: "2024-01-15T14:30:00Z",
    version: 1,
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
    // For DELETE (204-like), return empty JSON array or object as needed
    if (method === "DELETE") {
      return new Response(null, { status: 204 });
    }
    return jsonResponse(makeHarness());
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// api.listHarnesses
// ---------------------------------------------------------------------------

describe("api.listHarnesses", () => {
  it("GETs /api/spaces/{spaceId}/harnesses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        const method = (init?.method ?? "GET").toUpperCase();
        const headers = init?.headers as Record<string, string> | undefined;
        captured.push({ url, method, body: undefined, headers: headers ?? {} });
        return jsonResponse([makeHarness()]);
      }),
    );

    const result = await api.listHarnesses("space-1");

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/spaces/space-1/harnesses");
    expect(captured[0].method).toBe("GET");
    expect(Array.isArray(result)).toBe(true);
    expect(result[0].name).toBe("my-harness");
  });

  it("uses the correct spaceId in the URL", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        const method = (init?.method ?? "GET").toUpperCase();
        captured.push({ url, method, body: undefined, headers: {} });
        return jsonResponse([]);
      }),
    );

    await api.listHarnesses("another-space");

    expect(captured[0].url).toBe("/api/spaces/another-space/harnesses");
  });
});

// ---------------------------------------------------------------------------
// api.getHarness
// ---------------------------------------------------------------------------

describe("api.getHarness", () => {
  it("GETs /api/spaces/{spaceId}/harnesses/{name}", async () => {
    await api.getHarness("space-1", "my-harness");

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/spaces/space-1/harnesses/my-harness");
    expect(captured[0].method).toBe("GET");
  });

  it("URL-encodes the name using encodeURIComponent", async () => {
    await api.getHarness("space-1", "my harness");

    expect(captured[0].url).toBe("/api/spaces/space-1/harnesses/my%20harness");
  });

  it("URL-encodes names with special characters", async () => {
    await api.getHarness("space-1", "harness/special+chars");

    expect(captured[0].url).toBe(
      `/api/spaces/space-1/harnesses/${encodeURIComponent("harness/special+chars")}`,
    );
  });

  it("resolves with the returned Harness object", async () => {
    const result = await api.getHarness("space-1", "my-harness");

    expect(result.name).toBe("my-harness");
  });
});

// ---------------------------------------------------------------------------
// api.createHarness
// ---------------------------------------------------------------------------

describe("api.createHarness", () => {
  it("POSTs to /api/spaces/{spaceId}/harnesses", async () => {
    const body = {
      name: "new-harness",
      nodes: [],
      edges: [],
      variables: {},
    };

    await api.createHarness("space-1", body);

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/spaces/space-1/harnesses");
    expect(captured[0].method).toBe("POST");
  });

  it("sends the harness body as JSON", async () => {
    const body = {
      name: "new-harness",
      description: "desc",
      nodes: [],
      edges: [],
      variables: { key: "value" },
    };

    await api.createHarness("space-1", body);

    expect(captured[0].body).toEqual(body);
  });

  it("sets Content-Type: application/json", async () => {
    await api.createHarness("space-1", {
      name: "h",
      nodes: [],
      edges: [],
      variables: {},
    });

    expect(captured[0].headers["Content-Type"]).toBe("application/json");
  });

  it("resolves with the created Harness", async () => {
    const result = await api.createHarness("space-1", {
      name: "my-harness",
      nodes: [],
      edges: [],
      variables: {},
    });

    expect(result.name).toBe("my-harness");
  });
});

// ---------------------------------------------------------------------------
// api.updateHarness
// ---------------------------------------------------------------------------

describe("api.updateHarness", () => {
  it("PUTs to /api/spaces/{spaceId}/harnesses/{name}", async () => {
    const harness = makeHarness();

    await api.updateHarness("space-1", "my-harness", harness);

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/spaces/space-1/harnesses/my-harness");
    expect(captured[0].method).toBe("PUT");
  });

  it("URL-encodes the name using encodeURIComponent", async () => {
    const harness = makeHarness({ name: "my harness" });

    await api.updateHarness("space-1", "my harness", harness);

    expect(captured[0].url).toBe("/api/spaces/space-1/harnesses/my%20harness");
  });

  it("sends the full harness body as JSON", async () => {
    const harness = makeHarness({ variables: { env: "prod" } });

    await api.updateHarness("space-1", "my-harness", harness);

    expect(captured[0].body).toEqual(harness);
  });

  it("sets Content-Type: application/json", async () => {
    await api.updateHarness("space-1", "my-harness", makeHarness());

    expect(captured[0].headers["Content-Type"]).toBe("application/json");
  });

  it("resolves with the updated Harness", async () => {
    const result = await api.updateHarness("space-1", "my-harness", makeHarness());

    expect(result.name).toBe("my-harness");
  });
});

// ---------------------------------------------------------------------------
// api.deleteHarness
// ---------------------------------------------------------------------------

describe("api.deleteHarness", () => {
  it("DELETEs /api/spaces/{spaceId}/harnesses/{name}", async () => {
    await api.deleteHarness("space-1", "my-harness");

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/spaces/space-1/harnesses/my-harness");
    expect(captured[0].method).toBe("DELETE");
  });

  it("URL-encodes the name using encodeURIComponent", async () => {
    await api.deleteHarness("space-1", "my harness");

    expect(captured[0].url).toBe("/api/spaces/space-1/harnesses/my%20harness");
  });

  it("resolves to undefined on successful delete (204)", async () => {
    const result = await api.deleteHarness("space-1", "my-harness");

    expect(result).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// URL-encoding: name with spaces → my%20harness
// ---------------------------------------------------------------------------

describe("URL-encoding: name with spaces", () => {
  it('encodes "my harness" as "my%20harness" in getHarness', async () => {
    await api.getHarness("space-1", "my harness");

    expect(captured[0].url).toContain("my%20harness");
  });

  it('encodes "my harness" as "my%20harness" in updateHarness', async () => {
    await api.updateHarness("space-1", "my harness", makeHarness({ name: "my harness" }));

    expect(captured[0].url).toContain("my%20harness");
  });

  it('encodes "my harness" as "my%20harness" in deleteHarness', async () => {
    await api.deleteHarness("space-1", "my harness");

    expect(captured[0].url).toContain("my%20harness");
  });
});
