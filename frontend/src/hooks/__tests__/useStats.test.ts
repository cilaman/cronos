import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useTaskStats, useSpaceStats, useGlobalStats } from "../useStats";

vi.mock("../../api", () => ({
  api: {
    taskStats: vi.fn().mockResolvedValue({ task_id: "t1", runs: [] }),
    spaceStats: vi.fn().mockResolvedValue([]),
    globalStats: vi.fn().mockResolvedValue({ total_tasks_with_stats: 0 }),
  },
}));

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

describe("useTaskStats", () => {
  it("is disabled when taskId is undefined", () => {
    const { result } = renderHook(() => useTaskStats(undefined), {
      wrapper: makeWrapper(),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("uses the correct query key when taskId is provided", async () => {
    const { result } = renderHook(() => useTaskStats("task-1"), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const { api } = await import("../../api");
    expect(api.taskStats).toHaveBeenCalledWith("task-1");
  });
});

describe("useSpaceStats", () => {
  it("is disabled when spaceId is undefined", () => {
    const { result } = renderHook(() => useSpaceStats(undefined), {
      wrapper: makeWrapper(),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches when spaceId is provided", async () => {
    const { result } = renderHook(() => useSpaceStats("space-1"), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const { api } = await import("../../api");
    expect(api.spaceStats).toHaveBeenCalledWith("space-1", undefined, undefined);
  });
});

describe("useGlobalStats", () => {
  it("fetches global stats unconditionally", async () => {
    const { result } = renderHook(() => useGlobalStats(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const { api } = await import("../../api");
    expect(api.globalStats).toHaveBeenCalled();
  });
});
