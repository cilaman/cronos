import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { STORAGE_KEYS } from "../lib/storage";
import type { TaskState, View } from "../types";

// Capture the props passed to <Board /> so we can assert on them.
const boardSpy = vi.fn();
// Capture the props passed to <BoardToolbar /> so we can assert that
// onViewChange is or is not supplied depending on the URL/route context.
const toolbarSpy = vi.fn();

vi.mock("../components/Board", () => ({
  Board: (props: {
    spaceId: string | null;
    compact?: boolean;
    viewId?: string | null;
    activeLaneStates?: TaskState[];
  }) => {
    boardSpy(props);
    return (
      <div
        data-testid="board-mock"
        data-compact={String(props.compact ?? false)}
        data-space-id={props.spaceId ?? "null"}
        data-view-id={props.viewId ?? "null"}
        data-active-lanes={
          props.activeLaneStates ? props.activeLaneStates.join(",") : "undefined"
        }
      />
    );
  },
}));

vi.mock("../components/BoardToolbar", () => ({
  BoardToolbar: (props: {
    spaceId: string | null;
    viewId?: string | null;
    onViewChange?: (next: string | null) => void;
    onCompactToggle: () => void;
    compact: boolean;
    onSortModeToggle: () => void;
    sortMode: string;
  }) => {
    toolbarSpy(props);
    return (
      <div
        data-testid="toolbar-mock"
        data-view-id={props.viewId ?? "null"}
        data-has-on-view-change={String(typeof props.onViewChange === "function")}
      >
        {/* Re-expose the compact toggle so the existing compact-state tests
            (which click `Switch to minimal cards`) still drive the page. */}
        <button
          type="button"
          aria-label={
            props.compact ? "Switch to full cards" : "Switch to minimal cards"
          }
          onClick={props.onCompactToggle}
        />
        {/* A button that, when clicked, simulates the user picking a view in
            the picker. The test asserts the resulting Board props. */}
        {props.onViewChange && (
          <button
            type="button"
            data-testid="simulate-view-change"
            onClick={() => props.onViewChange?.("focus")}
          />
        )}
      </div>
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
    spaceViews: vi.fn(async (): Promise<View[]> => []),
    board: vi.fn(),
    create: vi.fn(),
    start: vi.fn(),
    uploadTaskFile: vi.fn(),
  },
}));

// Import after vi.mock so the mocks apply.
import { BoardPage } from "../pages/BoardPage";
import { Routes, Route } from "react-router-dom";

function renderPage(initialEntries: string[] = ["/board"]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/board" element={<BoardPage />} />
          <Route path="/spaces/:spaceId" element={<BoardPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BoardPage — compact state + storage integration", () => {
  beforeEach(() => {
    window.localStorage.clear();
    boardSpy.mockClear();
    toolbarSpy.mockClear();
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

describe("BoardPage — view URL param routing", () => {
  beforeEach(() => {
    window.localStorage.clear();
    boardSpy.mockClear();
    toolbarSpy.mockClear();
  });

  it("passes viewId=null to Board when the URL has no ?view param (scoped space)", async () => {
    renderPage(["/spaces/space-1"]);

    await waitFor(() => {
      expect(boardSpy).toHaveBeenCalled();
    });
    const latest = boardSpy.mock.calls[boardSpy.mock.calls.length - 1][0];
    expect(latest.viewId).toBeNull();
    expect(latest.spaceId).toBe("space-1");
  });

  it("passes ?view=focus through to Board.viewId when the URL has it", async () => {
    // Provide a views list that contains "focus" so the
    // reset-on-deleted-view effect does NOT wipe the URL param.
    const { api } = await import("../api");
    (api.spaceViews as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        id: "focus",
        name: "Focus",
        lanes: ["active", "waiting"],
        type_filter: null,
        default: false,
        created_at: "2026-05-25T00:00:00Z",
        updated_at: "2026-05-25T00:00:00Z",
      },
    ] satisfies View[]);

    renderPage(["/spaces/space-1?view=focus"]);

    await waitFor(() => {
      const latest = boardSpy.mock.calls[boardSpy.mock.calls.length - 1][0];
      expect(latest.viewId).toBe("focus");
    });
  });

  it("propagates the same viewId to BoardToolbar", async () => {
    const { api } = await import("../api");
    (api.spaceViews as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        id: "focus",
        name: "Focus",
        lanes: ["active", "waiting"],
        type_filter: null,
        default: false,
        created_at: "2026-05-25T00:00:00Z",
        updated_at: "2026-05-25T00:00:00Z",
      },
    ] satisfies View[]);

    renderPage(["/spaces/space-1?view=focus"]);

    await waitFor(() => {
      const latest = toolbarSpy.mock.calls[toolbarSpy.mock.calls.length - 1][0];
      expect(latest.viewId).toBe("focus");
    });
  });

  it("passes onViewChange to BoardToolbar when the page is scoped to a space", async () => {
    renderPage(["/spaces/space-1"]);

    // Wait until BoardToolbar has been rendered.
    await waitFor(() => {
      expect(screen.getByTestId("toolbar-mock")).toBeInTheDocument();
    });
    expect(screen.getByTestId("toolbar-mock").getAttribute("data-has-on-view-change")).toBe(
      "true",
    );
  });

  it("does NOT pass onViewChange to BoardToolbar on the unscoped /board route", async () => {
    renderPage(["/board"]);

    await waitFor(() => {
      expect(screen.getByTestId("toolbar-mock")).toBeInTheDocument();
    });
    // The /board page does not own a single space, so the picker must be
    // hidden (i.e. onViewChange omitted) — otherwise the picker would have
    // no spaceId to load views for.
    expect(screen.getByTestId("toolbar-mock").getAttribute("data-has-on-view-change")).toBe(
      "false",
    );
  });

  it("invoking onViewChange from the toolbar pushes ?view= into the URL and propagates to Board + Toolbar", async () => {
    // The reset-on-deleted-view useEffect would otherwise wipe the URL
    // param the moment views resolve and don't contain "focus". Provide a
    // realistic views list that includes "focus" so the URL survives.
    const { api } = await import("../api");
    (api.spaceViews as ReturnType<typeof vi.fn>).mockResolvedValue([
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
    ] satisfies View[]);

    renderPage(["/spaces/space-1"]);
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByTestId("simulate-view-change")).toBeInTheDocument();
    });

    // Sanity: starts with viewId=null on both children.
    expect(screen.getByTestId("toolbar-mock").getAttribute("data-view-id")).toBe(
      "null",
    );
    expect(screen.getByTestId("board-mock").getAttribute("data-view-id")).toBe(
      "null",
    );

    // Act — the mock toolbar fires onViewChange("focus"), which BoardPage
    // bound to a setSearchParams writer that pushes ?view=focus.
    await user.click(screen.getByTestId("simulate-view-change"));

    // Both children should re-render with viewId="focus" once the URL
    // (and therefore searchParams) updates.
    await waitFor(() => {
      expect(
        screen.getByTestId("toolbar-mock").getAttribute("data-view-id"),
      ).toBe("focus");
    });
    expect(screen.getByTestId("board-mock").getAttribute("data-view-id")).toBe(
      "focus",
    );
  });

  it("resets ?view to clean URL when the active view is missing from the loaded list", async () => {
    // This is the contract of the "silently reset to default" useEffect:
    // a stale bookmark like /spaces/space-1?view=deleted-view should NOT
    // strand the user on a broken view — the URL param is cleared.
    const { api } = await import("../api");
    (api.spaceViews as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: "all",
        name: "All lanes",
        lanes: ["backlog", "active", "waiting", "done"],
        type_filter: null,
        default: true,
        created_at: "2026-05-25T00:00:00Z",
        updated_at: "2026-05-25T00:00:00Z",
      },
    ] satisfies View[]);

    renderPage(["/spaces/space-1?view=deleted-view"]);

    // After views load and the effect runs, toolbar.viewId should clear.
    await waitFor(() => {
      expect(
        screen.getByTestId("toolbar-mock").getAttribute("data-view-id"),
      ).toBe("null");
    });
    expect(screen.getByTestId("board-mock").getAttribute("data-view-id")).toBe(
      "null",
    );
  });
});

