import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RunHistory } from "../RunHistory";
import type { RunSummary } from "../../../hooks/useHarnessRuns";

// Mock the useHarnessRuns hook
const mockUseHarnessRuns = vi.fn();
vi.mock("../../../hooks/useHarnessRuns", () => ({
  useHarnessRuns: (...args: unknown[]) => mockUseHarnessRuns(...args),
}));

function makeRun(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-1",
    harness_id: "harness-1",
    status: "done",
    triggered_at: "2024-01-01T12:00:00Z",
    finished_at: "2024-01-01T12:05:00Z",
    ...overrides,
  };
}

const defaultProps = {
  spaceId: "space-1",
  name: "my-harness",
  onSelectRun: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RunHistory", () => {
  it('renders "No runs yet." when the run list is empty (R5)', () => {
    mockUseHarnessRuns.mockReturnValue({ data: [], isLoading: false, isError: false });
    render(<RunHistory {...defaultProps} />);
    expect(screen.getByTestId("run-history-empty")).toBeTruthy();
    expect(screen.getByText("No runs yet.")).toBeTruthy();
  });

  it('renders "No runs yet." when data is undefined', () => {
    mockUseHarnessRuns.mockReturnValue({ data: undefined, isLoading: false, isError: false });
    render(<RunHistory {...defaultProps} />);
    expect(screen.getByText("No runs yet.")).toBeTruthy();
  });

  it("renders loading state", () => {
    mockUseHarnessRuns.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    render(<RunHistory {...defaultProps} />);
    expect(screen.getByTestId("run-history-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    mockUseHarnessRuns.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    render(<RunHistory {...defaultProps} />);
    expect(screen.getByTestId("run-history-error")).toBeTruthy();
  });

  it("renders run list with status pills and timestamps", () => {
    const runs = [
      makeRun({ run_id: "run-a", status: "done", triggered_at: "2024-01-01T10:00:00Z" }),
      makeRun({ run_id: "run-b", status: "failed", triggered_at: "2024-01-01T11:00:00Z" }),
    ];
    mockUseHarnessRuns.mockReturnValue({ data: runs, isLoading: false, isError: false });
    render(<RunHistory {...defaultProps} />);
    expect(screen.getByTestId("run-history-list")).toBeTruthy();
    expect(screen.getByTestId("run-item-run-a")).toBeTruthy();
    expect(screen.getByTestId("run-item-run-b")).toBeTruthy();
    expect(screen.getByTestId("run-status-pill-run-a")).toBeTruthy();
    expect(screen.getByTestId("run-status-pill-run-b")).toBeTruthy();
  });

  it("renders runs newest-first", () => {
    const runs = [
      makeRun({ run_id: "run-old", status: "done", triggered_at: "2024-01-01T08:00:00Z" }),
      makeRun({ run_id: "run-new", status: "done", triggered_at: "2024-01-01T10:00:00Z" }),
      makeRun({ run_id: "run-mid", status: "done", triggered_at: "2024-01-01T09:00:00Z" }),
    ];
    mockUseHarnessRuns.mockReturnValue({ data: runs, isLoading: false, isError: false });
    render(<RunHistory {...defaultProps} />);

    const list = screen.getByTestId("run-history-list");
    const items = list.querySelectorAll("[data-testid^='run-item-']");
    const ids = Array.from(items).map((el) => el.getAttribute("data-testid"));
    expect(ids).toEqual(["run-item-run-new", "run-item-run-mid", "run-item-run-old"]);
  });

  it('calls onSelectRun with mode "replay" for a finished run', () => {
    const onSelectRun = vi.fn();
    mockUseHarnessRuns.mockReturnValue({
      data: [makeRun({ run_id: "run-done", status: "done" })],
      isLoading: false,
      isError: false,
    });
    render(<RunHistory {...defaultProps} onSelectRun={onSelectRun} />);
    fireEvent.click(screen.getByTestId("run-item-run-done"));
    expect(onSelectRun).toHaveBeenCalledWith("run-done", "replay");
  });

  it('calls onSelectRun with mode "live" for a running run', () => {
    const onSelectRun = vi.fn();
    mockUseHarnessRuns.mockReturnValue({
      data: [makeRun({ run_id: "run-live", status: "running" })],
      isLoading: false,
      isError: false,
    });
    render(<RunHistory {...defaultProps} onSelectRun={onSelectRun} />);
    fireEvent.click(screen.getByTestId("run-item-run-live"));
    expect(onSelectRun).toHaveBeenCalledWith("run-live", "live");
  });

  it("calls onSelectRun with correct args for cancelled run (replay)", () => {
    const onSelectRun = vi.fn();
    mockUseHarnessRuns.mockReturnValue({
      data: [makeRun({ run_id: "run-cancelled", status: "cancelled" })],
      isLoading: false,
      isError: false,
    });
    render(<RunHistory {...defaultProps} onSelectRun={onSelectRun} />);
    fireEvent.click(screen.getByTestId("run-item-run-cancelled"));
    expect(onSelectRun).toHaveBeenCalledWith("run-cancelled", "replay");
  });

  it("calls onSelectRun with correct args for failed run (replay)", () => {
    const onSelectRun = vi.fn();
    mockUseHarnessRuns.mockReturnValue({
      data: [makeRun({ run_id: "run-failed", status: "failed" })],
      isLoading: false,
      isError: false,
    });
    render(<RunHistory {...defaultProps} onSelectRun={onSelectRun} />);
    fireEvent.click(screen.getByTestId("run-item-run-failed"));
    expect(onSelectRun).toHaveBeenCalledWith("run-failed", "replay");
  });

  it("passes spaceId and name to useHarnessRuns", () => {
    mockUseHarnessRuns.mockReturnValue({ data: [], isLoading: false, isError: false });
    render(<RunHistory spaceId="my-space" name="my-harness" onSelectRun={vi.fn()} />);
    expect(mockUseHarnessRuns).toHaveBeenCalledWith("my-space", "my-harness");
  });

  it("renders status pill text for each run status", () => {
    const runs = [
      makeRun({ run_id: "r1", status: "running" }),
      makeRun({ run_id: "r2", status: "done" }),
      makeRun({ run_id: "r3", status: "failed" }),
      makeRun({ run_id: "r4", status: "cancelled" }),
    ];
    mockUseHarnessRuns.mockReturnValue({ data: runs, isLoading: false, isError: false });
    render(<RunHistory {...defaultProps} />);

    expect(screen.getByTestId("run-status-pill-r1").textContent).toBe("running");
    expect(screen.getByTestId("run-status-pill-r2").textContent).toBe("done");
    expect(screen.getByTestId("run-status-pill-r3").textContent).toBe("failed");
    expect(screen.getByTestId("run-status-pill-r4").textContent).toBe("cancelled");
  });
});
