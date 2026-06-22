import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { RunSummary } from "../../api";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

let mockRuns: RunSummary[] = [];
let mockRunsLoading = false;
let mockRunsError = false;
const mockTriggerMutate = vi.fn();
let mockTriggerIsPending = false;
let mockTriggerIsError = false;

vi.mock("../../hooks/useHarnessRuns", () => ({
  useHarnessRuns: () => ({
    data: mockRuns,
    isLoading: mockRunsLoading,
    isError: mockRunsError,
  }),
  useTriggerHarnessRun: () => ({
    mutate: mockTriggerMutate,
    isPending: mockTriggerIsPending,
    isError: mockTriggerIsError,
  }),
}));

// Stub HarnessRunPanel to avoid deep hook dependencies in page tests
vi.mock("../../components/HarnessRunPanel", () => ({
  HarnessRunPanel: ({ runId }: { runId: string; spaceId: string; harnessId: string }) => (
    <div data-testid={`harness-run-panel-${runId}`}>HarnessRunPanel:{runId}</div>
  ),
}));

// Import component AFTER vi.mock
import { HarnessRunsPage } from "../HarnessRunsPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRunSummary(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-1",
    harness_id: "harness-a",
    status: "done",
    triggered_at: "2024-01-01T00:00:00Z",
    finished_at: "2024-01-01T00:01:00Z",
    ...overrides,
  };
}

function renderPage(
  spaceId = "space-1",
  name = "harness-a",
  initialSearch = "",
) {
  const path = `/spaces/${spaceId}/harnesses/${name}/runs${initialSearch}`;
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/spaces/:spaceId/harnesses/:name/runs"
          element={<HarnessRunsPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HarnessRunsPage", () => {
  beforeEach(() => {
    mockRuns = [];
    mockRunsLoading = false;
    mockRunsError = false;
    mockTriggerMutate.mockReset();
    mockTriggerIsPending = false;
    mockTriggerIsError = false;
  });

  it("renders the harness name in an h1 with text-title class", () => {
    renderPage("space-1", "my-harness");
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toBeInTheDocument();
    expect(h1.textContent).toBe("my-harness");
    expect(h1.className).toContain("text-title");
  });

  it("h1 does not carry ad-hoc size classes", () => {
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.className).not.toMatch(/text-\[22px\]/);
    expect(h1.className).not.toMatch(/uppercase/);
    expect(h1.className).not.toMatch(/tracking-\[/);
  });

  it("wraps content in a PageContainer (max-w-[1280px])", () => {
    const { container } = renderPage();
    const wrapper = container.querySelector(".max-w-\\[1280px\\]");
    expect(wrapper).not.toBeNull();
  });

  it("test renders empty state when no runs", () => {
    mockRuns = [];
    renderPage();
    expect(screen.getByTestId("runs-empty")).toBeInTheDocument();
    expect(screen.getByText(/no runs yet/i)).toBeInTheDocument();
  });

  it("test renders run list with status badges", () => {
    mockRuns = [
      makeRunSummary({ run_id: "run-1", status: "done" }),
      makeRunSummary({ run_id: "run-2", status: "running" }),
      makeRunSummary({ run_id: "run-3", status: "failed" }),
    ];
    renderPage();
    expect(screen.getByTestId("run-row-run-1")).toBeInTheDocument();
    expect(screen.getByTestId("run-row-run-2")).toBeInTheDocument();
    expect(screen.getByTestId("run-row-run-3")).toBeInTheDocument();
    // Status badges - use getAllByTestId since multiple badges may share same status name
    expect(screen.getByTestId("run-badge-done")).toBeInTheDocument();
    expect(screen.getByTestId("run-badge-running")).toBeInTheDocument();
    expect(screen.getByTestId("run-badge-failed")).toBeInTheDocument();
  });

  it("test shows HarnessRunPanel when a run is selected", () => {
    mockRuns = [makeRunSummary({ run_id: "run-1", status: "done" })];
    renderPage("space-1", "harness-a", "?run=run-1");
    expect(screen.getByTestId("harness-run-panel-run-1")).toBeInTheDocument();
  });

  it("shows no-run-selected placeholder when no run is focused", () => {
    mockRuns = [makeRunSummary({ run_id: "run-1" })];
    renderPage();
    expect(screen.getByTestId("no-run-selected")).toBeInTheDocument();
  });

  it("clicking a run row focuses that run in the panel", () => {
    mockRuns = [
      makeRunSummary({ run_id: "run-1", status: "done" }),
      makeRunSummary({ run_id: "run-2", status: "running" }),
    ];
    renderPage();
    // Initially no panel
    expect(screen.queryByTestId("harness-run-panel-run-1")).not.toBeInTheDocument();
    // Click run-1 row
    fireEvent.click(screen.getByTestId("run-row-run-1"));
    // Panel should now render
    expect(screen.getByTestId("harness-run-panel-run-1")).toBeInTheDocument();
  });

  it("test trigger run button calls trigger mutation", () => {
    renderPage();
    const btn = screen.getByTestId("run-now-button");
    fireEvent.click(btn);
    expect(mockTriggerMutate).toHaveBeenCalledWith(
      { spaceId: "space-1", name: "harness-a" },
      expect.any(Object),
    );
  });
});
