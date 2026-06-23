import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Mock the api so useSpaces can resolve without a real HTTP layer
// ---------------------------------------------------------------------------
const spacesMock = vi.fn();
vi.mock("../../api", () => ({
  api: {
    spaces: () => spacesMock(),
  },
}));

// Import AFTER vi.mock so mocks apply.
import { SpaceFilterDropdown } from "../SpaceFilterDropdown";

const FOCUS_RING_CLASSES = [
  "focus:outline-none",
  "focus-visible:ring-1",
  "focus-visible:ring-accent",
];

const SAMPLE_SPACES = [
  {
    id: "s1",
    name: "Backend",
    color: "#0F766E",
    icon: null,
    description: "",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "s2",
    name: "Frontend",
    color: "#9333EA",
    icon: "⚛️",
    description: "",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

function renderDropdown(
  partial: Partial<React.ComponentProps<typeof SpaceFilterDropdown>> = {},
) {
  const props = {
    value: null,
    onChange: vi.fn(),
    ...partial,
  };
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SpaceFilterDropdown {...props} />
    </QueryClientProvider>,
  );
}

describe("SpaceFilterDropdown buttons — trigger", () => {
  beforeEach(() => {
    spacesMock.mockReset();
    spacesMock.mockResolvedValue({ spaces: SAMPLE_SPACES });
  });

  it("renders a <button> element as the trigger (not a div with role=button)", () => {
    renderDropdown();
    const trigger = screen.getByRole("button");
    expect(trigger.tagName).toBe("BUTTON");
  });

  it("trigger carries all three focus-ring classes", () => {
    renderDropdown();
    const trigger = screen.getByRole("button");
    for (const cls of FOCUS_RING_CLASSES) {
      expect(trigger.className).toContain(cls);
    }
  });

  it("trigger is disabled when disabled=true", () => {
    renderDropdown({ disabled: true });
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("trigger shows 'All spaces' text when value is null", () => {
    renderDropdown({ value: null });
    expect(screen.getByRole("button")).toHaveTextContent("All spaces");
  });

  it("trigger opens dropdown on click", async () => {
    renderDropdown();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));
    // After opening, there are multiple buttons (trigger + dropdown items).
    await waitFor(() => {
      expect(screen.getAllByRole("button").length).toBeGreaterThan(1);
    });
  });
});

describe("SpaceFilterDropdown buttons — dropdown items", () => {
  beforeEach(() => {
    spacesMock.mockReset();
    spacesMock.mockResolvedValue({ spaces: SAMPLE_SPACES });
  });

  it("dropdown items are <button> elements (not divs with role=button)", async () => {
    renderDropdown();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      // Expect at least the "All spaces" item + two space items
      expect(screen.getAllByRole("button").length).toBeGreaterThanOrEqual(3);
    });

    const allButtons = screen.getAllByRole("button");
    for (const btn of allButtons) {
      expect(btn.tagName).toBe("BUTTON");
    }
  });

  it("dropdown items carry all three focus-ring classes", async () => {
    renderDropdown();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getAllByRole("button").length).toBeGreaterThanOrEqual(3);
    });

    const allButtons = screen.getAllByRole("button");
    // Check all buttons (trigger + items) have focus ring
    for (const btn of allButtons) {
      for (const cls of FOCUS_RING_CLASSES) {
        expect(btn.className).toContain(cls);
      }
    }
  });

  it("clicking 'All spaces' item calls onChange(null)", async () => {
    const onChange = vi.fn();
    renderDropdown({ value: "s1", onChange });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getAllByRole("button").length).toBeGreaterThan(1);
    });

    const allSpacesBtn = screen
      .getAllByRole("button")
      .find((b) => b.textContent?.includes("All spaces"));
    expect(allSpacesBtn).toBeDefined();
    await user.click(allSpacesBtn!);

    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("clicking a space item calls onChange with the space id", async () => {
    const onChange = vi.fn();
    renderDropdown({ value: null, onChange });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getAllByRole("button").length).toBeGreaterThanOrEqual(3);
    });

    const backendBtn = screen
      .getAllByRole("button")
      .find((b) => b.textContent?.includes("Backend"));
    expect(backendBtn).toBeDefined();
    await user.click(backendBtn!);

    expect(onChange).toHaveBeenCalledWith("s1");
  });
});
