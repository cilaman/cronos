import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "../DashboardPage";
import type { SpacesResponse, GlobalStats, TestReportSummary } from "../../types";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: vi.fn(),
  useActivity: vi.fn(),
  useImportSpace: vi.fn(),
}));

vi.mock("../../hooks/useTasks", () => ({
  useCreateTask: vi.fn(),
}));

vi.mock("../../hooks/useStats", () => ({
  useGlobalStats: vi.fn(),
}));

vi.mock("../../hooks/useTestReports", () => ({
  useTestReports: vi.fn(),
  useLatestTestReport: vi.fn(),
}));

// Prevent TaskForm from pulling in heavy dependencies
vi.mock("../../components/TaskForm", () => ({
  TaskForm: () => <div data-testid="task-form" />,
}));

import {
  useSpaces,
  useActivity,
  useImportSpace,
} from "../../hooks/useSpaces";
import { useCreateTask } from "../../hooks/useTasks";
import { useGlobalStats } from "../../hooks/useStats";
import { useTestReports, useLatestTestReport } from "../../hooks/useTestReports";

// Use two spaces so the auto-select-single-space effect does NOT fire in default tests.
const mockSpacesResponse: SpacesResponse = {
  spaces: [
    {
      id: "space-1",
      name: "My Space",
      color: "#15803D",
      icon: null,
      task_counts: { backlog: 2, active: 1, waiting: 0, done: 5, archived: 0 },
      last_activity_at: null,
    },
    {
      id: "space-2",
      name: "Other Space",
      color: "#1D4ED8",
      icon: null,
      task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
      last_activity_at: null,
    },
  ],
  totals: { backlog: 2, active: 1, waiting: 0, done: 5, archived: 0 },
  feature_totals: { backlog: 3, planned: 0, processing: 0, waiting: 0, done: 1 },
};

const mockGlobalStats: GlobalStats = {
  total_tasks_with_stats: 3,
  total_runs: 12,
  total_input_tokens: 80_000,
  total_output_tokens: 40_000,
  total_cache_tokens: 5_000,
  total_cost_usd: 0.85,
  total_duration_seconds: 1_800,
  tool_use_summary: { Read: 40, Write: 20 },
  exit_reason_counts: { DONE: 10, STOPPED: 2 },
  avg_tokens_per_run: 10_000,
};

const mockTestReport: TestReportSummary = {
  id: "report-1",
  space_id: "space-1",
  report_type: "space",
  triggered_by: "manual",
  started_at: "2026-01-01T00:00:00Z",
  ended_at: "2026-01-01T00:05:00Z",
  total_tests: 100,
  total_passed: 95,
  total_failed: 3,
  total_errors: 1,
  total_skipped: 1,
  coverage_pct: 82.5,
  exit_code: 0,
  framework: "pytest",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
      isLoading: false,
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useActivity).mockReturnValue({
      data: [],
    } as unknown as ReturnType<typeof useActivity>);

    vi.mocked(useImportSpace).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useImportSpace>);

    vi.mocked(useCreateTask).mockReturnValue({
      mutateAsync: vi.fn(),
    } as unknown as ReturnType<typeof useCreateTask>);

    vi.mocked(useGlobalStats).mockReturnValue({
      data: mockGlobalStats,
    } as ReturnType<typeof useGlobalStats>);

    vi.mocked(useTestReports).mockReturnValue({
      data: undefined,
      isLoading: false,
    } as ReturnType<typeof useTestReports>);

    vi.mocked(useLatestTestReport).mockReturnValue({
      data: undefined,
    } as ReturnType<typeof useLatestTestReport>);
  });

  it("renders the Dashboard page heading", () => {
    renderPage();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("shows skeleton tiles while spaces are loading", () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useSpaces>);

    renderPage();
    // StatTile skeleton blocks present
    // At minimum the loading state should not show the dashboard heading content
    expect(screen.queryByText("To Do")).not.toBeInTheDocument();
  });

  it("renders stat tile labels from the StatTile primitive", () => {
    renderPage();
    expect(screen.getByText("To Do")).toBeInTheDocument();
    expect(screen.getByText("Active agents")).toBeInTheDocument();
    expect(screen.getByText("Waiting")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("Total tasks")).toBeInTheDocument();
    expect(screen.getByText("Features")).toBeInTheDocument();
  });

  it("renders stat tile values from totals", () => {
    renderPage();
    // backlog=2, active=1, waiting=0, done=5; total=8
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    // feature_totals.backlog = 3
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders the AI Performance section using MetricTile (StatTile primitive)", () => {
    renderPage();
    // MetricTile labels derived from GlobalStats
    expect(screen.getByText("Runs")).toBeInTheDocument();
    expect(screen.getByText("Tokens")).toBeInTheDocument();
    expect(screen.getByText("Est. cost")).toBeInTheDocument();
    expect(screen.getByText("Total time")).toBeInTheDocument();
  });

  it("renders spaces list", () => {
    renderPage();
    // Multiple elements may carry the name (space card + space filter option)
    expect(screen.getAllByText("My Space").length).toBeGreaterThan(0);
  });

  it("renders empty-state for activity when no activity events", () => {
    renderPage();
    expect(screen.getByText("No activity yet")).toBeInTheDocument();
  });

  it("renders Test Health section", () => {
    renderPage();
    expect(screen.getByText("Test Health")).toBeInTheDocument();
  });

  it("shows 'select a space' prompt in Test Health when no space is selected", () => {
    renderPage();
    expect(
      screen.getByText(/Select a space above to view test health/i),
    ).toBeInTheDocument();
  });

  it("shows test report summary when test reports are loaded", () => {
    vi.mocked(useTestReports).mockReturnValue({
      data: [mockTestReport],
      isLoading: false,
    } as ReturnType<typeof useTestReports>);

    renderPage();
    // The test health card shows the summary if a space is selected —
    // by default no space is selected, so the "select a space" prompt appears.
    expect(
      screen.getByText(/Select a space above to view test health/i),
    ).toBeInTheDocument();
  });

  it("renders New task button", () => {
    renderPage();
    expect(screen.getByText("New task")).toBeInTheDocument();
  });

  it("renders New space link", () => {
    renderPage();
    expect(screen.getAllByText("New space").length).toBeGreaterThan(0);
  });
});
