import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: () => ({
    data: {
      spaces: [
        {
          id: "space-1",
          name: "My Space",
          color: "#15803D",
          icon: null,
          task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
          last_activity_at: null,
          autopilot: "disabled",
        },
      ],
      totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
    },
    isLoading: false,
  }),
}));

vi.mock("../../components/FeaturesBoard", () => ({
  FeaturesBoard: ({ spaceId }: { spaceId: string }) => (
    <div data-testid="features-board" data-space-id={spaceId}>
      FeaturesBoard
    </div>
  ),
}));

vi.mock("../../components/SpaceFilterDropdown", () => ({
  SpaceFilterDropdown: () => (
    <div data-testid="space-filter-dropdown">SpaceFilterDropdown</div>
  ),
}));

import { FeaturesPage } from "../FeaturesPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderScopedPage(spaceId = "space-1") {
  return render(
    <MemoryRouter initialEntries={[`/spaces/${spaceId}/features`]}>
      <Routes>
        <Route path="/spaces/:spaceId/features" element={<FeaturesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderGlobalPage() {
  return render(
    <MemoryRouter initialEntries={["/features"]}>
      <Routes>
        <Route path="/features" element={<FeaturesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FeaturesPage — scoped (spaceId in URL)", () => {
  it("renders an h1 with class text-title", () => {
    renderScopedPage();
    const h1 = document.querySelector("h1");
    expect(h1).toBeTruthy();
    expect(h1?.className).toContain("text-title");
  });

  it("h1 does not use ad-hoc size classes text-[13px] or uppercase tracking-[0.18em]", () => {
    renderScopedPage();
    const h1 = document.querySelector("h1");
    expect(h1?.className).not.toContain("text-[13px]");
    expect(h1?.className).not.toContain("uppercase");
    expect(h1?.className).not.toContain("tracking-[0.18em]");
  });

  it("renders the space name as h1 title when space data is loaded", () => {
    renderScopedPage("space-1");
    const h1 = document.querySelector("h1");
    expect(h1?.textContent).toBe("My Space");
  });

  it("renders FeaturesBoard with the correct spaceId", () => {
    renderScopedPage("space-1");
    const board = screen.getByTestId("features-board");
    expect(board).toBeInTheDocument();
    expect(board.getAttribute("data-space-id")).toBe("space-1");
  });
});

describe("FeaturesPage — global (no spaceId in URL)", () => {
  beforeEach(() => {
    // localStorage may contain stale data between tests
    try {
      localStorage.removeItem("cronos.features.lastSpaceId");
    } catch {
      /* ignore */
    }
  });

  it("renders an h1 with class text-title", () => {
    renderGlobalPage();
    const h1 = document.querySelector("h1");
    expect(h1).toBeTruthy();
    expect(h1?.className).toContain("text-title");
  });

  it("h1 does not use ad-hoc size classes", () => {
    renderGlobalPage();
    const h1 = document.querySelector("h1");
    expect(h1?.className).not.toContain("uppercase");
    expect(h1?.className).not.toContain("tracking-[0.18em]");
    expect(h1?.className).not.toContain("text-[13px]");
  });

  it("renders SpaceFilterDropdown for space selection", () => {
    renderGlobalPage();
    expect(screen.getByTestId("space-filter-dropdown")).toBeInTheDocument();
  });
});
