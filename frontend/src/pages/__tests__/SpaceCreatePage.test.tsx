import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../hooks/useSpaces", () => ({
  useCreateSpace: vi.fn(),
}));

vi.mock("../../components/spaces/SpaceForm", () => ({
  SpaceForm: ({ mode }: { mode: string }) => (
    <div data-testid="space-form">SpaceForm:{mode}</div>
  ),
}));

import { SpaceCreatePage } from "../SpaceCreatePage";
import { useCreateSpace } from "../../hooks/useSpaces";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setupDefaults() {
  vi.mocked(useCreateSpace).mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
    error: null,
  } as unknown as ReturnType<typeof useCreateSpace>);
}

function renderPage() {
  return render(
    <MemoryRouter>
      <SpaceCreatePage />
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SpaceCreatePage", () => {
  beforeEach(() => {
    setupDefaults();
  });

  it("renders the page title in an h1 with text-title class", () => {
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toBeInTheDocument();
    expect(h1.textContent).toBe("New space");
    expect(h1.className).toContain("text-title");
  });

  it("h1 does not carry ad-hoc size classes", () => {
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.className).not.toMatch(/text-\[22px\]/);
    expect(h1.className).not.toMatch(/uppercase/);
    expect(h1.className).not.toMatch(/tracking-\[/);
  });

  it("wraps content in a PageContainer with reading width (max-w-[768px])", () => {
    const { container } = renderPage();
    const wrapper = container.querySelector(".max-w-\\[768px\\]");
    expect(wrapper).not.toBeNull();
  });

  it("does not use content width (max-w-[1280px])", () => {
    const { container } = renderPage();
    const wrapper = container.querySelector(".max-w-\\[1280px\\]");
    expect(wrapper).toBeNull();
  });

  it("renders the SpaceForm component", () => {
    renderPage();
    expect(screen.getByTestId("space-form")).toBeInTheDocument();
  });

  it("renders Dashboard breadcrumb linking to /", () => {
    renderPage();
    const dashboardLink = screen.getByRole("link", { name: /Dashboard/i });
    expect(dashboardLink).toBeInTheDocument();
    expect(dashboardLink).toHaveAttribute("href", "/");
  });

  it("renders page subtitle about spaces", () => {
    renderPage();
    expect(
      screen.getByText(/Spaces own their own tasks/i),
    ).toBeInTheDocument();
  });
});
