/**
 * Sidebar wordmark tests (I4) — assert that:
 *   (a) CronosMark SVG renders (data-testid="cronos-mark", role="img")
 *   (b) "CRONOS" text node is present with JetBrains Mono font class (font-mono)
 *   (c) The legacy pulse-dot span is NOT present
 *       (class "bg-accent-bright shadow-accent-glow" was the old pulse-dot indicator)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mocks — must be declared before the component import
// ---------------------------------------------------------------------------

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: () => ({ data: { spaces: [] } }),
}));

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

function renderSidebar() {
  const client = makeClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="*" element={<Sidebar />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Sidebar — CronosMark wordmark (I4)", () => {
  it("renders the CronosMark SVG via data-testid", () => {
    renderSidebar();
    expect(screen.getByTestId("cronos-mark")).toBeInTheDocument();
  });

  it("CronosMark has role=img for accessibility", () => {
    renderSidebar();
    expect(screen.getByRole("img", { name: /cronos mark/i })).toBeInTheDocument();
  });

  it("renders the CRONOS text node in uppercase", () => {
    renderSidebar();
    // The text node renders as uppercase "CRONOS" (explicit, not CSS transform).
    expect(screen.getByText("CRONOS")).toBeInTheDocument();
  });

  it("CRONOS text node carries JetBrains Mono font class (font-mono)", () => {
    renderSidebar();
    const textNode = screen.getByText("CRONOS");
    expect(textNode.className).toMatch(/font-mono/);
  });

  it("legacy pulse-dot span is absent (bg-accent-bright + shadow-accent-glow removed)", () => {
    const { container } = renderSidebar();
    // The old wordmark used a <span> with both bg-accent-bright and shadow-accent-glow.
    const pulseDot = container.querySelector(".bg-accent-bright.shadow-accent-glow");
    expect(pulseDot).not.toBeInTheDocument();
  });

  it("CronosMark SVG is an <svg> element", () => {
    const { container } = renderSidebar();
    const svg = container.querySelector("svg[data-testid='cronos-mark']");
    expect(svg).toBeInTheDocument();
  });

  it("CronosMark inlines the brand geometry (outer, middle, and inner rings present)", () => {
    const { container } = renderSidebar();
    const svg = container.querySelector("svg[data-testid='cronos-mark']");
    expect(svg).toBeTruthy();
    // The SVG contains circles (rings + nodes + core) — at least 7 total.
    const circles = svg!.querySelectorAll("circle");
    expect(circles.length).toBeGreaterThanOrEqual(7);
  });
});
