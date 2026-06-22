import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mock all hooks used by DashboardPage
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

vi.mock("../../components/TaskForm", () => ({
  TaskForm: () => <div data-testid="task-form">TaskForm</div>,
}));

vi.mock("../../api", () => ({
  api: {
    uploadTaskFile: vi.fn(),
    start: vi.fn(),
  },
}));

import { DashboardPage } from "../DashboardPage";
import { useSpaces, useActivity, useImportSpace } from "../../hooks/useSpaces";
import { useCreateTask } from "../../hooks/useTasks";
import { useGlobalStats } from "../../hooks/useStats";
import { useTestReports, useLatestTestReport } from "../../hooks/useTestReports";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const emptySpacesData = {
  spaces: [],
  totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
};

function setupDefaults() {
  vi.mocked(useSpaces).mockReturnValue({
    data: emptySpacesData,
    isLoading: false,
  } as unknown as ReturnType<typeof useSpaces>);

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
    data: undefined,
  } as unknown as ReturnType<typeof useGlobalStats>);

  vi.mocked(useTestReports).mockReturnValue({
    data: undefined,
    isLoading: false,
  } as ReturnType<typeof useTestReports>);

  vi.mocked(useLatestTestReport).mockReturnValue({
    data: undefined,
  } as unknown as ReturnType<typeof useLatestTestReport>);
}

function renderPage() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DashboardPage", () => {
  beforeEach(() => {
    setupDefaults();
  });

  it("renders the page title in an h1 with text-title class", () => {
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toBeInTheDocument();
    expect(h1.textContent).toBe("Dashboard");
    expect(h1.className).toContain("text-title");
  });

  it("h1 does not carry ad-hoc size classes", () => {
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.className).not.toMatch(/text-\[22px\]/);
    expect(h1.className).not.toMatch(/text-lg/);
    expect(h1.className).not.toMatch(/uppercase/);
    expect(h1.className).not.toMatch(/tracking-\[/);
  });

  it("wraps content in a PageContainer (max-w-[1280px])", () => {
    const { container } = renderPage();
    const wrapper = container.querySelector(".max-w-\\[1280px\\]");
    expect(wrapper).not.toBeNull();
  });

  it("shows loading state while spaces are fetching", () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useSpaces>);

    renderPage();
    expect(screen.getByText(/Loading dashboard/i)).toBeInTheDocument();
  });

  it("shows empty state when there are no spaces", () => {
    renderPage();
    expect(screen.getByText(/Create your first space/i)).toBeInTheDocument();
  });

  it("shows stat tiles when spaces data is loaded", () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: {
        spaces: [],
        totals: { backlog: 3, active: 1, waiting: 2, done: 5, archived: 0 },
        feature_totals: { backlog: 0 },
      },
      isLoading: false,
    } as unknown as ReturnType<typeof useSpaces>);

    renderPage();
    expect(screen.getByText("To Do")).toBeInTheDocument();
    expect(screen.getByText("Active agents")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("renders New task and New space action buttons", () => {
    renderPage();
    expect(screen.getByText(/New task/i)).toBeInTheDocument();
    // Both the header action and empty-state link say "New space"; expect at least one
    expect(screen.getAllByText(/New space/i).length).toBeGreaterThanOrEqual(1);
  });
});
