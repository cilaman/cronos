import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { PluginsResponse } from "../../types";
import {
  usePlugins,
  useInstallPlugin,
  useUninstallPlugin,
  useEnablePlugin,
  useDisablePlugin,
  useAddMarketplace,
  useRemoveMarketplace,
} from "../usePlugins";

// ---------------------------------------------------------------------------
// API mock
// ---------------------------------------------------------------------------

vi.mock("../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api")>();
  return {
    ...actual,
    api: {
      plugins: vi.fn(),
      installPlugin: vi.fn(),
      uninstallPlugin: vi.fn(),
      enablePlugin: vi.fn(),
      disablePlugin: vi.fn(),
      addMarketplace: vi.fn(),
      removeMarketplace: vi.fn(),
    },
  };
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockPluginsResponse: PluginsResponse = {
  installed: [],
  available: [],
  marketplaces: [],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

/** Returns the query keys passed to all invalidateQueries calls on the client. */
function spyKeys(spy: {
  mock: { calls: unknown[][] };
}): (unknown[] | undefined)[] {
  return spy.mock.calls.map(
    (call) => (call[0] as { queryKey?: unknown[] } | undefined)?.queryKey,
  );
}

// ---------------------------------------------------------------------------
// Tests: usePlugins
// ---------------------------------------------------------------------------

describe("usePlugins", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.plugins and caches data under ['plugins'] key", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.plugins).mockResolvedValue(mockPluginsResponse);

    const { result } = renderHook(() => usePlugins(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.plugins).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual(mockPluginsResponse);
    expect(client.getQueryData(["plugins"])).toEqual(mockPluginsResponse);
  });
});

// ---------------------------------------------------------------------------
// Tests: mutation hooks — each must call the api fn AND invalidate ['plugins']
// ---------------------------------------------------------------------------

describe("useInstallPlugin", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.installPlugin and invalidates ['plugins'] on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.installPlugin).mockResolvedValue(mockPluginsResponse);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useInstallPlugin(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ pluginId: "my-plugin", scope: "user" });
    });

    expect(api.installPlugin).toHaveBeenCalledWith("my-plugin", "user");
    expect(spyKeys(spy)).toContainEqual(["plugins"]);
  });
});

describe("useUninstallPlugin", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.uninstallPlugin and invalidates ['plugins'] on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.uninstallPlugin).mockResolvedValue(mockPluginsResponse);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUninstallPlugin(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("my-plugin");
    });

    expect(api.uninstallPlugin).toHaveBeenCalledWith("my-plugin");
    expect(spyKeys(spy)).toContainEqual(["plugins"]);
  });
});

describe("useEnablePlugin", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.enablePlugin and invalidates ['plugins'] on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.enablePlugin).mockResolvedValue(mockPluginsResponse);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useEnablePlugin(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("my-plugin");
    });

    expect(api.enablePlugin).toHaveBeenCalledWith("my-plugin");
    expect(spyKeys(spy)).toContainEqual(["plugins"]);
  });
});

describe("useDisablePlugin", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.disablePlugin and invalidates ['plugins'] on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.disablePlugin).mockResolvedValue(mockPluginsResponse);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDisablePlugin(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("my-plugin");
    });

    expect(api.disablePlugin).toHaveBeenCalledWith("my-plugin");
    expect(spyKeys(spy)).toContainEqual(["plugins"]);
  });
});

describe("useAddMarketplace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.addMarketplace and invalidates ['plugins'] on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.addMarketplace).mockResolvedValue(mockPluginsResponse);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useAddMarketplace(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("https://example.com/marketplace");
    });

    expect(api.addMarketplace).toHaveBeenCalledWith("https://example.com/marketplace");
    expect(spyKeys(spy)).toContainEqual(["plugins"]);
  });
});

describe("useRemoveMarketplace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.removeMarketplace and invalidates ['plugins'] on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.removeMarketplace).mockResolvedValue(mockPluginsResponse);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useRemoveMarketplace(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("my-marketplace");
    });

    expect(api.removeMarketplace).toHaveBeenCalledWith("my-marketplace");
    expect(spyKeys(spy)).toContainEqual(["plugins"]);
  });
});
