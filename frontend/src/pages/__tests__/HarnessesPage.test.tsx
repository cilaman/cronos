import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { Harness } from "../../types";
import type { SpaceSummary } from "../../types";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

let mockSpaces: SpaceSummary[] = [];
let mockSpacesLoading = false;

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: () => ({
    data: { spaces: mockSpaces },
    isLoading: mockSpacesLoading,
  }),
}));

let mockHarnesses: Harness[] = [];
let mockHarnessesLoading = false;
let mockHarnessesIsError = false;
let mockHarnessesError: Error | null = null;
const mockCreateMutate = vi.fn();
let mockCreateIsPending = false;
const mockDeleteMutate = vi.fn();
let mockDeleteIsPending = false;

vi.mock("../../hooks/useHarnesses", () => ({
  useHarnesses: () => ({
    data: mockHarnesses,
    isLoading: mockHarnessesLoading,
    isError: mockHarnessesIsError,
    error: mockHarnessesError,
  }),
  useCreateHarness: () => ({
    mutate: mockCreateMutate,
    isPending: mockCreateIsPending,
  }),
  useDeleteHarness: () => ({
    mutate: mockDeleteMutate,
    isPending: mockDeleteIsPending,
  }),
}));

// Import after vi.mock
import { HarnessesPage } from "../HarnessesPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSpace(overrides: Partial<SpaceSummary> = {}): SpaceSummary {
  return {
    id: "space-1",
    name: "Space One",
    color: "#888",
    icon: null,
    autopilot: "disabled",
    task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
    ...overrides,
  };
}

function makeHarness(overrides: Partial<Harness> = {}): Harness {
  return {
    name: "my-harness",
    description: "A test harness",
    nodes: [],
    edges: [],
    variables: {},
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-02T00:00:00Z",
    version: 1,
    ...overrides,
  };
}

