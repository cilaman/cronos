/**
 * DashboardPage.featuretile.test.tsx
 *
 * Focused Vitest for the Features StatTile added in I4:
 *  (a) the 6th tile renders with to='/features'
 *  (b) safe-zero default when feature_totals is undefined (rollback-deploy skew)
 *  (c) the 5 existing tiles still source from totals keys (no value drift)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "./DashboardPage";
import type { SpacesResponse } from "../types";

// ── Module mocks ──────────────────────────────────────────────────────────────

vi.mock("../hooks/useSpaces", () => ({
  useSpaces: vi.fn(),
  useActivity: vi.fn(),
  useImportSpace: vi.fn(),
}));

vi.mock("../hooks/useTasks", () => ({
  useCreateTask: vi.fn(),
}));

vi.mock("../hooks/useStats", () => ({
  useGlobalStats: vi.fn(),
}));

vi.mock("../hooks/useTestReports", () => ({
  useTestReports: vi.fn(),
  useLatestTestReport: vi.fn(),
}));

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: vi.fn(() => vi.fn()),
  };
});

import { useSpaces, useActivity, useImportSpace } from "../hooks/useSpaces";
import { useCreateTask } from "../hooks/useTasks";
import { useGlobalStats } from "../hooks/useStats";
import { useTestReports, useLatestTestReport } from "../hooks/useTestReports";

// ── Fixture helpers ───────────────────────────────────────────────────────────

const baseTotals = { backlog: 3, active: 1, waiting: 2, done: 5, archived: 0 };

function makeSpacesResponse(
  feature_totals?: SpacesResponse["feature_totals"],
): SpacesResponse {
  return {
    spaces: [],
    totals: baseTotals,
    ...(feature_totals !== undefined ? { feature_totals } : {}),
  };
}

function setupDefaultMocks(spacesResponse: SpacesResponse) {
  vi.mocked(useSpaces).mockReturnValue({
    data: spacesResponse,
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
  } as unknown as ReturnType<typeof useTestReports>);

  vi.mocked(useLatestTestReport).mockReturnValue({
    data: undefined,
  } as unknown as ReturnType<typeof useLatestTestReport>);
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("DashboardPage — Features StatTile (I4)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("(a) renders the 6th tile as a link to /features with label 'Features'", () => {
    const spacesResp = makeSpacesResponse({ backlog: 7, processing: 2, planned: 1, waiting: 0, done: 3 });
    setupDefaultMocks(spacesResp);
    renderDashboard();

    // The tile label should appear
    expect(screen.getByText("Features")).toBeInTheDocument();

    // The tile should be a link to /features
    const link = screen.getByRole("link", { name: /features/i });
    expect(link).toHaveAttribute("href", "/features");
  });

  it("(a) renders the Features tile value from feature_totals.backlog", () => {
    const spacesResp = makeSpacesResponse({ backlog: 7, processing: 2, planned: 1, waiting: 0, done: 3 });
    setupDefaultMocks(spacesResp);
    renderDashboard();

    // Value 7 should appear in the Features tile context
    // (We check for the text "7" appearing on screen — the tile renders a <p> with the value)
    const featuresTile = screen.getByRole("link", { name: /features/i });
    expect(featuresTile).toHaveTextContent("7");
  });

  it("(b) renders 0 for the Features tile when feature_totals is undefined (safe-zero default)", () => {
    // feature_totals omitted — simulates an older API deploy that lacks the field
    const spacesResp = makeSpacesResponse(undefined);
    setupDefaultMocks(spacesResp);
    renderDashboard();

    expect(screen.getByText("Features")).toBeInTheDocument();

    const featuresTile = screen.getByRole("link", { name: /features/i });
    expect(featuresTile).toHaveTextContent("0");
  });

  it("(b) renders 0 for the Features tile when feature_totals.backlog is absent", () => {
    // feature_totals present but backlog key missing (partial field)
    const spacesResp = makeSpacesResponse({ processing: 1, planned: 0, waiting: 0, done: 0 } as SpacesResponse["feature_totals"]);
    setupDefaultMocks(spacesResp);
    renderDashboard();

    const featuresTile = screen.getByRole("link", { name: /features/i });
    expect(featuresTile).toHaveTextContent("0");
  });

  it("(c) the 5 existing tiles still source from totals (no value drift)", () => {
    // baseTotals: backlog=3, active=1, waiting=2, done=5
    // feature_totals.backlog=99 — deliberately different from totals.backlog to detect drift
    const spacesResp = makeSpacesResponse({ backlog: 99, processing: 0, planned: 0, waiting: 0, done: 0 });
    setupDefaultMocks(spacesResp);
    renderDashboard();

    // The Features tile value = 99 (from feature_totals.backlog)
    const featuresTile = screen.getByRole("link", { name: /features/i });
    expect(featuresTile).toHaveTextContent("99");
    expect(featuresTile).toHaveAttribute("href", "/features");

    // The "To Do" tile must show 3 (from totals.backlog=3), not 99 (feature_totals.backlog)
    const toDoLabel = screen.getByText("To Do");
    const toDoTile = toDoLabel.closest("a");
    expect(toDoTile).not.toBeNull();
    expect(toDoTile).toHaveAttribute("href", "/board");
    expect(toDoTile).toHaveTextContent("3");

    // Active agents tile must show 1 (totals.active=1)
    const activeLabel = screen.getByText("Active agents");
    const activeTile = activeLabel.closest("a");
    expect(activeTile).not.toBeNull();
    expect(activeTile).toHaveAttribute("href", "/board");
    expect(activeTile).toHaveTextContent("1");

    // Waiting tile must show 2 (totals.waiting=2)
    const waitingLabel = screen.getByText("Waiting");
    // The Waiting tile is the one inside the stat-tile section (closest <a>)
    const waitingTile = waitingLabel.closest("a");
    expect(waitingTile).not.toBeNull();
    expect(waitingTile).toHaveAttribute("href", "/board");
    expect(waitingTile).toHaveTextContent("2");

    // Done tile must show 5 (totals.done=5)
    const doneLabel = screen.getByText("Done");
    const doneTile = doneLabel.closest("a");
    expect(doneTile).not.toBeNull();
    expect(doneTile).toHaveAttribute("href", "/board");
    expect(doneTile).toHaveTextContent("5");
  });
});
