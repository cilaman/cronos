import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { TreeToolbar } from "../TreeToolbar";

// ---------------------------------------------------------------------------
// Mocks — spaces endpoint stubbed so useSpaces() resolves locally.
// ---------------------------------------------------------------------------

vi.mock("../../api", () => ({
  api: {
    spaces: vi.fn(async () => ({
      spaces: [
        {
          id: "space-a",
          name: "Cronos",
          color: "#0F766E",
          icon: "🛰️",
          task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
          last_activity_at: null,
        },
        {
          id: "space-b",
          name: "Beta Space",
          color: "#4338CA",
          icon: null,
          task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
          last_activity_at: null,
        },
      ],
      totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
    })),
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderToolbar(props: Parameters<typeof TreeToolbar>[0]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TreeToolbar {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const defaultProps = {
  spaceId: null as string | null,
  onSpaceChange: () => {},
  sortMode: "manual" as const,
  onSortModeToggle: () => {},
  onExpandAll: () => {},
  onCollapseAll: () => {},
  boardLink: "/",
};

// ---------------------------------------------------------------------------
// Heading / title
// ---------------------------------------------------------------------------

describe("TreeToolbar — heading", () => {
  it("renders the generic 'Tree' heading when no space is active (spaceId is null)", () => {
    renderToolbar({ ...defaultProps });

    expect(screen.getByRole("heading", { level: 1, name: "Tree" })).toBeInTheDocument();
  });

  // Note: when spaceId is set, the active space comes from the useSpaces query
  // and renders asynchronously. We don't assert on the async-resolved name here
  // (covered by the BoardToolbar tests for the same pattern). Instead we assert
  // that the generic heading is NOT used until the lookup populates.
  it("does NOT render the generic 'Tree' heading when a spaceId is set", async () => {
    // When spaceId is set but useSpaces hasn't resolved yet, `active` is null
    // and the generic heading appears. After resolution, it's replaced by the
    // active space name. We assert on the post-resolution state.
    renderToolbar({ ...defaultProps, spaceId: "space-a" });

    // After react-query resolves with the mocked data, the space name shows.
    expect(await screen.findByRole("heading", { level: 1, name: "Cronos" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "Tree" })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Board view link
// ---------------------------------------------------------------------------

describe("TreeToolbar — Board view link", () => {
  it("renders a 'Board view' link with the href from the boardLink prop", () => {
    renderToolbar({ ...defaultProps, boardLink: "/spaces/space-a" });

    const link = screen.getByRole("link", { name: /Board view/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/spaces/space-a");
  });

  it("honors a root '/' boardLink for the all-spaces case", () => {
    renderToolbar({ ...defaultProps, boardLink: "/" });

    const link = screen.getByRole("link", { name: /Board view/i });
    expect(link).toHaveAttribute("href", "/");
  });
});

// ---------------------------------------------------------------------------
// Sort toggle
// ---------------------------------------------------------------------------

describe("TreeToolbar — sort toggle", () => {
  it("renders with 'Sort by priority' aria-label when sortMode is 'manual'", () => {
    renderToolbar({ ...defaultProps, sortMode: "manual" });

    const btn = screen.getByRole("button", { name: /Sort by priority/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("title", "Sort by priority");
  });

  it("renders with 'Switch to manual order' aria-label when sortMode is 'priority'", () => {
    renderToolbar({ ...defaultProps, sortMode: "priority" });

    const btn = screen.getByRole("button", { name: /Switch to manual order/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("title", "Manual order");
  });

  it("calls onSortModeToggle when the sort button is clicked", async () => {
    const onSortModeToggle = vi.fn();
    renderToolbar({ ...defaultProps, sortMode: "manual", onSortModeToggle });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /Sort by priority/i }));

    expect(onSortModeToggle).toHaveBeenCalledTimes(1);
  });

  it("calls onSortModeToggle from the priority-active state as well", async () => {
    const onSortModeToggle = vi.fn();
    renderToolbar({ ...defaultProps, sortMode: "priority", onSortModeToggle });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /Switch to manual order/i }));

    expect(onSortModeToggle).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Expand / collapse buttons
// ---------------------------------------------------------------------------

describe("TreeToolbar — expand/collapse buttons", () => {
  it("renders both 'Expand all' and 'Collapse all' buttons", () => {
    renderToolbar({ ...defaultProps });

    expect(screen.getByRole("button", { name: /Expand all/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Collapse all/i })).toBeInTheDocument();
  });

  it("calls onExpandAll exactly once when the Expand all button is clicked", async () => {
    const onExpandAll = vi.fn();
    renderToolbar({ ...defaultProps, onExpandAll });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /Expand all/i }));

    expect(onExpandAll).toHaveBeenCalledTimes(1);
  });

  it("calls onCollapseAll exactly once when the Collapse all button is clicked", async () => {
    const onCollapseAll = vi.fn();
    renderToolbar({ ...defaultProps, onCollapseAll });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /Collapse all/i }));

    expect(onCollapseAll).toHaveBeenCalledTimes(1);
  });

  it("does NOT call onCollapseAll when only Expand all is clicked", async () => {
    const onExpandAll = vi.fn();
    const onCollapseAll = vi.fn();
    renderToolbar({ ...defaultProps, onExpandAll, onCollapseAll });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /Expand all/i }));

    expect(onExpandAll).toHaveBeenCalledTimes(1);
    expect(onCollapseAll).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Filter locked
// ---------------------------------------------------------------------------

describe("TreeToolbar — filter locked", () => {
  beforeEach(() => {
    // Each test gets a fresh render — nothing global to reset.
  });

  it("disables the SpaceFilterDropdown button when filterLocked is true", () => {
    renderToolbar({ ...defaultProps, filterLocked: true });

    // SpaceFilterDropdown renders a <button> whose title is the disabled
    // tooltip when disabled is true.
    const disabledBtn = screen.getByTitle("Filter locked to this space");
    expect(disabledBtn).toBeDisabled();
  });

  it("does NOT disable the SpaceFilterDropdown button when filterLocked is false (default)", () => {
    renderToolbar({ ...defaultProps });

    // The disabled-tooltip title should not be set.
    expect(screen.queryByTitle("Filter locked to this space")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tree / DAG view toggle
// ---------------------------------------------------------------------------

describe("TreeToolbar — Tree/DAG view toggle", () => {
  it("does NOT render the Tree/DAG toggle when onViewModeToggle is not provided", () => {
    renderToolbar({ ...defaultProps });

    expect(screen.queryByRole("button", { name: "Tree view" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "DAG view" })).not.toBeInTheDocument();
  });

  it("renders Tree and DAG buttons when onViewModeToggle is provided", () => {
    renderToolbar({
      ...defaultProps,
      viewMode: "tree",
      onViewModeToggle: vi.fn(),
    });

    expect(screen.getByRole("button", { name: "Tree view" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "DAG view" })).toBeInTheDocument();
  });

  it("Tree button has aria-pressed=true when viewMode is 'tree'", () => {
    renderToolbar({
      ...defaultProps,
      viewMode: "tree",
      onViewModeToggle: vi.fn(),
    });

    expect(screen.getByRole("button", { name: "Tree view" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "DAG view" })).toHaveAttribute("aria-pressed", "false");
  });

  it("DAG button has aria-pressed=true when viewMode is 'dag'", () => {
    renderToolbar({
      ...defaultProps,
      viewMode: "dag",
      onViewModeToggle: vi.fn(),
    });

    expect(screen.getByRole("button", { name: "DAG view" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Tree view" })).toHaveAttribute("aria-pressed", "false");
  });

  it("clicking DAG button calls onViewModeToggle when viewMode is 'tree'", async () => {
    const onViewModeToggle = vi.fn();
    renderToolbar({
      ...defaultProps,
      viewMode: "tree",
      onViewModeToggle,
    });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "DAG view" }));

    expect(onViewModeToggle).toHaveBeenCalledTimes(1);
  });

  it("clicking Tree button calls onViewModeToggle when viewMode is 'dag'", async () => {
    const onViewModeToggle = vi.fn();
    renderToolbar({
      ...defaultProps,
      viewMode: "dag",
      onViewModeToggle,
    });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Tree view" }));

    expect(onViewModeToggle).toHaveBeenCalledTimes(1);
  });

  it("clicking Tree button when already in tree mode does NOT call onViewModeToggle", async () => {
    const onViewModeToggle = vi.fn();
    renderToolbar({
      ...defaultProps,
      viewMode: "tree",
      onViewModeToggle,
    });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Tree view" }));

    expect(onViewModeToggle).not.toHaveBeenCalled();
  });
});