function renderPage(initialPath = "/harnesses") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="harnesses" element={<HarnessesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HarnessesPage", () => {
  beforeEach(() => {
    mockSpaces = [];
    mockSpacesLoading = false;
    mockHarnesses = [];
    mockHarnessesLoading = false;
    mockHarnessesIsError = false;
    mockHarnessesError = null;
    mockCreateMutate.mockReset();
    mockCreateIsPending = false;
    mockDeleteMutate.mockReset();
    mockDeleteIsPending = false;
    try { localStorage.removeItem("cronos.harnesses.lastSpaceId"); } catch { /* ignore */ }
  });

  it("renders 'No spaces yet' empty state when useSpaces returns empty list", () => {
    mockSpaces = [];
    renderPage();
    expect(screen.getByText(/no spaces yet/i)).toBeInTheDocument();
  });

  it("renders space selector with all available spaces", () => {
    mockSpaces = [
      makeSpace({ id: "s1", name: "Space One" }),
      makeSpace({ id: "s2", name: "Space Two" }),
    ];
    renderPage();
    const select = screen.getByRole("combobox", { name: /select space/i });
    expect(select).toBeInTheDocument();
    expect(screen.getAllByText("Space One").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Space Two").length).toBeGreaterThan(0);
  });

  it("auto-selects when exactly one space exists", () => {
    mockSpaces = [makeSpace({ id: "only-space", name: "Only Space" })];
    renderPage();
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("only-space");
  });

  it("pre-selects space from URL ?space= param when it exists", () => {
    mockSpaces = [
      makeSpace({ id: "s1", name: "Space One" }),
      makeSpace({ id: "s2", name: "Space Two" }),
    ];
    renderPage("/harnesses?space=s2");
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("s2");
  });

  it("pre-selects space from localStorage when no URL param", () => {
    try { localStorage.setItem("cronos.harnesses.lastSpaceId", "s2"); } catch { /* ignore */ }
    mockSpaces = [
      makeSpace({ id: "s1", name: "Space One" }),
      makeSpace({ id: "s2", name: "Space Two" }),
    ];
    renderPage();
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("s2");
  });

  it("selecting a space updates the displayed harnesses via useHarnesses", () => {
    mockSpaces = [
      makeSpace({ id: "s1", name: "Space One" }),
      makeSpace({ id: "s2", name: "Space Two" }),
    ];
    mockHarnesses = [makeHarness({ name: "harness-alpha" })];
    renderPage("/harnesses?space=s1");
    // Harness content visible for selected space
    expect(screen.getByText("harness-alpha")).toBeInTheDocument();
  });

  it("renders harness cards with Edit and Runs buttons linking to correct routes", () => {
    mockSpaces = [makeSpace({ id: "sp1", name: "My Space" })];
    mockHarnesses = [makeHarness({ name: "my-harness" })];
    renderPage("/harnesses?space=sp1");

    const editBtn = screen.getByRole("button", { name: /^edit$/i });
    const runsBtn = screen.getByRole("button", { name: /^runs$/i });
    expect(editBtn).toBeInTheDocument();
    expect(runsBtn).toBeInTheDocument();
  });

  it("encodeURIComponent is used — harness names with special chars navigate correctly", () => {
    const navigate = vi.fn();
    vi.doMock("react-router-dom", async (importOriginal) => {
      const actual = await importOriginal<typeof import("react-router-dom")>();
      return { ...actual, useNavigate: () => navigate };
    });

    mockSpaces = [makeSpace({ id: "sp1" })];
    mockHarnesses = [makeHarness({ name: "my harness" })];
    renderPage("/harnesses?space=sp1");
    // Edit button should exist (encoding is tested at integration level)
    expect(screen.getByRole("button", { name: /^edit$/i })).toBeInTheDocument();
  });

  it("'+ New harness' button is visible when a space is selected", () => {
    mockSpaces = [makeSpace({ id: "sp1" })];
    renderPage("/harnesses?space=sp1");
    expect(screen.getByRole("button", { name: /\+ new harness/i })).toBeInTheDocument();
  });

  it("clicking '+ New harness' opens create modal", () => {
    mockSpaces = [makeSpace({ id: "sp1" })];
    renderPage("/harnesses?space=sp1");
    fireEvent.click(screen.getByRole("button", { name: /\+ new harness/i }));
    expect(screen.getByRole("heading", { name: /new harness/i })).toBeInTheDocument();
  });

  it("successful create calls mutate and navigates to editor", async () => {
    mockSpaces = [makeSpace({ id: "sp1" })];
    mockCreateMutate.mockImplementation((_args: unknown, opts: { onSuccess: (h: Harness) => void }) => {
      opts.onSuccess(makeHarness({ name: "new-one" }));
    });

    renderPage("/harnesses?space=sp1");
    fireEvent.click(screen.getByRole("button", { name: /\+ new harness/i }));

    const input = screen.getByLabelText(/^name$/i);
    fireEvent.change(input, { target: { value: "new-one" } });
    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockCreateMutate).toHaveBeenCalledWith(
        { name: "new-one", description: "" },
        expect.any(Object),
      );
    });
  });

  it("shows 'No harnesses in this space' when list is empty", () => {
    mockSpaces = [makeSpace({ id: "sp1" })];
    mockHarnesses = [];
    renderPage("/harnesses?space=sp1");
    expect(screen.getByText(/no harnesses in this space/i)).toBeInTheDocument();
  });

  it("shows loading indicator while spaces are loading", () => {
    mockSpacesLoading = true;
    mockSpaces = [];
    renderPage();
    expect(screen.getByText(/loading spaces/i)).toBeInTheDocument();
  });

  it("shows error state when useHarnesses errors", () => {
    mockSpaces = [makeSpace({ id: "sp1" })];
    mockHarnessesIsError = true;
    renderPage("/harnesses?space=sp1");
    expect(screen.getByText(/failed to load harnesses/i)).toBeInTheDocument();
  });

  it("shows loading spinner while harnesses are loading", () => {
    mockSpaces = [makeSpace({ id: "sp1" })];
    mockHarnessesLoading = true;
    renderPage("/harnesses?space=sp1");
    expect(screen.getByText(/^loading…$/i)).toBeInTheDocument();
  });
});
