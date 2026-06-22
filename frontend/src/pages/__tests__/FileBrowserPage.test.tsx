import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { Board } from "../../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Capture FileBrowser props so we can assert on breadcrumb, files, etc.
const fileBrowserSpy = vi.fn();

vi.mock("../../components/FileBrowser", () => ({
  FileBrowser: (props: {
    breadcrumb?: string;
    isLoading?: boolean;
    files?: unknown[];
    fileUrlBuilder?: (path: string, dl?: boolean) => string;
    onUpload?: unknown;
    onSave?: unknown;
  }) => {
    fileBrowserSpy(props);
    return (
      <div data-testid="file-browser">
        {props.breadcrumb && (
          <span data-testid="breadcrumb">{props.breadcrumb}</span>
        )}
        {props.isLoading && <span data-testid="files-loading">Loading files…</span>}
        {!props.isLoading &&
          (props.files ?? []).map((f: unknown, i: number) => (
            <span key={i} data-testid="file-entry">
              {(f as { name: string }).name}
            </span>
          ))}
      </div>
    );
  },
}));

// Control useBoard return from tests
let mockBoardData: Board | undefined = undefined;
let mockBoardLoading = false;
let mockBoardError = false;

vi.mock("../../hooks/useTasks", () => ({
  useBoard: () => ({
    data: mockBoardData,
    isLoading: mockBoardLoading,
    isError: mockBoardError,
  }),
}));

// Control useSpace return from tests
let mockSpaceData: { id: string; name: string } | undefined = undefined;

vi.mock("../../hooks/useSpaces", () => ({
  useSpace: () => ({ data: mockSpaceData }),
}));

// Mock api module so taskFiles is controllable
const mockTaskFiles = vi.fn();

vi.mock("../../api", () => ({
  api: {
    taskFiles: (...args: unknown[]) => mockTaskFiles(...args),
  },
  taskFileUrl: (taskId: string, path: string, dl?: boolean) =>
    `/api/tasks/${taskId}/files/${path}${dl ? "?download=true" : ""}`,
}));

// Import component AFTER vi.mock
import { FileBrowserPage } from "../FileBrowserPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
    },
  });
}

function makeTask(
  id: string,
  title: string,
  overrides: Partial<import("../../types").TaskSummary> = {},
): import("../../types").TaskSummary {
  return {
    id,
    space_id: "space-1",
    title,
    state: "backlog",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    waiting_question: null,
    brief_preview: "",
    priority: 0,
    manual_order: 0,
    agent_mode: "auto",
    space_name: "My Space",
    space_color: "#15803D",
    space_icon: null,
    type: "task",
    parent_id: null,
    ...overrides,
  };
}

function makeBoard(
  tasks: import("../../types").TaskSummary[],
): Board {
  return {
    backlog: tasks,
    active: [],
    waiting: [],
    done: [],
    archived: [],
  };
}

