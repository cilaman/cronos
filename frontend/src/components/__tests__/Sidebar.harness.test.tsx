import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock useSpaces so Sidebar renders without hitting the network.
vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: () => ({ data: { spaces: [] } }),
}));

// Mock sub-components that make extra hook calls or network requests.
vi.mock("../ThemePicker", () => ({
  ThemePicker: () => <div data-testid="theme-picker-mock" />,
}));
vi.mock("../BuildInfo", () => ({
  BuildInfo: () => <div data-testid="build-info-mock" />,
}));

// Import AFTER mocks
import { Sidebar } from "../Sidebar";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

/**
 * Render Sidebar inside a route that has a spaceId param (simulates /spaces/:spaceId/... routes).
 */
function renderInsideSpaceRoute(spaceId = "test-space") {
  const client = makeClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/spaces/${spaceId}/board`]}>
        <Routes>
          <Route
            path="/spaces/:spaceId/*"
            element={<Sidebar />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * Render Sidebar on a non-space route (e.g. the root dashboard) where spaceId is undefined.
 */
function renderOutsideSpaceRoute() {
  const client = makeClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Sidebar />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Sidebar — harnesses nav entry", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows Harnesses link when rendered inside a space route (spaceId defined)", () => {
    renderInsideSpaceRoute("test-space");

    const link = screen.getByRole("link", { name: /harnesses/i });
    expect(link).toBeInTheDocument();
  });

  it("Harnesses link href points to /spaces/{spaceId}/harnesses", () => {
    renderInsideSpaceRoute("my-space");

    const link = screen.getByRole("link", { name: /harnesses/i });
    expect(link).toHaveAttribute("href", "/spaces/my-space/harnesses");
  });

  it("does NOT show Harnesses link on a non-space route (spaceId undefined)", () => {
    renderOutsideSpaceRoute();

    expect(screen.queryByRole("link", { name: /harnesses/i })).not.toBeInTheDocument();
  });

  it("Harnesses link renders alongside existing nav entries (Stats still present)", () => {
    renderInsideSpaceRoute("test-space");

    // Both standard nav entries and the harnesses entry should exist.
    expect(screen.getByRole("link", { name: /stats/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /harnesses/i })).toBeInTheDocument();
  });

  it("Stats link is present even without a spaceId (non-space route)", () => {
    renderOutsideSpaceRoute();

    // Ensure standard nav entries still render on non-space routes.
    expect(screen.getByRole("link", { name: /stats/i })).toBeInTheDocument();
    // But no harnesses link.
    expect(screen.queryByRole("link", { name: /harnesses/i })).not.toBeInTheDocument();
  });
});
