import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { FeatureRead } from "../../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockUseFeature = vi.fn();
const patchMutateAsync = vi.fn();
const processMutateAsync = vi.fn();
const setRealizeMutateAsync = vi.fn();

vi.mock("../../hooks/useFeatures", () => ({
  useFeature: (id: string | null) => mockUseFeature(id),
  usePatchFeature: () => ({
    mutateAsync: patchMutateAsync,
    isPending: false,
    error: null,
  }),
  useProcessFeature: () => ({
    mutateAsync: processMutateAsync,
    isPending: false,
    error: null,
  }),
  useSetRealize: () => ({
    mutateAsync: setRealizeMutateAsync,
    isPending: false,
  }),
}));

// ---------------------------------------------------------------------------
// Imports (after vi.mock)
// ---------------------------------------------------------------------------

import { FeatureDetail } from "../FeatureDetail";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeFeature(overrides: Partial<FeatureRead> = {}): FeatureRead {
  return {
    id: "feat-1",
    space_id: "space-1",
    title: "Dark mode support",
    state: "backlog",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    brief: "Support dark mode across the app.",
    priority: 3,
    manual_order: 0,
    type: "feature",
    parent_id: null,
    depends_on: [],
    pr_url: null,
    proposed_pr_path: null,
    feature_state: "backlog",
    feature_key: "FEAT-42",
    realizes: null,
    issue_number: null,
    issue_url: null,
    proposed_issue_path: null,
    waiting_question: null,
    realizing_items: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false, staleTime: Infinity } },
  });
}

function renderDetail(
  featureId = "feat-1",
  onClose = vi.fn(),
) {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <FeatureDetail featureId={featureId} onClose={onClose} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockUseFeature.mockReturnValue({ data: null, isLoading: false, error: null, refetch: vi.fn() });
  patchMutateAsync.mockClear().mockResolvedValue(undefined);
  processMutateAsync.mockClear().mockResolvedValue(undefined);
  setRealizeMutateAsync.mockClear().mockResolvedValue(undefined);
  window.confirm = vi.fn().mockReturnValue(true);
});

// ---------------------------------------------------------------------------
// 1. Loading and error states
// ---------------------------------------------------------------------------

describe("FeatureDetail — loading state", () => {
  it("renders a skeleton while loading", () => {
    mockUseFeature.mockReturnValue({ data: null, isLoading: true, error: null, refetch: vi.fn() });
    const { container } = renderDetail();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });
});

