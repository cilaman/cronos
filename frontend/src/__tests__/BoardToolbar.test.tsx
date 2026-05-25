import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { BoardToolbar } from "../components/BoardToolbar";
import type { View } from "../types";

// Mock the API module so useSpaces() resolves without real network calls.
// `spaceViews` is consumed by useViews() inside <ViewPicker>; it must
// resolve to an array (the picker assumes a list).
vi.mock("../api", () => ({
  api: {
    spaces: vi.fn(async () => ({
      spaces: [
        {
          id: "space-1",
          name: "Space One",
          color: "#15803D",
          icon: null,
          task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
          last_activity_at: null,
        },
      ],
      totals: {
        backlog: 0,
        active: 0,
        waiting: 0,
        done: 0,
        archived: 0,
      },
    })),
    spaceViews: vi.fn(async (): Promise<View[]> => []),
  },
}));

function renderToolbar(props: Parameters<typeof BoardToolbar>[0]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BoardToolbar {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const defaultProps = {
  spaceId: null,
  onSpaceChange: () => {},
  onNewTask: () => {},
  sortMode: "manual" as const,
  onSortModeToggle: () => {},
};

describe("BoardToolbar — compact toggle", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders the toggle button when compact is false with 'Switch to minimal cards' aria-label", () => {
    renderToolbar({
      ...defaultProps,
      compact: false,
      onCompactToggle: () => {},
    });
    const btn = screen.getByRole("button", {
      name: /Switch to minimal cards/i,
    });
    expect(btn).toBeInTheDocument();
  });

  it("renders the toggle button when compact is true with 'Switch to full cards' aria-label", () => {
    renderToolbar({
      ...defaultProps,
      compact: true,
      onCompactToggle: () => {},
    });
    const btn = screen.getByRole("button", {
      name: /Switch to full cards/i,
    });
    expect(btn).toBeInTheDocument();
  });

  it("uses 'Full cards' title when compact is true", () => {
    renderToolbar({
      ...defaultProps,
      compact: true,
      onCompactToggle: () => {},
    });
    const btn = screen.getByRole("button", {
      name: /Switch to full cards/i,
    });
    expect(btn).toHaveAttribute("title", "Full cards");
  });

  it("uses 'Minimal cards' title when compact is false", () => {
    renderToolbar({
      ...defaultProps,
      compact: false,
      onCompactToggle: () => {},
    });
    const btn = screen.getByRole("button", {
      name: /Switch to minimal cards/i,
    });
    expect(btn).toHaveAttribute("title", "Minimal cards");
  });

  it("invokes onCompactToggle when the toggle is clicked", async () => {
    const onCompactToggle = vi.fn();
    renderToolbar({
      ...defaultProps,
      compact: false,
      onCompactToggle,
    });
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /Switch to minimal cards/i }),
    );
    expect(onCompactToggle).toHaveBeenCalledTimes(1);
  });

  it("invokes onCompactToggle when clicked from compact state", async () => {
    const onCompactToggle = vi.fn();
    renderToolbar({
      ...defaultProps,
      compact: true,
      onCompactToggle,
    });
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /Switch to full cards/i }),
    );
    expect(onCompactToggle).toHaveBeenCalledTimes(1);
  });

  it("renders the New task button alongside the toggle", () => {
    renderToolbar({
      ...defaultProps,
      compact: false,
      onCompactToggle: () => {},
    });
    expect(
      screen.getByRole("button", { name: /New task/i }),
    ).toBeInTheDocument();
  });
});

describe("BoardToolbar — ViewPicker slot", () => {
  // ViewPicker renders a button labelled "Views" while its useViews() query
  // is still loading. Once views resolve, the label switches to the active
  // view name. We assert against both states.
  const propsWithSpace = {
    ...defaultProps,
    spaceId: "space-1",
    compact: false,
    onCompactToggle: () => {},
  };

  it("renders ViewPicker when spaceId and onViewChange are both provided", async () => {
    renderToolbar({
      ...propsWithSpace,
      onViewChange: vi.fn(),
    });

    // Loading state: the picker shows the "Views" placeholder.
    expect(
      await screen.findByRole("button", { name: /Views/i }),
    ).toBeInTheDocument();
  });

  it("does NOT render ViewPicker when onViewChange is omitted (unscoped board)", async () => {
    renderToolbar({
      ...propsWithSpace,
      // no onViewChange — typical of /board (all spaces) where the URL
      // doesn't carry a view filter.
    });

    // Allow other effects to flush so we don't false-pass on a not-yet-mounted node.
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /New task/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /^Views$/i })).not.toBeInTheDocument();
  });

  it("does NOT render ViewPicker when spaceId is null even if onViewChange is provided", async () => {
    renderToolbar({
      ...defaultProps,
      spaceId: null,
      compact: false,
      onCompactToggle: () => {},
      onViewChange: vi.fn(),
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /New task/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /^Views$/i })).not.toBeInTheDocument();
  });

  it("invokes onViewChange when a view is selected from the picker", async () => {
    // Override the mock for this test so views resolve with sample data.
    const { api } = await import("../api");
    const sample: View[] = [
      {
        id: "all",
        name: "All lanes",
        lanes: ["backlog", "active", "waiting", "done"],
        type_filter: null,
        default: true,
        created_at: "2026-05-25T00:00:00Z",
        updated_at: "2026-05-25T00:00:00Z",
      },
      {
        id: "focus",
        name: "Focus",
        lanes: ["active", "waiting"],
        type_filter: null,
        default: false,
        created_at: "2026-05-25T00:00:00Z",
        updated_at: "2026-05-25T00:00:00Z",
      },
    ];
    (api.spaceViews as ReturnType<typeof vi.fn>).mockResolvedValueOnce(sample);

    const onViewChange = vi.fn();
    renderToolbar({ ...propsWithSpace, onViewChange });

    // Wait for views to resolve — trigger label switches to "All lanes".
    const trigger = await screen.findByRole("button", { name: /All lanes/i });
    const user = userEvent.setup();
    await user.click(trigger);
    await user.click(screen.getByText("Focus"));

    expect(onViewChange).toHaveBeenCalledTimes(1);
    expect(onViewChange).toHaveBeenCalledWith("focus");
  });
});
