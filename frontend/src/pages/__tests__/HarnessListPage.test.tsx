import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { Harness } from "../../types";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

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

// Import component AFTER vi.mock
import { HarnessListPage } from "../HarnessListPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function renderPage(spaceId = "space-1") {
  const path = `/spaces/${spaceId}/harnesses`;
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/spaces/:spaceId/harnesses" element={<HarnessListPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HarnessListPage", () => {
  beforeEach(() => {
    mockHarnesses = [];
    mockHarnessesLoading = false;
    mockHarnessesIsError = false;
    mockHarnessesError = null;
    mockCreateMutate.mockReset();
    mockCreateIsPending = false;
    mockDeleteMutate.mockReset();
    mockDeleteIsPending = false;
  });

  it("renders h1 with class text-title and title 'Harnesses'", () => {
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1, name: /harnesses/i });
    expect(h1).toBeInTheDocument();
    expect(h1.className).toContain("text-title");
  });

  it("h1 does not carry ad-hoc size classes (text-lg, text-sm, text-[22px])", () => {
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.className).not.toContain("text-lg");
    expect(h1.className).not.toContain("text-sm");
    expect(h1.className).not.toContain("text-[22px]");
    expect(h1.className).not.toContain("uppercase");
    expect(h1.className).not.toContain("tracking-[");
  });

  it("wraps content in PageContainer (max-w-[1280px])", () => {
    const { container } = renderPage();
    const wrapper = container.querySelector(".max-w-\\[1280px\\]");
    expect(wrapper).not.toBeNull();
  });

  it("renders subtitle text about automation workflows", () => {
    renderPage();
    expect(screen.getByText(/automation workflows/i)).toBeInTheDocument();
  });

  it("shows '+ New harness' button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /\+ new harness/i })).toBeInTheDocument();
  });

  it("shows loading indicator while harnesses are loading", () => {
    mockHarnessesLoading = true;
    renderPage();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows error banner when useHarnesses errors", () => {
    mockHarnessesIsError = true;
    mockHarnessesError = new Error("Network error");
    renderPage();
    expect(screen.getByText(/failed to load harnesses/i)).toBeInTheDocument();
  });

  it("shows empty state when harness list is empty", () => {
    mockHarnesses = [];
    renderPage();
    expect(screen.getByText(/no harnesses yet/i)).toBeInTheDocument();
  });

  it("renders a HarnessCard for each harness", () => {
    mockHarnesses = [
      makeHarness({ name: "harness-alpha" }),
      makeHarness({ name: "harness-beta" }),
    ];
    renderPage();
    expect(screen.getByText("harness-alpha")).toBeInTheDocument();
    expect(screen.getByText("harness-beta")).toBeInTheDocument();
  });

  it("clicking '+ New harness' opens create modal", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /\+ new harness/i }));
    expect(screen.getByRole("heading", { name: /new harness/i })).toBeInTheDocument();
  });

  it("create modal calls mutate on form submit", async () => {
    mockCreateMutate.mockImplementation(
      (_args: unknown, opts: { onSuccess: (h: Harness) => void }) => {
        opts.onSuccess(makeHarness({ name: "new-harness" }));
      },
    );
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /\+ new harness/i }));
    const nameInput = screen.getByLabelText(/^name$/i);
    fireEvent.change(nameInput, { target: { value: "new-harness" } });
    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));
    await waitFor(() => {
      expect(mockCreateMutate).toHaveBeenCalledWith(
        { name: "new-harness", description: "" },
        expect.any(Object),
      );
    });
  });

  it("harness card shows Edit and Runs buttons", () => {
    mockHarnesses = [makeHarness({ name: "my-harness" })];
    renderPage();
    expect(screen.getByRole("button", { name: /^edit$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^runs$/i })).toBeInTheDocument();
  });

  it("clicking delete icon opens confirm dialog", () => {
    mockHarnesses = [makeHarness({ name: "to-delete" })];
    renderPage();
    const deleteBtn = screen.getByRole("button", { name: /delete to-delete/i });
    fireEvent.click(deleteBtn);
    expect(screen.getByText(/delete harness\?/i)).toBeInTheDocument();
  });

  it("confirm delete calls deleteHarness.mutate", () => {
    mockHarnesses = [makeHarness({ name: "to-delete" })];
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /delete to-delete/i }));
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    expect(mockDeleteMutate).toHaveBeenCalledWith("to-delete", expect.any(Object));
  });
});
