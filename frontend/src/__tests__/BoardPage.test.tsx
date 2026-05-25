import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { STORAGE_KEYS } from "../lib/storage";

// Capture the props passed to <Board /> so we can assert on `compact`.
const boardSpy = vi.fn();

vi.mock("../components/Board", () => ({
  Board: (props: { spaceId: string | null; compact?: boolean }) => {
    boardSpy(props);
    return (
      <div
        data-testid="board-mock"
        data-compact={String(props.compact ?? false)}
        data-space-id={props.spaceId ?? "null"}
      />
    );
  },
}));

vi.mock("../components/TaskForm", () => ({
  TaskForm: () => <div data-testid="task-form-mock" />,
}));

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
    board: vi.fn(),
    create: vi.fn(),
    start: vi.fn(),
    uploadTaskFile: vi.fn(),
  },
}));

// Import after vi.mock so the mocks apply.
import { BoardPage } from "../pages/BoardPage";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/board"]}>
        <BoardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BoardPage — compact state + storage integration", () => {
  beforeEach(() => {
    window.localStorage.clear();
    boardSpy.mockClear();
  });

  it("initialises compact=false when localStorage has no value", () => {
    renderPage();
    const board = screen.getByTestId("board-mock");
    expect(board.getAttribute("data-compact")).toBe("false");
  });

  it("initialises compact=true when localStorage has 'minimal'", () => {
    window.localStorage.setItem(STORAGE_KEYS.cardViewMode, "minimal");
    renderPage();
    const board = screen.getByTestId("board-mock");
    expect(board.getAttribute("data-compact")).toBe("true");
  });

  it("initialises compact=false when localStorage has 'full'", () => {
    window.localStorage.setItem(STORAGE_KEYS.cardViewMode, "full");
    renderPage();
    const board = screen.getByTestId("board-mock");
    expect(board.getAttribute("data-compact")).toBe("false");
  });

  it("passes compact prop through to the Board component", () => {
    window.localStorage.setItem(STORAGE_KEYS.cardViewMode, "minimal");
    renderPage();
    // The most recent boardSpy call should record compact=true
    const calls = boardSpy.mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    expect(calls[calls.length - 1][0].compact).toBe(true);
  });

  it("toggling compact persists 'minimal' to localStorage", async () => {
    renderPage();
    const user = userEvent.setup();
    const toggle = screen.getByRole("button", {
      name: /Switch to minimal cards/i,
    });
    await user.click(toggle);
    expect(window.localStorage.getItem(STORAGE_KEYS.cardViewMode)).toBe(
      "minimal",
    );
  });

  it("toggling compact off persists 'full' to localStorage", async () => {
    window.localStorage.setItem(STORAGE_KEYS.cardViewMode, "minimal");
    renderPage();
    const user = userEvent.setup();
    const toggle = screen.getByRole("button", {
      name: /Switch to full cards/i,
    });
    await user.click(toggle);
    expect(window.localStorage.getItem(STORAGE_KEYS.cardViewMode)).toBe("full");
  });

  it("after toggling, Board receives the updated compact prop", async () => {
    renderPage();
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /Switch to minimal cards/i }),
    );
    // The latest render of Board should reflect compact=true
    const board = screen.getByTestId("board-mock");
    expect(board.getAttribute("data-compact")).toBe("true");
  });

  it("toggling twice flips back to compact=false", async () => {
    renderPage();
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /Switch to minimal cards/i }),
    );
    await user.click(
      screen.getByRole("button", { name: /Switch to full cards/i }),
    );
    const board = screen.getByTestId("board-mock");
    expect(board.getAttribute("data-compact")).toBe("false");
    expect(window.localStorage.getItem(STORAGE_KEYS.cardViewMode)).toBe("full");
  });
});
