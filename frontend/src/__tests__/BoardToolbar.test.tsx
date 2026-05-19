import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { BoardToolbar } from "../components/BoardToolbar";

// Mock the API module so useSpaces() resolves without real network calls.
vi.mock("../api", () => ({
  api: {
    spaces: vi.fn(async () => ({
      spaces: [],
      totals: {
        backlog: 0,
        active: 0,
        waiting: 0,
        done: 0,
        archived: 0,
      },
    })),
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
