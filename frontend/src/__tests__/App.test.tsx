import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock Sidebar to avoid deep dependency tree
vi.mock("../components/Sidebar", () => ({
  Sidebar: ({ onClose }: { onClose: () => void }) => (
    <nav data-testid="sidebar-mock" aria-label="Sidebar">
      <button type="button" onClick={onClose} data-testid="sidebar-close">
        Close
      </button>
    </nav>
  ),
}));

// Mock Outlet (react-router-dom) to avoid router setup complexity
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    Outlet: () => <div data-testid="outlet-mock" />,
  };
});

import App from "../App";

function renderApp() {
  return render(
    <MemoryRouter>
      <App />
    </MemoryRouter>
  );
}

describe("App", () => {
  it("renders the mobile top bar with the Open navigation button", () => {
    renderApp();
    // The mobile nav button has aria-label="Open navigation"
    expect(screen.getByRole("button", { name: /open navigation/i })).toBeInTheDocument();
  });

  it("renders a Lucide SVG icon inside the mobile nav button", () => {
    renderApp();
    const button = screen.getByRole("button", { name: /open navigation/i });
    const svg = button.querySelector("svg");
    expect(svg).not.toBeNull();
    // Lucide always adds the 'lucide' class to SVG elements
    expect(svg?.classList.contains("lucide")).toBe(true);
  });

  it("nav button icon is aria-hidden (decorative)", () => {
    renderApp();
    const button = screen.getByRole("button", { name: /open navigation/i });
    const svg = button.querySelector("svg");
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
  });

  it("nav button SVG has no inline hand-rolled rect elements (replaced by Lucide)", () => {
    renderApp();
    const button = screen.getByRole("button", { name: /open navigation/i });
    const rects = button.querySelectorAll("svg > rect");
    // The old hamburger had 3 <rect> children of the SVG directly;
    // Lucide's Menu icon uses <line> elements instead.
    expect(rects.length).toBe(0);
  });

  it("renders the Sidebar component", () => {
    renderApp();
    expect(screen.getByTestId("sidebar-mock")).toBeInTheDocument();
  });

  it("does not touch emoji space avatars (R7) — brand text Cronos is plain text", () => {
    renderApp();
    // The mobile top bar shows "Cronos" as text — no emoji injection
    expect(screen.getByText("Cronos")).toBeInTheDocument();
  });
});
