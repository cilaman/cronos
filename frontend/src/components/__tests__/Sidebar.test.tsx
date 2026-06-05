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

function renderAtRoute(path: string, routePattern = "*") {
  const client = makeClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={routePattern} element={<Sidebar />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderAtRoot() {
  return renderAtRoute("/", "/");
}

function renderAtBoard() {
  return renderAtRoute("/board", "/board");
}

function renderAtFeatures() {
  return renderAtRoute("/features", "/features");
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// 1. Tasks nav item (renamed from Kanban)
// ---------------------------------------------------------------------------

describe("Sidebar — Tasks nav item (renamed from Kanban)", () => {
  it("renders a 'Tasks' nav link", () => {
    renderAtRoot();
    expect(screen.getByRole("link", { name: /tasks/i })).toBeInTheDocument();
  });

  it("Tasks link href points to /board", () => {
    renderAtRoot();
    const link = screen.getByRole("link", { name: /tasks/i });
    expect(link).toHaveAttribute("href", "/board");
  });

  it("does NOT render a 'Kanban' nav link (label was renamed)", () => {
    renderAtRoot();
    expect(screen.queryByRole("link", { name: /^kanban$/i })).not.toBeInTheDocument();
  });

  it("Tasks link gets active styling when on /board route", () => {
    renderAtBoard();
    // NavLink applies shadow-inset-hairline and text-ink (not text-ink-muted) when active.
    const link = screen.getByRole("link", { name: /tasks/i });
    expect(link.className).toMatch(/shadow-inset-hairline/);
  });
});

// ---------------------------------------------------------------------------
// 2. Features nav item
// ---------------------------------------------------------------------------

describe("Sidebar — Features nav item", () => {
  it("renders a 'Features' nav link", () => {
    renderAtRoot();
    expect(screen.getByRole("link", { name: /^features$/i })).toBeInTheDocument();
  });

  it("Features link href points to /features", () => {
    renderAtRoot();
    const link = screen.getByRole("link", { name: /^features$/i });
    expect(link).toHaveAttribute("href", "/features");
  });

  it("Features link gets active styling when on /features route", () => {
    renderAtFeatures();
    const link = screen.getByRole("link", { name: /^features$/i });
    // The primaryNavLinkClasses function applies shadow-inset-hairline when isActive is true.
    expect(link.className).toMatch(/shadow-inset-hairline/);
  });

  it("Features link does NOT have active styling when on a different route", () => {
    renderAtRoot();
    const link = screen.getByRole("link", { name: /^features$/i });
    // On the root route, the Features link should not have the active bg-surface-2 class.
    // Note: inactive state has hover:bg-surface-2/60 but NOT the solid bg-surface-2 used when active.
    // We check that the link has the muted text class (inactive) rather than the shadow class (active).
    expect(link.className).not.toMatch(/shadow-inset-hairline/);
    expect(link.className).toMatch(/text-ink-muted/);
  });
});

// ---------------------------------------------------------------------------
// 3. Order — Tasks appears immediately before Features
// ---------------------------------------------------------------------------

describe("Sidebar — nav item ordering", () => {
  it("Tasks link appears before Features link in the DOM", () => {
    renderAtRoot();
    const links = screen.getAllByRole("link");
    const taskIdx = links.findIndex((l) => /^tasks$/i.test(l.textContent ?? ""));
    const featureIdx = links.findIndex((l) => /^features$/i.test(l.textContent ?? ""));
    expect(taskIdx).toBeGreaterThanOrEqual(0);
    expect(featureIdx).toBeGreaterThanOrEqual(0);
    expect(taskIdx).toBeLessThan(featureIdx);
  });

  it("Features link appears before Archived link in the DOM", () => {
    renderAtRoot();
    const links = screen.getAllByRole("link");
    const featureIdx = links.findIndex((l) => /^features$/i.test(l.textContent ?? ""));
    const archivedIdx = links.findIndex((l) => /^archived$/i.test(l.textContent ?? ""));
    expect(featureIdx).toBeGreaterThanOrEqual(0);
    expect(archivedIdx).toBeGreaterThanOrEqual(0);
    expect(featureIdx).toBeLessThan(archivedIdx);
  });

  it("existing nav items (Dashboard, Archived, Stats, Harnesses) are still present", () => {
    renderAtRoot();
    expect(screen.getByRole("link", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /archived/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /stats/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /harnesses/i })).toBeInTheDocument();
  });
});
