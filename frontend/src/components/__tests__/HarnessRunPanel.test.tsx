import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { HarnessRunState } from "../../api";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

let mockRunData: HarnessRunState | undefined;
let mockRunIsLoading = false;
let mockRunIsError = false;
let mockStreamEvents: { type: string; [key: string]: unknown }[] = [];
let mockStreamStatus: "connecting" | "live" | "ended" | "error" = "ended";
const mockCancelMutate = vi.fn();
let mockCancelIsPending = false;

vi.mock("../../hooks/useHarnessRuns", () => ({
  useHarnessRun: () => ({
    data: mockRunData,
    isLoading: mockRunIsLoading,
    isError: mockRunIsError,
  }),
  useHarnessRunStream: () => ({
    events: mockStreamEvents,
    status: mockStreamStatus,
  }),
  useCancelHarnessRun: () => ({
    mutate: mockCancelMutate,
    isPending: mockCancelIsPending,
  }),
}));

// Import component AFTER mocks
import { HarnessRunPanel } from "../HarnessRunPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRunState(overrides: Partial<HarnessRunState> = {}): HarnessRunState {
  return {
    run_id: "run-1",
    harness_id: "harness-a",
    goal_task_id: "task-1",
    status: "running",
    nodes_executed: {},
    waiting_node_id: null,
    ...overrides,
  };
}

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderPanel(props: { runId?: string; spaceId?: string; harnessId?: string } = {}) {
  const client = makeClient();
  return render(
    <QueryClientProvider client={client}>
      <HarnessRunPanel
        runId={props.runId ?? "run-1"}
        spaceId={props.spaceId ?? "space-1"}
        harnessId={props.harnessId ?? "harness-a"}
      />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HarnessRunPanel", () => {
  beforeEach(() => {
    mockRunData = undefined;
    mockRunIsLoading = false;
    mockRunIsError = false;
    mockStreamEvents = [];
    mockStreamStatus = "ended";
    mockCancelMutate.mockReset();
    mockCancelIsPending = false;
  });

  it("test renders loading state when data not yet available", () => {
    mockRunIsLoading = true;
    mockRunData = undefined;
    renderPanel();
    expect(screen.getByTestId("run-panel-loading")).toBeInTheDocument();
    expect(screen.getByText(/Loading run/i)).toBeInTheDocument();
  });

  it("test renders node status badges for each node in run state", () => {
    mockRunData = makeRunState({
      nodes_executed: {
        node_a: {
          status: "done",
          child_task_id: null,
          output: "ok",
          reason: null,
          started_at: "2024-01-01T00:00:00Z",
          ended_at: "2024-01-01T00:00:30Z",
        },
        node_b: {
          status: "in_progress",
          child_task_id: null,
          output: null,
          reason: null,
          started_at: "2024-01-01T00:00:31Z",
          ended_at: null,
        },
        node_c: {
          status: "pending",
          child_task_id: null,
          output: null,
          reason: null,
          started_at: null,
          ended_at: null,
        },
      },
    });
    renderPanel();
    // Panel renders
    expect(screen.getByTestId("harness-run-panel")).toBeInTheDocument();
    // Node rows
    expect(screen.getByTestId("node-row-node_a")).toBeInTheDocument();
    expect(screen.getByTestId("node-row-node_b")).toBeInTheDocument();
    expect(screen.getByTestId("node-row-node_c")).toBeInTheDocument();
    // Status badges
    expect(screen.getByTestId("node-status-done")).toBeInTheDocument();
    expect(screen.getByTestId("node-status-in_progress")).toBeInTheDocument();
    expect(screen.getByTestId("node-status-pending")).toBeInTheDocument();
  });

  it("test shows cancel button when status is running", () => {
    mockRunData = makeRunState({ status: "running" });
    renderPanel();
    expect(screen.getByTestId("cancel-button")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel run/i })).toBeInTheDocument();
  });

  it("test does not show cancel button when status is done", () => {
    mockRunData = makeRunState({ status: "done" });
    renderPanel();
    expect(screen.queryByTestId("cancel-button")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel run/i })).not.toBeInTheDocument();
  });

  it("test calls cancel mutation on cancel button click", () => {
    mockRunData = makeRunState({ status: "running" });
    renderPanel({ runId: "run-1" });
    const btn = screen.getByTestId("cancel-button");
    fireEvent.click(btn);
    expect(mockCancelMutate).toHaveBeenCalledWith("run-1");
  });

  it("test shows history truncated badge after buffer_truncated event", () => {
    mockRunData = makeRunState({ status: "running" });
    mockStreamEvents = [{ type: "buffer_truncated" }];
    renderPanel();
    expect(screen.getByTestId("buffer-truncated-badge")).toBeInTheDocument();
    expect(screen.getByText(/history truncated/i)).toBeInTheDocument();
  });
});
