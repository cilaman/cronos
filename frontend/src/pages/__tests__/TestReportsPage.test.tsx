import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { TestReportsPage } from "../TestReportsPage";
import type {
  SpacesResponse,
  TestReport,
  TestReportSummary,
} from "../../types";

vi.mock("../../hooks/useTestReports", () => ({
  useTestReports: vi.fn(),
  useTestReport: vi.fn(),
}));

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: vi.fn(),
}));

import { useTestReports, useTestReport } from "../../hooks/useTestReports";
import { useSpaces } from "../../hooks/useSpaces";

const mockSpacesResponse: SpacesResponse = {
  spaces: [
    {
      id: "space-1",
      name: "My Space",
      color: "#15803D",
      icon: null,
      task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
      last_activity_at: null,
    },
  ],
  totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
};

const mockReportSummary: TestReportSummary = {
  id: "report-1",
  space_id: "space-1",
  task_id: null,
  report_type: "space",
  triggered_by: "tester",
  started_at: "2024-06-01T10:00:00Z",
  ended_at: "2024-06-01T10:01:00Z",
  total_passed: 15,
  total_failed: 2,
  total_errors: 0,
  total_skipped: 1,
  total_tests: 18,
  coverage_pct: 72.5,
  exit_code: 1,
  framework: "pytest",
};

const mockReport: TestReport = {
  ...mockReportSummary,
  suites: [
    {
      name: "test_api",
      tests: [
        {
          id: "tc-1",
          name: "test_create_task",
          status: "passed",
          duration_seconds: 0.12,
          error_message: null,
        },
        {
          id: "tc-2",
          name: "test_delete_task",
          status: "failed",
          duration_seconds: 0.08,
          error_message: "AssertionError: 404 != 200",
        },
      ],
      passed: 1,
      failed: 1,
      errors: 0,
      skipped: 0,
      duration_seconds: 0.2,
    },
  ],
  coverage_data: { "src/api.py": 85, "src/storage.py": 60 },
  raw_output: "FAILED test_api.py::test_delete_task",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <TestReportsPage />
    </MemoryRouter>,
  );
}

describe("TestReportsPage", () => {
  beforeEach(() => {
    vi.mocked(useSpaces).mockReturnValue({
      data: { spaces: [], totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 } },
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useTestReports).mockReturnValue({
      data: undefined,
      isLoading: false,
    } as ReturnType<typeof useTestReports>);

    vi.mocked(useTestReport).mockReturnValue({
      data: undefined,
      isLoading: false,
    } as ReturnType<typeof useTestReport>);
  });

  it("renders the Test Reports page header", () => {
    renderPage();
    expect(screen.getByText("Test Reports")).toBeInTheDocument();
  });

  it("shows 'select a space' prompt when no space is selected", () => {
    renderPage();
    expect(
      screen.getByText(/Select a space above to view test reports/i),
    ).toBeInTheDocument();
  });

  it("shows space filter dropdown when spaces exist", () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    renderPage();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText("My Space")).toBeInTheDocument();
  });

  it("shows loading indicator while reports are fetching", async () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useTestReports).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useTestReports>);

    renderPage();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "space-1");

    expect(screen.getByText(/Loading…/)).toBeInTheDocument();
  });

  it("shows 'no test reports yet' when space has no reports", async () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useTestReports).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useTestReports>);

    renderPage();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "space-1");

    expect(screen.getByText(/No test reports yet/i)).toBeInTheDocument();
  });

  it("shows summary bar with pass/fail counts when reports exist", async () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useTestReports).mockReturnValue({
      data: [mockReportSummary],
      isLoading: false,
    } as ReturnType<typeof useTestReports>);

    vi.mocked(useTestReport).mockReturnValue({
      data: mockReport,
      isLoading: false,
    } as ReturnType<typeof useTestReport>);

    renderPage();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "space-1");

    // Summary bar labels appear at least once
    // (TestStatusBadge in suite rows may also render "Passed", hence getAllBy)
    expect(screen.getAllByText("Passed").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Failed").length).toBeGreaterThanOrEqual(1);
    // Coverage tile appears in the summary bar
    expect(screen.getByText("Coverage")).toBeInTheDocument();
    // Numeric pass count from SummaryBar
    expect(screen.getByText("15")).toBeInTheDocument(); // total_passed
  });

  it("shows trend strip label when multiple reports exist", async () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useTestReports).mockReturnValue({
      data: [mockReportSummary],
      isLoading: false,
    } as ReturnType<typeof useTestReports>);

    vi.mocked(useTestReport).mockReturnValue({
      data: mockReport,
      isLoading: false,
    } as ReturnType<typeof useTestReport>);

    renderPage();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "space-1");

    expect(screen.getByText("Trend")).toBeInTheDocument();
    expect(screen.getByText(/last 1 run/i)).toBeInTheDocument();
  });

  it("shows suite details in report detail section", async () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useTestReports).mockReturnValue({
      data: [mockReportSummary],
      isLoading: false,
    } as ReturnType<typeof useTestReports>);

    vi.mocked(useTestReport).mockReturnValue({
      data: mockReport,
      isLoading: false,
    } as ReturnType<typeof useTestReport>);

    renderPage();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "space-1");

    // Suite name appears in the detail section
    expect(screen.getByText("test_api")).toBeInTheDocument();
  });

  it("shows coverage by module section when coverage_data is present", async () => {
    vi.mocked(useSpaces).mockReturnValue({
      data: mockSpacesResponse,
    } as ReturnType<typeof useSpaces>);

    vi.mocked(useTestReports).mockReturnValue({
      data: [mockReportSummary],
      isLoading: false,
    } as ReturnType<typeof useTestReports>);

    vi.mocked(useTestReport).mockReturnValue({
      data: mockReport,
      isLoading: false,
    } as ReturnType<typeof useTestReport>);

    renderPage();

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "space-1");

    expect(screen.getByText("Coverage by module")).toBeInTheDocument();
    expect(screen.getByText("src/api.py")).toBeInTheDocument();
    expect(screen.getByText("src/storage.py")).toBeInTheDocument();
  });
});
