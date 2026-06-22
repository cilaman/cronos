import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../components/TreeView", () => ({
  TreeView: ({ archivedOnly }: { archivedOnly: boolean }) => (
    <div data-testid="tree-view" data-archived-only={String(archivedOnly)}>
      TreeView
    </div>
  ),
}));

vi.mock("../../components/SpaceFilterDropdown", () => ({
  SpaceFilterDropdown: () => (
    <div data-testid="space-filter-dropdown">SpaceFilterDropdown</div>
  ),
}));

import { ArchivedPage } from "../ArchivedPage";

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function renderPage() {
  return render(
    <MemoryRouter>
      <ArchivedPage />
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ArchivedPage — PageHeader text-title migration", () => {
  it("renders an h1 with class text-title", () => {
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1).toBeTruthy();
    expect(h1?.className).toContain("text-title");
  });

  it("h1 text content is 'Archived'", () => {
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1?.textContent).toBe("Archived");
  });

  it("h1 does not use ad-hoc size classes text-[13px] or uppercase tracking-[0.18em]", () => {
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1?.className).not.toContain("text-[13px]");
    expect(h1?.className).not.toContain("uppercase");
    expect(h1?.className).not.toContain("tracking-[0.18em]");
  });

  it("renders SpaceFilterDropdown for space filtering", () => {
    renderPage();
    expect(screen.getByTestId("space-filter-dropdown")).toBeInTheDocument();
  });

  it("renders TreeView with archivedOnly=true", () => {
    renderPage();
    const treeView = screen.getByTestId("tree-view");
    expect(treeView).toBeInTheDocument();
    expect(treeView.getAttribute("data-archived-only")).toBe("true");
  });
});
