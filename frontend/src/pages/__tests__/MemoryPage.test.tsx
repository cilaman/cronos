import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { MemoryItem, SpacesResponse } from "../../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockSpacesResponse: SpacesResponse = {
  spaces: [],
  totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
};

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: () => ({ data: mockSpacesResponse }),
}));

let mockMemoryItems: MemoryItem[] = [];
let mockIsLoading = false;

vi.mock("../../hooks/useMemory", () => ({
  useMemoryItems: () => ({ data: mockMemoryItems, isLoading: mockIsLoading }),
  useConfirmMemory: () => ({ mutate: vi.fn(), isPending: false }),
  useRejectMemory: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { MemoryPage } from "../MemoryPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<MemoryItem> = {}): MemoryItem {
  return {
    id: "item-1",
    title: "Test memory",
    body: "Some body text",
    kind: "fact",
    scope: "global",
    score: 0.8,
    confidence: 0.9,
    ref_count: 3,
    confirmed: true,
    sources: [],
    links: [],
    last_used_at: "2026-01-01T00:00:00Z",
    ttl_until: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <MemoryPage />
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MemoryPage — PageHeader text-title migration", () => {
  beforeEach(() => {
    mockMemoryItems = [];
    mockIsLoading = false;
    mockSpacesResponse = {
      spaces: [],
      totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
    };
  });

  it("renders an h1 with class text-title", () => {
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1).toBeTruthy();
    expect(h1?.className).toContain("text-title");
  });

  it("h1 text content is 'Memory Browser'", () => {
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1?.textContent).toBe("Memory Browser");
  });

  it("h1 does not use ad-hoc size classes text-[22px] or uppercase tracking-[0.14em]", () => {
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1?.className).not.toContain("text-[22px]");
    expect(h1?.className).not.toContain("uppercase");
    expect(h1?.className).not.toContain("tracking-[0.14em]");
  });

  it("renders 'Memory Browser' heading", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Memory Browser" })).toBeInTheDocument();
  });

  it("shows unconfirmed badge in header actions when there are unconfirmed items", () => {
    mockMemoryItems = [makeItem({ confirmed: false })];
    renderPage();
    expect(screen.getByText("1 unconfirmed")).toBeInTheDocument();
  });

  it("does not show unconfirmed badge in header when all items are confirmed", () => {
    mockMemoryItems = [makeItem({ confirmed: true })];
    renderPage();
    // The header badge shows "N unconfirmed"; no such element should exist
    expect(screen.queryByText(/\d+ unconfirmed/)).toBeNull();
  });

  it("shows loading indicator while fetching items", () => {
    mockIsLoading = true;
    mockMemoryItems = [];
    renderPage();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows empty state when no items in scope", () => {
    mockMemoryItems = [];
    renderPage();
    expect(
      screen.getByText("No memory items in this scope."),
    ).toBeInTheDocument();
  });

  it("renders memory items list", () => {
    mockMemoryItems = [makeItem({ title: "Alpha memory" })];
    renderPage();
    expect(screen.getByText("Alpha memory")).toBeInTheDocument();
  });

  it("uses reading-width PageContainer (max-w-[768px])", () => {
    const { container } = renderPage();
    // PageContainer with width='reading' renders max-w-[768px]
    const pageContainer = container.querySelector("[class*='max-w-\\[768px\\]']");
    expect(pageContainer).toBeTruthy();
  });
});
