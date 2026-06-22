import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { Space } from "../../types";

// ---------------------------------------------------------------------------
// Mock heavy sub-components (repo link, autopilot, form) to avoid side effects
// ---------------------------------------------------------------------------

vi.mock("../../components/spaces/SpaceForm", () => ({
  SpaceForm: ({ mode }: { mode: string }) => (
    <div data-testid="space-form" data-mode={mode}>SpaceForm</div>
  ),
}));

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

let mockSpace: Space | null = null;
let mockSpaceLoading = false;
const mockUpdateMutate = vi.fn();
const mockLinkMutate = vi.fn();
const mockUnlinkMutate = vi.fn();
const mockImportMutate = vi.fn();
const mockDeleteMutate = vi.fn();

vi.mock("../../hooks/useSpaces", () => ({
  useSpace: () => ({
    data: mockSpace,
    isLoading: mockSpaceLoading,
  }),
  useUpdateSpace: () => ({
    mutateAsync: mockUpdateMutate,
    isPending: false,
    error: null,
  }),
  useLinkSpaceRepo: () => ({
    mutateAsync: mockLinkMutate,
    isPending: false,
    error: null,
  }),
  useUnlinkSpaceRepo: () => ({
    mutateAsync: mockUnlinkMutate,
    isPending: false,
    error: null,
  }),
  useImportSpace: () => ({
    mutateAsync: mockImportMutate,
    isPending: false,
    error: null,
  }),
  useDeleteSpace: () => ({
    mutateAsync: mockDeleteMutate,
    isPending: false,
  }),
}));

vi.mock("../../api", () => ({
  api: {
    exportSpace: vi.fn(),
  },
}));

// Import component AFTER vi.mock
import { SpaceSettingsPage } from "../SpaceSettingsPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSpace(overrides: Partial<Space> = {}): Space {
  return {
    id: "space-1",
    name: "My Space",
    color: "#4f46e5",
    icon: null,
    description: "",
    git_repo_url: null,
    git_branch: null,
    git_share_cronos: false,
    agent_defaults: {},
    autopilot: "disabled",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-02T00:00:00Z",
    ...overrides,
  };
}

function renderPage(spaceId = "space-1") {
  return render(
    <MemoryRouter initialEntries={[`/spaces/${spaceId}/settings`]}>
      <Routes>
        <Route path="/spaces/:spaceId/settings" element={<SpaceSettingsPage />} />
        <Route path="/" element={<div>Dashboard</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SpaceSettingsPage", () => {
  beforeEach(() => {
    mockSpace = null;
    mockSpaceLoading = false;
    mockUpdateMutate.mockReset();
  });

  it("renders loading state", () => {
    mockSpaceLoading = true;
    renderPage();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders h1 with class text-title containing the space name", () => {
    mockSpace = makeSpace({ name: "My Space" });
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1, name: /my space/i });
    expect(h1).toBeInTheDocument();
    expect(h1.className).toContain("text-title");
  });

  it("h1 does not carry ad-hoc size classes (text-[22px], uppercase, tracking-[0.14em])", () => {
    mockSpace = makeSpace({ name: "My Space" });
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.className).not.toContain("text-[22px]");
    expect(h1.className).not.toContain("uppercase");
    expect(h1.className).not.toContain("tracking-[");
    expect(h1.className).not.toContain("text-lg");
    expect(h1.className).not.toContain("text-sm");
  });

  it("wraps content in PageContainer with width='reading' (max-w-[768px])", () => {
    mockSpace = makeSpace();
    const { container } = renderPage();
    const wrapper = container.querySelector(".max-w-\\[768px\\]");
    expect(wrapper).not.toBeNull();
  });

  it("does NOT use the wide content container (max-w-[1280px] or old max-w-5xl)", () => {
    mockSpace = makeSpace();
    const { container } = renderPage();
    expect(container.querySelector(".max-w-\\[1280px\\]")).toBeNull();
    expect(container.querySelector(".max-w-5xl")).toBeNull();
  });

  it("renders breadcrumb with Dashboard and space name links", () => {
    mockSpace = makeSpace({ name: "My Space" });
    renderPage();
    const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
    expect(dashboardLink).toBeInTheDocument();
    expect(dashboardLink.getAttribute("href")).toBe("/");
  });

  it("renders 'Back to board' link", () => {
    mockSpace = makeSpace({ id: "space-1", name: "My Space" });
    renderPage();
    const backLink = screen.getByRole("link", { name: /back to board/i });
    expect(backLink).toBeInTheDocument();
    expect(backLink.getAttribute("href")).toBe("/spaces/space-1");
  });

  it("renders SpaceForm in edit mode", () => {
    mockSpace = makeSpace();
    renderPage();
    const form = screen.getByTestId("space-form");
    expect(form).toBeInTheDocument();
    expect(form.getAttribute("data-mode")).toBe("edit");
  });

  it("shows 'Space not found' when space is null and not loading", () => {
    mockSpace = null;
    mockSpaceLoading = false;
    renderPage();
    expect(screen.getByText(/space not found/i)).toBeInTheDocument();
  });
});
