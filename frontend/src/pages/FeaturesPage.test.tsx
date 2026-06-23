/**
 * FeaturesPage.test.tsx
 *
 * Tests for I9: verifies that:
 * 1. Loading state shows Skeleton component (not an animate-spin spinner, not "Loading spaces…" text)
 * 2. When spaces data is loaded, FeaturesBoard renders (not loading skeleton)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { FeaturesPage } from "./FeaturesPage";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let spacesIsLoading = false;
let spacesData: { spaces: { id: string; name: string }[] } | undefined = undefined;

vi.mock("../hooks/useSpaces", () => ({
  useSpaces: () => ({
    data: spacesData,
    isLoading: spacesIsLoading,
  }),
}));

vi.mock("../components/FeaturesBoard", () => ({
  FeaturesBoard: ({ spaceId }: { spaceId: string }) => (
    <div data-testid="features-board-mock" data-space-id={spaceId}>
      FeaturesBoard
    </div>
  ),
}));

vi.mock("../components/SpaceFilterDropdown", () => ({
  SpaceFilterDropdown: () => <div data-testid="space-filter-dropdown-mock" />,
}));

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

function renderPage(path = "/features") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/features" element={<FeaturesPage />} />
        <Route path="/spaces/:spaceId/features" element={<FeaturesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderScopedPage(spaceId: string) {
  return render(
    <MemoryRouter initialEntries={[`/spaces/${spaceId}/features`]}>
      <Routes>
        <Route path="/spaces/:spaceId/features" element={<FeaturesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FeaturesPage — loading state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    spacesIsLoading = false;
    spacesData = undefined;
  });

  it("shows Skeleton (role=status, aria-label=Loading) when spaces are loading", () => {
    spacesIsLoading = true;
    spacesData = undefined;
    renderPage();

    const skeletons = screen.getAllByRole("status", { name: "Loading" });
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("does NOT show the animate-spin spinner when loading", () => {
    spacesIsLoading = true;
    spacesData = undefined;
    const { container } = renderPage();

    // Old implementation had animate-spin class; the new one must NOT have it
    const spinners = container.querySelectorAll(".animate-spin");
    expect(spinners).toHaveLength(0);
  });

  it("does NOT show 'Loading spaces' text when loading", () => {
    spacesIsLoading = true;
    spacesData = undefined;
    renderPage();

    // Old loading text was "Loading spaces…"
    expect(screen.queryByText(/loading spaces/i)).not.toBeInTheDocument();
  });

  it("renders card variant Skeleton bars (animate-shimmer) during loading", () => {
    spacesIsLoading = true;
    spacesData = undefined;
    const { container } = renderPage();

    // Card variant emits animate-shimmer bars
    const shimmerBars = container.querySelectorAll(".animate-shimmer");
    expect(shimmerBars.length).toBeGreaterThan(0);
  });
});

describe("FeaturesPage — loaded state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    spacesIsLoading = false;
    spacesData = {
      spaces: [{ id: "space-1", name: "Space One" }],
    };
  });

  it("does NOT show Skeleton when spaces are loaded and a space is selected", () => {
    renderPage("/features?space=space-1");

    // After loading completes, role=status loading elements should not be present
    // (they may briefly appear, but with isLoading=false they should be gone)
    expect(screen.queryByRole("status", { name: "Loading" })).not.toBeInTheDocument();
  });

  it("renders the SpaceFilterDropdown toolbar on the global features route", () => {
    renderPage();
    expect(screen.getByTestId("space-filter-dropdown-mock")).toBeInTheDocument();
  });

  it("renders FeaturesBoard for the scoped route (spaceId in URL)", () => {
    renderScopedPage("space-1");
    expect(screen.getByTestId("features-board-mock")).toBeInTheDocument();
    expect(screen.getByTestId("features-board-mock")).toHaveAttribute("data-space-id", "space-1");
  });

  it("does NOT show Skeleton on the scoped route when data is loaded", () => {
    renderScopedPage("space-1");
    expect(screen.queryByRole("status", { name: "Loading" })).not.toBeInTheDocument();
  });

  it("shows 'No spaces yet.' message when spaces list is empty", () => {
    spacesData = { spaces: [] };
    renderPage();
    expect(screen.getByText(/no spaces yet/i)).toBeInTheDocument();
  });
});