describe("FeatureDetail — error state", () => {
  it("renders the error message when useFeature returns an error", () => {
    mockUseFeature.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("Not found"),
      refetch: vi.fn(),
    });
    renderDetail();
    expect(screen.getByText("Not found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. Feature data rendering
// ---------------------------------------------------------------------------

describe("FeatureDetail — renders feature data", () => {
  it("renders the feature title", () => {
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    expect(screen.getByRole("heading", { name: "Dark mode support" })).toBeInTheDocument();
  });

  it("renders the feature_state badge", () => {
    mockUseFeature.mockReturnValue({
      data: makeFeature({ feature_state: "planned" }),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderDetail();
    expect(screen.getByText("planned")).toBeInTheDocument();
  });

  it("renders the feature type badge", () => {
    mockUseFeature.mockReturnValue({ data: makeFeature({ type: "fix" }), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    expect(screen.getByText("fix")).toBeInTheDocument();
  });

  it("renders the feature_key", () => {
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    expect(screen.getByText("FEAT-42")).toBeInTheDocument();
  });

  it("renders the brief content", () => {
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    expect(screen.getByText("Support dark mode across the app.")).toBeInTheDocument();
  });

  it("renders 'No brief yet' when brief is empty", () => {
    mockUseFeature.mockReturnValue({
      data: makeFeature({ brief: "" }),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderDetail();
    expect(screen.getByText("No brief yet.")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 3. waiting_question amber box
// ---------------------------------------------------------------------------

describe("FeatureDetail — waiting_question box", () => {
  it("renders the waiting_question amber box when present", () => {
    mockUseFeature.mockReturnValue({
      data: makeFeature({ waiting_question: "Which color scheme?" }),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderDetail();
    expect(screen.getByTestId("waiting-question-box")).toBeInTheDocument();
    expect(screen.getByText("Which color scheme?")).toBeInTheDocument();
  });

  it("does NOT render the waiting_question box when absent", () => {
    mockUseFeature.mockReturnValue({
      data: makeFeature({ waiting_question: null }),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderDetail();
    expect(screen.queryByTestId("waiting-question-box")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 4. Process button
// ---------------------------------------------------------------------------

describe("FeatureDetail — Process button", () => {
  it("renders a Start decomposition button", () => {
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    expect(screen.getByRole("button", { name: /start decomposition/i })).toBeInTheDocument();
  });

  it("Start decomposition button is disabled when feature_state is 'processing'", () => {
    mockUseFeature.mockReturnValue({
      data: makeFeature({ feature_state: "processing" }),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderDetail();
    expect(screen.getByRole("button", { name: /start decomposition/i })).toBeDisabled();
  });

  it("Start decomposition button calls processFeature.mutateAsync after confirm", async () => {
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /start decomposition/i }));
    expect(processMutateAsync).toHaveBeenCalledWith("feat-1");
  });

  it("Start decomposition button does NOT call mutateAsync when confirm is cancelled", async () => {
    (window.confirm as ReturnType<typeof vi.fn>).mockReturnValue(false);
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /start decomposition/i }));
    expect(processMutateAsync).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 5. Realizing items
// ---------------------------------------------------------------------------

describe("FeatureDetail — realizing_items", () => {
  const realizingItems = [
    {
      id: "goal-1",
      space_id: "space-1",
      title: "Implement dark mode UI",
      state: "active" as const,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      waiting_question: null,
      brief_preview: "",
      priority: 3,
      manual_order: 0,
      agent_mode: "auto" as const,
      space_name: null,
      space_color: null,
      space_icon: null,
    },
  ];

  it("renders realizing_items when present", () => {
    mockUseFeature.mockReturnValue({
      data: makeFeature({ realizing_items: realizingItems }),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderDetail();
    expect(screen.getByText("Implement dark mode UI")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /unlink implement dark mode ui/i })).toBeInTheDocument();
  });

  it("does NOT render realizing_items section when list is empty", () => {
    mockUseFeature.mockReturnValue({
      data: makeFeature({ realizing_items: [] }),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderDetail();
    expect(screen.queryByText(/Realizing Goals/i)).not.toBeInTheDocument();
  });

  it("Unlink button calls setRealize.mutateAsync with feature_id: null", async () => {
    mockUseFeature.mockReturnValue({
      data: makeFeature({ realizing_items: realizingItems }),
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderDetail();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /unlink implement dark mode ui/i }));
    expect(setRealizeMutateAsync).toHaveBeenCalledWith({
      featureId: "feat-1",
      body: { item_id: "goal-1", feature_id: null },
    });
  });
});

// ---------------------------------------------------------------------------
// 6. Inline edit
// ---------------------------------------------------------------------------

describe("FeatureDetail — inline edit", () => {
  it("clicking Edit shows the edit form", async () => {
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByRole("textbox", { name: "Title" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Brief" })).toBeInTheDocument();
  });

  it("Save calls patchFeature.mutateAsync with updated title and brief", async () => {
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const titleInput = screen.getByRole("textbox", { name: "Title" });
    await user.clear(titleInput);
    await user.type(titleInput, "Updated title");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(patchMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        featureId: "feat-1",
        body: expect.objectContaining({ title: "Updated title" }),
      }),
    );
  });

  it("Cancel hides the edit form without saving", async () => {
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByRole("textbox", { name: "Title" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("textbox", { name: "Title" })).not.toBeInTheDocument();
    expect(patchMutateAsync).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 7. Close behavior
// ---------------------------------------------------------------------------

describe("FeatureDetail — close behavior", () => {
  it("Close button calls onClose", async () => {
    const onClose = vi.fn();
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail("feat-1", onClose);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Esc key calls onClose when not editing", async () => {
    const onClose = vi.fn();
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail("feat-1", onClose);
    const user = userEvent.setup();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Esc key does NOT call onClose when edit form is open", async () => {
    const onClose = vi.fn();
    mockUseFeature.mockReturnValue({ data: makeFeature(), isLoading: false, error: null, refetch: vi.fn() });
    renderDetail("feat-1", onClose);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.keyboard("{Escape}");
    expect(onClose).not.toHaveBeenCalled();
  });
});
