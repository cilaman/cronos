/**
 * HarnessListPage.test.tsx
 *
 * Tests for I8 — three behaviors:
 *   1. CreateHarnessModal: opens, dismisses on Escape, dismisses on scrim click
 *   2. Delete-confirm modal: opens, dismisses on Escape
 *   3. Loading state: shows Skeleton cards, not a spinner
 *   4. Harnesses render when loaded
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { HarnessListPage } from "./HarnessListPage";
import type { Harness } from "../types";

// ── Module mocks ──────────────────────────────────────────────────────────────

vi.mock("../hooks/useHarnesses", () => ({
  useHarnesses: vi.fn(),
  useCreateHarness: vi.fn(),
  useDeleteHarness: vi.fn(),
}));

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: vi.fn(() => vi.fn()),
    useParams: vi.fn(() => ({ spaceId: "space-1" })),
  };
});

import { useHarnesses, useCreateHarness, useDeleteHarness } from "../hooks/useHarnesses";

// ── Fixture helpers ───────────────────────────────────────────────────────────

const SAMPLE_HARNESSES: Harness[] = [
  {
    name: "ci-pipeline",
    description: "Runs CI tests",
    nodes: [],
    edges: [],
    variables: {},
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-02T00:00:00Z",
  },
  {
    name: "deploy-prod",
    description: "Deploy to production",
    nodes: [],
    edges: [],
    variables: {},
    created_at: "2024-01-03T00:00:00Z",
    updated_at: "2024-01-04T00:00:00Z",
  },
];

function makeUseHarnesses(overrides: Partial<ReturnType<typeof useHarnesses>>) {
  return {
    data: undefined,
    isLoading: false,
    error: null,
    ...overrides,
  };
}

function makeUseMutation(overrides: Record<string, unknown> = {}) {
  return {
    mutate: vi.fn(),
    isPending: false,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <HarnessListPage />
    </MemoryRouter>,
  );
}

// ── Setup defaults ────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.mocked(useHarnesses).mockReturnValue(
    makeUseHarnesses({ data: SAMPLE_HARNESSES }) as ReturnType<typeof useHarnesses>,
  );
  vi.mocked(useCreateHarness).mockReturnValue(makeUseMutation() as unknown as ReturnType<typeof useCreateHarness>);
  vi.mocked(useDeleteHarness).mockReturnValue(makeUseMutation() as unknown as ReturnType<typeof useDeleteHarness>);
});

// ── 1. Loading state: shows Skeleton cards, not a spinner ─────────────────────

describe("HarnessListPage — loading state", () => {
  it("shows Skeleton cards (not a spinner) while loading", () => {
    vi.mocked(useHarnesses).mockReturnValue(
      makeUseHarnesses({ isLoading: true, data: undefined }) as ReturnType<typeof useHarnesses>,
    );
    renderPage();

    // Should have multiple Skeleton role=status elements
    const skeletons = screen.getAllByRole("status", { name: "Loading" });
    expect(skeletons.length).toBeGreaterThanOrEqual(3);

    // Should NOT have an animate-spin spinner
    const { container } = render(
      <MemoryRouter>
        <HarnessListPage />
      </MemoryRouter>,
    );
    const spinners = container.querySelectorAll(".animate-spin");
    expect(spinners).toHaveLength(0);
  });
});

// ── 2. Harnesses render when loaded ──────────────────────────────────────────

describe("HarnessListPage — harnesses loaded", () => {
  it("renders harness cards when data is available", () => {
    renderPage();
    expect(screen.getByText("ci-pipeline")).toBeInTheDocument();
    expect(screen.getByText("deploy-prod")).toBeInTheDocument();
  });

  it("shows the page heading", () => {
    renderPage();
    expect(screen.getByText("Harnesses")).toBeInTheDocument();
  });

  it("does not show a spinner when loaded", () => {
    const { container } = renderPage();
    expect(container.querySelector(".animate-spin")).toBeNull();
  });
});

// ── 3. CreateHarnessModal: Escape dismisses ───────────────────────────────────

describe("HarnessListPage — CreateHarnessModal — Escape key dismisses", () => {
  it("opens the create modal when '+ New harness' is clicked", async () => {
    renderPage();
    await userEvent.click(screen.getByText("+ New harness"));
    expect(screen.getByText("New Harness")).toBeInTheDocument();
  });

  it("dismisses CreateHarnessModal on Escape key", async () => {
    renderPage();
    await userEvent.click(screen.getByText("+ New harness"));
    expect(screen.getByText("New Harness")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByText("New Harness")).not.toBeInTheDocument();
  });
});

// ── 4. CreateHarnessModal: scrim click dismisses ──────────────────────────────

describe("HarnessListPage — CreateHarnessModal — scrim click dismisses", () => {
  it("dismisses CreateHarnessModal on scrim (backdrop) click", async () => {
    renderPage();
    await userEvent.click(screen.getByText("+ New harness"));
    expect(screen.getByText("New Harness")).toBeInTheDocument();

    // Click the scrim (modal backdrop)
    await userEvent.click(screen.getByTestId("modal-scrim"));
    expect(screen.queryByText("New Harness")).not.toBeInTheDocument();
  });
});

// ── 5. Delete-confirm modal: Escape dismisses ─────────────────────────────────

describe("HarnessListPage — delete-confirm modal — Escape key dismisses", () => {
  it("opens delete-confirm modal when delete button is clicked", async () => {
    renderPage();
    const deleteBtn = screen.getByLabelText("Delete ci-pipeline");
    await userEvent.click(deleteBtn);
    expect(screen.getByText("Delete harness?")).toBeInTheDocument();
  });

  it("dismisses delete-confirm modal on Escape key", async () => {
    renderPage();
    const deleteBtn = screen.getByLabelText("Delete ci-pipeline");
    await userEvent.click(deleteBtn);
    expect(screen.getByText("Delete harness?")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByText("Delete harness?")).not.toBeInTheDocument();
  });
});