describe("BoardPage — activeLaneStates propagation", () => {
  beforeEach(() => {
    window.localStorage.clear();
    boardSpy.mockClear();
    toolbarSpy.mockClear();
  });

  it("passes undefined activeLaneStates when no views are loaded yet", async () => {
    // The default spaceViews mock resolves with [] — useMemo returns null,
    // and `activeLaneStates` becomes undefined.
    renderPage(["/spaces/space-1"]);

    await waitFor(() => {
      expect(boardSpy).toHaveBeenCalled();
    });
    const latest = boardSpy.mock.calls[boardSpy.mock.calls.length - 1][0];
    expect(latest.activeLaneStates).toBeUndefined();
  });

  it("propagates the active view's lanes to Board when views resolve", async () => {
    const { api } = await import("../api");
    (api.spaceViews as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
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
    ] satisfies View[]);

    renderPage(["/spaces/space-1?view=focus"]);

    // Wait until the views resolve and propagate as activeLaneStates.
    await waitFor(() => {
      const latest = boardSpy.mock.calls[boardSpy.mock.calls.length - 1][0];
      expect(latest.activeLaneStates).toEqual(["active", "waiting"]);
    });
  });

  it("falls back to the default view's lanes when ?view points to an unknown id", async () => {
    const { api } = await import("../api");
    (api.spaceViews as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        id: "all",
        name: "All lanes",
        lanes: ["backlog", "active", "waiting", "done"],
        type_filter: null,
        default: true,
        created_at: "2026-05-25T00:00:00Z",
        updated_at: "2026-05-25T00:00:00Z",
      },
    ] satisfies View[]);

    renderPage(["/spaces/space-1?view=does-not-exist"]);

    // The deleted-view useEffect clears the URL param, but in the meantime
    // the activeView memo falls back to the default — the user must never
    // see an "empty board" because a bookmark went stale.
    await waitFor(() => {
      const latest = boardSpy.mock.calls[boardSpy.mock.calls.length - 1][0];
      expect(latest.activeLaneStates).toEqual([
        "backlog",
        "active",
        "waiting",
        "done",
      ]);
    });
  });
});
