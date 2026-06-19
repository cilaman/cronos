import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "../api";
import type { PluginsResponse } from "../types";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function makePluginsResponse(overrides: Partial<PluginsResponse> = {}): PluginsResponse {
  return {
    installed: [],
    available: [],
    marketplaces: [],
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
  body: string | null;
}

let captured: CapturedRequest[];

beforeEach(() => {
  captured = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      const body = typeof init?.body === "string" ? init.body : null;
      captured.push({ url, method, body });
      return jsonResponse(makePluginsResponse());
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// api.plugins
// ---------------------------------------------------------------------------

describe("api.plugins", () => {
  it("GETs /api/plugins", async () => {
    await api.plugins();

    expect(captured).toHaveLength(1);
    expect(captured[0].url).toBe("/api/plugins");
    expect(captured[0].method).toBe("GET");
  });

  it("returns a PluginsResponse", async () => {
    const result = await api.plugins();

    expect(Array.isArray(result.installed)).toBe(true);
    expect(Array.isArray(result.available)).toBe(true);
    expect(Array.isArray(result.marketplaces)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// api.installPlugin
// ---------------------------------------------------------------------------

describe("api.installPlugin", () => {
  it("POSTs /api/plugins/install with plugin_id and scope", async () => {
    await api.installPlugin("my-plugin", "user");

    expect(captured[0].url).toBe("/api/plugins/install");
    expect(captured[0].method).toBe("POST");
    expect(JSON.parse(captured[0].body!)).toEqual({ plugin_id: "my-plugin", scope: "user" });
  });

  it("defaults scope to 'user' when not provided", async () => {
    await api.installPlugin("another-plugin");

    expect(JSON.parse(captured[0].body!)).toEqual({ plugin_id: "another-plugin", scope: "user" });
  });

  it("returns PluginsResponse", async () => {
    const result = await api.installPlugin("p");
    expect(Array.isArray(result.installed)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// api.uninstallPlugin
// ---------------------------------------------------------------------------

describe("api.uninstallPlugin", () => {
  it("POSTs /api/plugins/uninstall with plugin_id", async () => {
    await api.uninstallPlugin("my-plugin");

    expect(captured[0].url).toBe("/api/plugins/uninstall");
    expect(captured[0].method).toBe("POST");
    expect(JSON.parse(captured[0].body!)).toEqual({ plugin_id: "my-plugin" });
  });

  it("returns PluginsResponse", async () => {
    const result = await api.uninstallPlugin("p");
    expect(Array.isArray(result.installed)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// api.enablePlugin
// ---------------------------------------------------------------------------

describe("api.enablePlugin", () => {
  it("POSTs /api/plugins/enable with plugin_id", async () => {
    await api.enablePlugin("my-plugin");

    expect(captured[0].url).toBe("/api/plugins/enable");
    expect(captured[0].method).toBe("POST");
    expect(JSON.parse(captured[0].body!)).toEqual({ plugin_id: "my-plugin" });
  });

  it("returns PluginsResponse", async () => {
    const result = await api.enablePlugin("p");
    expect(Array.isArray(result.installed)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// api.disablePlugin
// ---------------------------------------------------------------------------

describe("api.disablePlugin", () => {
  it("POSTs /api/plugins/disable with plugin_id", async () => {
    await api.disablePlugin("my-plugin");

    expect(captured[0].url).toBe("/api/plugins/disable");
    expect(captured[0].method).toBe("POST");
    expect(JSON.parse(captured[0].body!)).toEqual({ plugin_id: "my-plugin" });
  });

  it("returns PluginsResponse", async () => {
    const result = await api.disablePlugin("p");
    expect(Array.isArray(result.installed)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// api.addMarketplace
// ---------------------------------------------------------------------------

describe("api.addMarketplace", () => {
  it("POSTs /api/plugins/marketplaces with source", async () => {
    await api.addMarketplace("https://example.com/plugins");

    expect(captured[0].url).toBe("/api/plugins/marketplaces");
    expect(captured[0].method).toBe("POST");
    expect(JSON.parse(captured[0].body!)).toEqual({ source: "https://example.com/plugins" });
  });

  it("returns PluginsResponse", async () => {
    const result = await api.addMarketplace("https://example.com");
    expect(Array.isArray(result.marketplaces)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// api.removeMarketplace
// ---------------------------------------------------------------------------

describe("api.removeMarketplace", () => {
  it("DELETEs /api/plugins/marketplaces/{name}", async () => {
    await api.removeMarketplace("official");

    expect(captured[0].url).toBe("/api/plugins/marketplaces/official");
    expect(captured[0].method).toBe("DELETE");
  });

  it("URL-encodes the marketplace name", async () => {
    await api.removeMarketplace("my market");

    expect(captured[0].url).toBe("/api/plugins/marketplaces/my%20market");
  });

  it("returns PluginsResponse", async () => {
    const result = await api.removeMarketplace("official");
    expect(Array.isArray(result.marketplaces)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Return types — all mutation functions return Promise<PluginsResponse>
// ---------------------------------------------------------------------------

describe("all mutation functions return PluginsResponse shape", () => {
  it("installPlugin, uninstallPlugin, enablePlugin, disablePlugin all return PluginsResponse", async () => {
    const responses = await Promise.all([
      api.installPlugin("p"),
      api.uninstallPlugin("p"),
      api.enablePlugin("p"),
      api.disablePlugin("p"),
    ]);

    for (const r of responses) {
      expect(r).toHaveProperty("installed");
      expect(r).toHaveProperty("available");
      expect(r).toHaveProperty("marketplaces");
    }
  });

  it("addMarketplace and removeMarketplace return PluginsResponse", async () => {
    const r1 = await api.addMarketplace("https://x.com");
    const r2 = await api.removeMarketplace("x");

    expect(r1).toHaveProperty("marketplaces");
    expect(r2).toHaveProperty("marketplaces");
  });
});
