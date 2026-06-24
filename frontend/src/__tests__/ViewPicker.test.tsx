import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { View } from "../types";

// Mock the api module — useViews() calls api.spaceViews(spaceId).
const spaceViewsMock = vi.fn();
vi.mock("../api", () => ({
  api: {
    spaceViews: (spaceId: string) => spaceViewsMock(spaceId),
  },
}));

// Import after vi.mock so the mocks apply.
import { ViewPicker } from "../components/ViewPicker";

const SAMPLE_VIEWS: View[] = [
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
  {
    id: "backlog-only",
    name: "Backlog only",
    lanes: ["backlog"],
    type_filter: ["task"],
    default: false,
    created_at: "2026-05-25T00:00:00Z",
    updated_at: "2026-05-25T00:00:00Z",
  },
];

function renderPicker(
  partial: Partial<Parameters<typeof ViewPicker>[0]> = {},
) {
  const props = {
    spaceId: "space-1",
    viewId: null,
    onChange: vi.fn(),
    onManageViews: vi.fn(),
    ...partial,
  };
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
    },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <ViewPicker {...props} />
    </QueryClientProvider>,
  );
  return { ...utils, props };
}

describe("ViewPicker", () => {
  beforeEach(() => {
    spaceViewsMock.mockReset();
    spaceViewsMock.mockResolvedValue(SAMPLE_VIEWS);
  });

  it("renders the default view name when viewId is null", async () => {
    renderPicker({ viewId: null });

    // Wait for the views query to resolve before asserting the trigger label.
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
  });

  it("renders the matching view name when viewId is set", async () => {
    renderPicker({ viewId: "focus" });

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("Focus");
    });
  });

  it("falls back to the default view when viewId is unknown", async () => {
    // Bookmarked/stale view id that no longer exists — picker should still
    // show *something* sensible (the default), not crash or render blank.
    renderPicker({ viewId: "does-not-exist" });

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
  });

  it("renders 'Views' placeholder while the query is loading (no data yet)", () => {
    // Return a promise that never resolves so the query stays in loading state.
    spaceViewsMock.mockReturnValue(new Promise(() => {}));

    renderPicker();

    expect(screen.getByRole("button")).toHaveTextContent("Views");
  });

  it("opens the dropdown when the trigger is clicked", async () => {
    renderPicker();
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });

    // Act
    await user.click(screen.getByRole("button"));

    // Every view name should appear inside the dropdown menu now.
    for (const v of SAMPLE_VIEWS) {
      expect(screen.getAllByText(v.name).length).toBeGreaterThanOrEqual(1);
    }
  });

  it("calls onChange with view.id when a non-default view item is clicked", async () => {
    const onChange = vi.fn();
    renderPicker({ viewId: null, onChange });
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));

    // Act — click "Focus" (non-default)
    await user.click(screen.getByText("Focus"));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("focus");
  });

  it("calls onChange with null when the default view item is clicked", async () => {
    // Clean URL semantics: selecting the default view should clear the
    // ?view= param, not set ?view=<default-id>.
    const onChange = vi.fn();
    renderPicker({ viewId: "focus", onChange });
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("Focus");
    });
    await user.click(screen.getByRole("button"));

    // Act — click "All lanes" (default=true)
    await user.click(screen.getByText("All lanes"));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("closes the dropdown after selecting a view", async () => {
    const onChange = vi.fn();
    renderPicker({ onChange });
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));

    // The "Manage views…" footer button is unique and only visible while open.
    expect(screen.getByText(/Manage views…/i)).toBeInTheDocument();

    // Act
    await user.click(screen.getByText("Focus"));

    // The footer should be gone now.
    expect(screen.queryByText(/Manage views…/i)).not.toBeInTheDocument();
  });

  it("renders a star icon next to the default view in the dropdown", async () => {
    // Activate "Focus" so the default row ("All lanes") is NOT the active
    // row. That isolates "default star" from "active check": the default
    // row gets exactly one svg (the star) and the third row (inactive,
    // non-default) gets zero svgs.
    renderPicker({ viewId: "focus" });
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("Focus");
    });
    await user.click(screen.getByRole("button"));

    const allLanesBtn = screen
      .getAllByRole("button")
      .find((b) => b.textContent === "All lanes");
    const backlogOnlyBtn = screen
      .getAllByRole("button")
      .find((b) => b.textContent === "Backlog only");

    expect(allLanesBtn).toBeDefined();
    expect(backlogOnlyBtn).toBeDefined();
    // Default row has 1 svg (the star). The inactive, non-default row
    // ("Backlog only") has 0 svgs (no star, no check).
    expect(allLanesBtn!.querySelectorAll("svg").length).toBe(1);
    expect(backlogOnlyBtn!.querySelectorAll("svg").length).toBe(0);
  });

  it("renders a star icon in the trigger when the active view is the default", async () => {
    renderPicker({ viewId: null });

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });

    // Trigger button has the chevron svg + (when default) the star svg.
    // When the active view is non-default, only the chevron is present.
    const trigger = screen.getByRole("button");
    expect(trigger.querySelectorAll("svg").length).toBe(1);
  });

  it("does NOT render a star icon in the trigger when the active view is non-default", async () => {
    renderPicker({ viewId: "focus" });

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("Focus");
    });

    const trigger = screen.getByRole("button");
    // Only the chevron svg should be present (no star).
    expect(trigger.querySelectorAll("svg").length).toBe(0);
  });

  it("renders a check icon next to the active view in the dropdown", async () => {
    renderPicker({ viewId: "focus" });
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("Focus");
    });
    await user.click(screen.getByRole("button"));

    const focusItem = screen
      .getAllByRole("button")
      .find((b) => b.textContent === "Focus");
    // Active row gets a check svg (no star because Focus is not default).
    expect(focusItem!.querySelectorAll("svg").length).toBe(1);
  });

  it("calls onManageViews and closes the dropdown when 'Manage views…' is clicked", async () => {
    const onManageViews = vi.fn();
    renderPicker({ onManageViews });
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));

    // Act
    await user.click(screen.getByText(/Manage views…/i));

    expect(onManageViews).toHaveBeenCalledTimes(1);
    // Dropdown closed → footer gone.
    expect(screen.queryByText(/Manage views…/i)).not.toBeInTheDocument();
  });

  it("calls api.spaceViews with the provided spaceId", async () => {
    renderPicker({ spaceId: "my-space" });

    await waitFor(() => {
      expect(spaceViewsMock).toHaveBeenCalledWith("my-space");
    });
  });

  it("closes the dropdown when Escape is pressed", async () => {
    renderPicker();
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));
    expect(screen.getByText(/Manage views…/i)).toBeInTheDocument();

    // Act
    await user.keyboard("{Escape}");

    expect(screen.queryByText(/Manage views…/i)).not.toBeInTheDocument();
  });

  it("closes the dropdown when clicking outside the picker", async () => {
    const onChange = vi.fn();
    const { container } = renderPicker({ onChange });
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));
    expect(screen.getByText(/Manage views…/i)).toBeInTheDocument();

    // Act — click document.body, which is outside the picker's ref subtree.
    // userEvent.click(document.body) does not synthesize the mousedown
    // event the picker listens to, so dispatch one directly.
    const md = new MouseEvent("mousedown", { bubbles: true });
    document.body.dispatchEvent(md);

    // Re-query after the state update propagates.
    await waitFor(() => {
      expect(screen.queryByText(/Manage views…/i)).not.toBeInTheDocument();
    });
    // Sanity: the outside-click handler should not invoke onChange.
    expect(onChange).not.toHaveBeenCalled();
    // container is still mounted.
    expect(container).toBeInTheDocument();
  });

  it("does not call onManageViews when the dropdown is opened then closed without clicking 'Manage views…'", async () => {
    const onManageViews = vi.fn();
    renderPicker({ onManageViews });
    const user = userEvent.setup();

    // Find the trigger by its text BEFORE opening (when it's the only
    // button on screen) and hold onto the reference for the toggle click
    // — once open there are multiple buttons in the DOM.
    const trigger = await screen.findByRole("button", { name: /All lanes/i });

    await user.click(trigger); // open
    expect(screen.getByText(/Manage views…/i)).toBeInTheDocument();
    await user.click(trigger); // close (toggle)

    expect(screen.queryByText(/Manage views…/i)).not.toBeInTheDocument();
    expect(onManageViews).not.toHaveBeenCalled();
  });

  it("tolerates an empty views list without crashing the trigger", async () => {
    spaceViewsMock.mockResolvedValueOnce([]);
    renderPicker();

    // When views resolve to [], the trigger should still render the
    // "Views" placeholder (resolvedView is null).
    await waitFor(() => {
      expect(spaceViewsMock).toHaveBeenCalled();
    });
    expect(screen.getByRole("button")).toHaveTextContent("Views");
  });
});
