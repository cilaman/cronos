import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { View } from "../../types";

// ---------------------------------------------------------------------------
// Mock the api so useViews can resolve without a real HTTP layer
// ---------------------------------------------------------------------------
const spaceViewsMock = vi.fn();
vi.mock("../../api", () => ({
  api: {
    spaceViews: (spaceId: string) => spaceViewsMock(spaceId),
  },
}));

// Import AFTER vi.mock so mocks apply.
import { ViewPicker } from "../ViewPicker";

const FOCUS_RING_CLASSES = [
  "focus:outline-none",
  "focus-visible:ring-1",
  "focus-visible:ring-accent",
];

const SAMPLE_VIEWS: View[] = [
  {
    id: "all",
    name: "All lanes",
    lanes: ["backlog", "active", "waiting", "done"],
    type_filter: null,
    default: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "focus",
    name: "Focus",
    lanes: ["active", "waiting"],
    type_filter: null,
    default: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

function renderPicker(
  partial: Partial<React.ComponentProps<typeof ViewPicker>> = {},
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
  return render(
    <QueryClientProvider client={queryClient}>
      <ViewPicker {...props} />
    </QueryClientProvider>,
  );
}

describe("ViewPicker buttons — trigger", () => {
  beforeEach(() => {
    spaceViewsMock.mockReset();
    spaceViewsMock.mockResolvedValue(SAMPLE_VIEWS);
  });

  it("renders a <button> element as the trigger (not a div with role=button)", async () => {
    renderPicker();
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    expect(screen.getByRole("button").tagName).toBe("BUTTON");
  });

  it("trigger carries all three focus-ring classes", async () => {
    renderPicker();
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    const trigger = screen.getByRole("button");
    for (const cls of FOCUS_RING_CLASSES) {
      expect(trigger.className).toContain(cls);
    }
  });

  it("trigger shows 'Views' when no views are loaded yet", () => {
    spaceViewsMock.mockReturnValue(new Promise(() => {}));
    renderPicker();
    expect(screen.getByRole("button")).toHaveTextContent("Views");
  });

  it("trigger opens dropdown when clicked", async () => {
    renderPicker();
    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));
    // Dropdown is open: multiple buttons visible
    await waitFor(() => {
      expect(screen.getAllByRole("button").length).toBeGreaterThan(1);
    });
  });
});

describe("ViewPicker buttons — dropdown items", () => {
  beforeEach(() => {
    spaceViewsMock.mockReset();
    spaceViewsMock.mockResolvedValue(SAMPLE_VIEWS);
  });

  it("dropdown items are <button> elements", async () => {
    renderPicker();
    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getAllByRole("button").length).toBeGreaterThan(1);
    });

    const allButtons = screen.getAllByRole("button");
    for (const btn of allButtons) {
      expect(btn.tagName).toBe("BUTTON");
    }
  });

  it("all buttons (trigger + dropdown items + manage views) carry focus-ring classes", async () => {
    renderPicker();
    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      // Trigger + 2 view items + Manage views = 4 buttons
      expect(screen.getAllByRole("button").length).toBeGreaterThanOrEqual(4);
    });

    const allButtons = screen.getAllByRole("button");
    for (const btn of allButtons) {
      for (const cls of FOCUS_RING_CLASSES) {
        expect(btn.className).toContain(cls);
      }
    }
  });

  it("'Manage views…' is a <button> element with focus ring", async () => {
    renderPicker();
    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByText(/Manage views…/i)).toBeInTheDocument();
    });

    const manageBtn = screen.getAllByRole("button").find(
      (b) => b.textContent?.includes("Manage views"),
    );
    expect(manageBtn).toBeDefined();
    expect(manageBtn!.tagName).toBe("BUTTON");
    for (const cls of FOCUS_RING_CLASSES) {
      expect(manageBtn!.className).toContain(cls);
    }
  });

  it("clicking a view item calls onChange", async () => {
    const onChange = vi.fn();
    renderPicker({ viewId: null, onChange });
    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getAllByRole("button").length).toBeGreaterThan(1);
    });

    // Click "Focus" (non-default view)
    const focusBtn = screen
      .getAllByRole("button")
      .find((b) => b.textContent?.includes("Focus"));
    expect(focusBtn).toBeDefined();
    await user.click(focusBtn!);

    expect(onChange).toHaveBeenCalledWith("focus");
  });

  it("clicking 'Manage views…' calls onManageViews", async () => {
    const onManageViews = vi.fn();
    renderPicker({ onManageViews });
    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("All lanes");
    });
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByText(/Manage views…/i)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/Manage views…/i));
    expect(onManageViews).toHaveBeenCalledTimes(1);
  });
});