function renderPage(spaceId = "space-1") {
  const queryClient = makeQueryClient();
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/spaces/${spaceId}/files`]}>
          <Routes>
            <Route path="/spaces/:spaceId/files" element={<FileBrowserPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FileBrowserPage", () => {
  beforeEach(() => {
    mockBoardData = undefined;
    mockBoardLoading = false;
    mockBoardError = false;
    mockSpaceData = { id: "space-1", name: "My Space" };
    mockTaskFiles.mockResolvedValue([]);
    fileBrowserSpy.mockClear();
    mockTaskFiles.mockClear();
  });

  // -----------------------------------------------------------------------
  // Loading state
  // -----------------------------------------------------------------------

  it("shows loading indicator while board is loading", () => {
    mockBoardLoading = true;
    renderPage();
    expect(screen.getByText("Loading tasks…")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Error state
  // -----------------------------------------------------------------------

  it("shows error message when board fails to load", () => {
    mockBoardError = true;
    renderPage();
    expect(screen.getByText("Failed to load tasks.")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Empty-state when no task selected
  // -----------------------------------------------------------------------

  it("shows guidance text when no task is selected", () => {
    mockBoardData = makeBoard([makeTask("t1", "My Task")]);
    renderPage();
    expect(
      screen.getByText("Select a task to browse its files."),
    ).toBeInTheDocument();
    // FileBrowser should NOT be rendered
    expect(screen.queryByTestId("file-browser")).toBeNull();
  });

  // -----------------------------------------------------------------------
  // Task list renders
  // -----------------------------------------------------------------------

  it("renders root tasks in the tree", () => {
    mockBoardData = makeBoard([
      makeTask("t1", "Alpha Task"),
      makeTask("t2", "Beta Task"),
    ]);
    renderPage();
    expect(screen.getByText("Alpha Task")).toBeInTheDocument();
    expect(screen.getByText("Beta Task")).toBeInTheDocument();
  });

  it("renders goals as collapsible nodes (collapsed by default)", () => {
    const goal = makeTask("g1", "My Goal", { type: "goal" });
    const child = makeTask("c1", "Child Task", { parent_id: "g1" });
    mockBoardData = makeBoard([goal, child]);
    renderPage();

    // Goal is visible
    expect(screen.getByText("My Goal")).toBeInTheDocument();
    // Child is NOT visible (collapsed by default)
    expect(screen.queryByText("Child Task")).toBeNull();
  });

  it("expands a goal node on click to reveal children", async () => {
    const goal = makeTask("g1", "My Goal", { type: "goal" });
    const child = makeTask("c1", "Child Task", { parent_id: "g1" });
    mockBoardData = makeBoard([goal, child]);
    renderPage();

    // Click the goal button to expand
    fireEvent.click(screen.getByText("My Goal"));
    expect(screen.getByText("Child Task")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Task click triggers files query and shows FileBrowser
  // -----------------------------------------------------------------------

  it("clicking a root task triggers api.taskFiles and renders FileBrowser", async () => {
    mockTaskFiles.mockResolvedValue([
      { name: "README.md", path: "README.md", size: 100, modified_at: "2026-01-01T00:00:00Z", is_dir: false, category: "text" },
    ]);
    mockBoardData = makeBoard([makeTask("t1", "My Task")]);
    renderPage();

    await act(async () => {
      fireEvent.click(screen.getByText("My Task"));
    });

    expect(mockTaskFiles).toHaveBeenCalledWith("t1");
    expect(screen.getByTestId("file-browser")).toBeInTheDocument();
  });

  it("clicking a child task under a goal triggers api.taskFiles", async () => {
    mockTaskFiles.mockResolvedValue([]);
    const goal = makeTask("g1", "The Goal", { type: "goal" });
    const child = makeTask("c1", "Child Task", { parent_id: "g1" });
    mockBoardData = makeBoard([goal, child]);
    renderPage();

    // Expand the goal first
    fireEvent.click(screen.getByText("The Goal"));

    await act(async () => {
      fireEvent.click(screen.getByText("Child Task"));
    });

    expect(mockTaskFiles).toHaveBeenCalledWith("c1");
    expect(screen.getByTestId("file-browser")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Breadcrumb updates with task selection
  // -----------------------------------------------------------------------

  it("breadcrumb shows space name and task title when task is selected", async () => {
    mockTaskFiles.mockResolvedValue([]);
    mockBoardData = makeBoard([makeTask("t1", "Alpha Task")]);
    renderPage();

    await act(async () => {
      fireEvent.click(screen.getByText("Alpha Task"));
    });

    const breadcrumb = screen.getByTestId("breadcrumb");
    expect(breadcrumb.textContent).toContain("My Space");
    expect(breadcrumb.textContent).toContain("Alpha Task");
  });

  it("breadcrumb shows only space name before any task is selected", () => {
    mockBoardData = makeBoard([makeTask("t1", "Alpha Task")]);
    renderPage();

    // No file browser shown (no selection), so no breadcrumb yet
    expect(screen.queryByTestId("breadcrumb")).toBeNull();
  });

  // -----------------------------------------------------------------------
  // Files loading state within FileBrowser
  // -----------------------------------------------------------------------

  it("FileBrowser receives isLoading=true while files are fetching", async () => {
    // Never resolve (stays loading)
    mockTaskFiles.mockImplementation(() => new Promise(() => {}));
    mockBoardData = makeBoard([makeTask("t1", "My Task")]);
    renderPage();

    await act(async () => {
      fireEvent.click(screen.getByText("My Task"));
    });

    expect(screen.getByTestId("files-loading")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Files error state
  // -----------------------------------------------------------------------

  it("shows error banner when task files fail to load", async () => {
    mockTaskFiles.mockRejectedValue(new Error("500 Server Error"));
    mockBoardData = makeBoard([makeTask("t1", "My Task")]);
    const queryClient = makeQueryClient();
    render(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: { queries: { retry: false, staleTime: Infinity } },
          })
        }
      >
        <MemoryRouter initialEntries={["/spaces/space-1/files"]}>
          <Routes>
            <Route path="/spaces/:spaceId/files" element={<FileBrowserPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await act(async () => {
      fireEvent.click(screen.getByText("My Task"));
    });

    // Wait for error to propagate
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText("Failed to load files.")).toBeInTheDocument();
    void queryClient; // suppress unused warning
  });

  // -----------------------------------------------------------------------
  // fileUrlBuilder uses taskFileUrl (R7 — task endpoint, NOT space endpoint)
  // -----------------------------------------------------------------------

  it("fileUrlBuilder passed to FileBrowser uses taskFileUrl with selected taskId", async () => {
    mockTaskFiles.mockResolvedValue([]);
    mockBoardData = makeBoard([makeTask("task-abc", "My Task")]);
    renderPage();

    await act(async () => {
      fireEvent.click(screen.getByText("My Task"));
    });

    expect(fileBrowserSpy).toHaveBeenCalled();
    const props = fileBrowserSpy.mock.calls[fileBrowserSpy.mock.calls.length - 1][0] as {
      fileUrlBuilder: (path: string, dl?: boolean) => string;
    };
    const url = props.fileUrlBuilder("some/file.txt");
    expect(url).toContain("/api/tasks/task-abc/files/");
    expect(url).not.toContain("/api/spaces/");
  });

  // -----------------------------------------------------------------------
  // Responsive layout classes
  // -----------------------------------------------------------------------

  it("page root has md:flex-row layout class for responsive stacking", () => {
    mockBoardData = makeBoard([]);
    const { container } = renderPage();
    const root = container.firstElementChild;
    expect(root?.className).toContain("md:flex-row");
  });
});
