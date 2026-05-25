import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { Space, SpacesResponse } from "../../types";
import {
  useSpaces,
  useSpace,
  useCreateSpace,
  useUpdateSpace,
  useDeleteSpace,
  useActivity,
} from "../useSpaces";

vi.mock("../../api", () => ({
  api: {
    spaces: vi.fn(),
    space: vi.fn(),
    createSpace: vi.fn(),
    updateSpace: vi.fn(),
    linkSpaceRepo: vi.fn(),
    unlinkSpaceRepo: vi.fn(),
    deleteSpace: vi.fn(),
    spaceTools: vi.fn(),
    importSpace: vi.fn(),
    activity: vi.fn(),
  },
}));

const mockSpace: Space = {
  id: "space-1",
  name: "Test Space",
  color: "#15803D",
  icon: null,
  description: "A test space",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  git_repo_url: null,
  git_branch: null,
  git_share_cronos: false,
  agent_defaults: {},
};

const mockSpacesResponse: SpacesResponse = {
  spaces: [
    {
      id: "space-1",
      name: "Test Space",
      color: "#15803D",
      icon: null,
      task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
      last_activity_at: null,
    },
  ],
  totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
};

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

describe("useSpaces", () => {
  beforeEach(() => vi.clearAllMocks());

  it('caches data under the ["spaces"] key', async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.spaces).mockResolvedValue(mockSpacesResponse);

    const { result } = renderHook(() => useSpaces(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.getQueryData(["spaces"])).toEqual(mockSpacesResponse);
    expect(result.current.data).toEqual(mockSpacesResponse);
  });
});

describe("useSpace", () => {
  it("is disabled when id is null", () => {
    const client = makeClient();
    const { result } = renderHook(() => useSpace(null), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches when id is provided", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.space).mockResolvedValue(mockSpace);

    const { result } = renderHook(() => useSpace("space-1"), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.space).toHaveBeenCalledWith("space-1");
    expect(result.current.data).toEqual(mockSpace);
  });
});

describe("useActivity", () => {
  it('uses ["activity", "all", 50] key by default', async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.activity).mockResolvedValue([]);

    const { result } = renderHook(() => useActivity(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.getQueryData(["activity", "all", 50])).toEqual([]);
  });

  it('uses space-specific key when spaceId is provided', async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.activity).mockResolvedValue([]);

    const { result } = renderHook(() => useActivity(25, "space-1"), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.getQueryData(["activity", "space-1", 25])).toEqual([]);
  });
});

describe("useCreateSpace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.createSpace with the provided body", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.createSpace).mockResolvedValue(mockSpace);

    const { result } = renderHook(() => useCreateSpace(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        name: "New Space",
        color: "#15803D",
      });
    });

    // React Query v5 may pass a context object as second arg; check only the first
    expect(vi.mocked(api.createSpace).mock.calls[0][0]).toEqual({
      name: "New Space",
      color: "#15803D",
    });
  });

  it("invalidates spaces and activity after creation", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.createSpace).mockResolvedValue(mockSpace);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateSpace(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ name: "New", color: "#15803D" });
    });

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(exactKeys).toContainEqual(["spaces"]);
    expect(exactKeys).toContainEqual(["activity"]);
  });
});

describe("useUpdateSpace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invalidates global spaces list and the specific space", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.updateSpace).mockResolvedValue({
      ...mockSpace,
      name: "Renamed",
    });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateSpace("space-1"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ name: "Renamed" });
    });

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(exactKeys).toContainEqual(["spaces"]);
    expect(exactKeys).toContainEqual(["space", "space-1"]);
  });

  it("also invalidates boards after space update", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.updateSpace).mockResolvedValue(mockSpace);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateSpace("space-1"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ name: "x" });
    });

    type FilterArg = { predicate?: (q: { queryKey: unknown[] }) => boolean };
    const boardPredicateCall = spy.mock.calls.find(([opts]) => {
      const filter = opts as FilterArg;
      return typeof filter?.predicate === "function";
    });
    expect(boardPredicateCall).toBeDefined();
  });
});

describe("useDeleteSpace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.deleteSpace and invalidates spaces and activity", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.deleteSpace).mockResolvedValue(undefined);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeleteSpace(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ id: "space-1" });
    });

    expect(api.deleteSpace).toHaveBeenCalledWith("space-1", false);

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(exactKeys).toContainEqual(["spaces"]);
    expect(exactKeys).toContainEqual(["activity"]);
  });

  it("passes cascade=true when requested", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.deleteSpace).mockResolvedValue(undefined);

    const { result } = renderHook(() => useDeleteSpace(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ id: "space-1", cascade: true });
    });

    expect(api.deleteSpace).toHaveBeenCalledWith("space-1", true);
  });
});
