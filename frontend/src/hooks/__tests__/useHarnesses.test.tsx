import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { Harness } from "../../types";
import { useHarnesses, useHarness, useSaveHarness } from "../useHarnesses";

// ---------------------------------------------------------------------------
// API mock
// ---------------------------------------------------------------------------

vi.mock("../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api")>();
  return {
    ...actual,
    api: {
      listHarnesses: vi.fn(),
      getHarness: vi.fn(),
      createHarness: vi.fn(),
      updateHarness: vi.fn(),
      deleteHarness: vi.fn(),
    },
  };
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockHarness: Harness = {
  name: "my-harness",
  description: "A test harness",
  nodes: [],
  edges: [],
  variables: {},
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  version: 1,
};

const mockHarnessList: Harness[] = [mockHarness];

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

// ---------------------------------------------------------------------------
// Tests: useHarnesses
// ---------------------------------------------------------------------------

describe("useHarnesses", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.listHarnesses with the correct spaceId", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.listHarnesses).mockResolvedValue(mockHarnessList);

    const { result } = renderHook(() => useHarnesses("space-1"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.listHarnesses).toHaveBeenCalledWith("space-1");
    expect(result.current.data).toEqual(mockHarnessList);
  });

  it('caches data under ["harnesses", spaceId] key', async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.listHarnesses).mockResolvedValue(mockHarnessList);

    const { result } = renderHook(() => useHarnesses("space-1"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.getQueryData(["harnesses", "space-1"])).toEqual(mockHarnessList);
  });
});

// ---------------------------------------------------------------------------
// Tests: useHarness
// ---------------------------------------------------------------------------

describe("useHarness", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.getHarness with the correct spaceId and name", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.getHarness).mockResolvedValue(mockHarness);

    const { result } = renderHook(() => useHarness("space-1", "my-harness"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.getHarness).toHaveBeenCalledWith("space-1", "my-harness");
    expect(result.current.data).toEqual(mockHarness);
  });

  it("is disabled when spaceId is empty", () => {
    const client = makeClient();

    const { result } = renderHook(() => useHarness("", "my-harness"), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
  });

  it("is disabled when name is empty", () => {
    const client = makeClient();

    const { result } = renderHook(() => useHarness("space-1", ""), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
  });
});

// ---------------------------------------------------------------------------
// Tests: useSaveHarness
// ---------------------------------------------------------------------------

describe("useSaveHarness", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.getHarness BEFORE api.updateHarness (call order matters)", async () => {
    const client = makeClient();
    const { api } = await import("../../api");

    const callOrder: string[] = [];
    vi.mocked(api.getHarness).mockImplementation(async () => {
      callOrder.push("getHarness");
      return mockHarness;
    });
    vi.mocked(api.updateHarness).mockImplementation(async () => {
      callOrder.push("updateHarness");
      return mockHarness;
    });

    const { result } = renderHook(() => useSaveHarness("space-1", "my-harness"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ nodes: [], edges: [] });
    });

    expect(callOrder[0]).toBe("getHarness");
    expect(callOrder[1]).toBe("updateHarness");
    expect(callOrder).toHaveLength(2);
  });

  it("PUT payload includes created_at from the GET response verbatim", async () => {
    const client = makeClient();
    const { api } = await import("../../api");

    const serverHarness: Harness = {
      ...mockHarness,
      created_at: "2024-01-01T12:34:56Z",
    };

    vi.mocked(api.getHarness).mockResolvedValue(serverHarness);
    vi.mocked(api.updateHarness).mockResolvedValue(serverHarness);

    const { result } = renderHook(() => useSaveHarness("space-1", "my-harness"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ description: "updated" });
    });

    const updateCall = vi.mocked(api.updateHarness).mock.calls[0];
    const putPayload = updateCall[2] as Harness;

    expect(putPayload.created_at).toBe("2024-01-01T12:34:56Z");
  });

  it("onSuccess invalidates BOTH ['harnesses', spaceId] AND ['harness', spaceId, name]", async () => {
    const client = makeClient();
    const { api } = await import("../../api");

    vi.mocked(api.getHarness).mockResolvedValue(mockHarness);
    vi.mocked(api.updateHarness).mockResolvedValue(mockHarness);

    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => useSaveHarness("space-1", "my-harness"),
      { wrapper: makeWrapper(client) },
    );

    await act(async () => {
      await result.current.mutateAsync({ description: "updated" });
    });

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(exactKeys).toContainEqual(["harnesses", "space-1"]);
    expect(exactKeys).toContainEqual(["harness", "space-1", "my-harness"]);
  });

  it("merges canvas state into the GET response before calling updateHarness", async () => {
    const client = makeClient();
    const { api } = await import("../../api");

    const serverHarness: Harness = {
      ...mockHarness,
      description: "original description",
      variables: { key1: "val1" },
    };

    vi.mocked(api.getHarness).mockResolvedValue(serverHarness);
    vi.mocked(api.updateHarness).mockResolvedValue(serverHarness);

    const { result } = renderHook(() => useSaveHarness("space-1", "my-harness"), {
      wrapper: makeWrapper(client),
    });

    const canvasUpdate: Partial<Harness> = {
      description: "new description",
      nodes: [],
    };

    await act(async () => {
      await result.current.mutateAsync(canvasUpdate);
    });

    const putPayload = vi.mocked(api.updateHarness).mock.calls[0][2] as Harness;

    // canvas state merged in
    expect(putPayload.description).toBe("new description");
    expect(putPayload.nodes).toEqual([]);
    // server fields preserved
    expect(putPayload.variables).toEqual({ key1: "val1" });
    expect(putPayload.created_at).toBe(mockHarness.created_at);
  });
});
