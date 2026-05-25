import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { StatsPage } from "../StatsPage";
import type { GlobalStats, SpacesResponse, TaskStats } from "../../types";

vi.mock("../../hooks/useStats", () => ({
  useGlobalStats: vi.fn(),
  useSpaceStats: vi.fn(),
}));

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: vi.fn(),
}));

import { useGlobalStats, useSpaceStats } from "../../hooks/useStats";
import { useSpaces } from "../../hooks/useSpaces";

const mockGlobalStats: GlobalStats = {
  total_tasks_with_stats: 5,
  total_runs: 20,
  total_input_tokens: 100_000,
  total_output_tokens: 50_000,
  total_cache_tokens: 10_000,
  total_cost_usd: 1.25,
  total_duration_seconds: 3_600,
  tool_use_summary: { Read: 50, Write: 30, Bash: 20 },
  exit_reason_counts: { DONE: 15, STOPPED: 5 },
  avg_tokens_per_run: 7_500,
};

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
  ],
  totals: { backlog: 2, active: 1, waiting: 0, done: 5, archived: 0 },
};

const mockSpaceStats: TaskStats[] = [
  {
    task_id: "task-1",
    space_id: "space-1",
    title: "My Task",
    runs: [],
    total_runs: 3,
    total_input_tokens: 10_000,
    total_output_tokens: 5_000,
    total_cache_tokens: 500,
    total_cost_usd: 0.15,
    total_duration_seconds: 600,
    tool_use_summary: { Read: 10 },
    exit_reason_counts: { DONE: 3 },
    avg_tokens_per_run: 5_000,
    crash_rate: 0,
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <StatsPage />
    </MemoryRouter>,
  );
}

describe("StatsPage", () => {
  beforeEach(() => {
    vi.mocked(useGlobalStats).mockReturnValue({
      data: mockGlobalStats,
      isLoading: false,
    } as ReturnType<typeof useGlobalStats>);

    vi.mocked(useSpaceStats).mockReturnValue({
      data: undefined,
    } as ReturnType<typeof useSpaceStats>);

    vi.mocked(useSpaces).mockReturnValue({
      data: { spaces: [], totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 } },
    } as ReturnType<typeof useSpaces>);
  });

  it("renders the Stats page header", () => {
    renderPage();
    expect(screen.getByText("Stats")).toBeInTheDocument();
  });

  it("shows a loading indicator while global stats are fetching", () => {
    vi.mocked(useGlobalStats).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useGlobalStats>);

    renderPage();
    expect(screen.getByText(/Loading statistics/i)).toBeInTheDocument();
  });

  it("renders overview tiles when global stats are loaded", () => {
    renderPage();
    // All six stat tile labels should be present
    expect(screen.getByText("Total runs")).toBeInTheDocument();
    expect(screen.getByText("Total tokens")).toBeInTheDocument();
    expect(screen.getByText("Est. cost")).toBeInTheDocument();
    expect(screen.getByText("Total time")).toBeInTheDocument();
    expect(screen.getByText("Tasks tracked")).toBeInTheDocument();
    // "20" appears both in the Total runs tile and the Bash tool count —
    // verify at least two elements carry that value
    expect(screen.getAllByText("20")).toHaveLength(2);
  });

  it("renders exit reason badges", () => {
    renderPage();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("Stopped")).toBeInTheDocument();
    expect(screen.getByText("Blocked")).toBeInTheDocument();
  });

  it("renders top tool usage bars", () => {
    renderPage();
    expect(screen.getByText("Read")).toBeInTheDocument();
    expect(screen.getByText("Write")).toBeInTheDocument();
    expect(screen.getByText("Bash")).toBeInTheDocument();
  });

  it("shows space filter when spaces exist", () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    renderPage();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText("My Space")).toBeInTheDocument();
  });

  it("shows 'select a space' prompt when no space is selected", () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    renderPage();
    expect(
      screen.getByText(/Select a space above to view per-task statistics/i),
    ).toBeInTheDocument();
  });

  it("renders per-space task table when a space is selected and stats are available", async () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useSpaceStats).mockReturnValue({
      data: mockSpaceStats,
    } as ReturnType<typeof useSpaceStats>);

    renderPage();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "space-1");

    // After selecting a space, table headers should appear
    expect(screen.getByText("Task")).toBeInTheDocument();
    expect(screen.getByText("Runs")).toBeInTheDocument();
  });

  it("shows empty-state message when space has no task stats", async () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useSpaceStats).mockReturnValue({
      data: [],
    } as ReturnType<typeof useSpaceStats>);

    renderPage();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "space-1");

    expect(
      screen.getByText(/No task statistics in this space yet/i),
    ).toBeInTheDocument();
  });
});
