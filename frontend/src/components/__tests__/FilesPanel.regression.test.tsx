/**
 * R6 regression guard — FilesPanel must continue to mount with only `taskId`
 * (and optionally `className`) and render FileBrowser WITHOUT a breadcrumb.
 *
 * This file MUST NOT modify FilesPanel.tsx. Its purpose is to fail loudly if
 * anyone accidentally breaks FilesPanel backward-compatibility.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Capture FileBrowser props so we can assert on them without rendering the
// real FileBrowser (which pulls in MarkdownEditorModal / file-viewer deps).
// ---------------------------------------------------------------------------

const fileBrowserSpy = vi.fn();

vi.mock("../FileBrowser", () => ({
  FileBrowser: (props: Record<string, unknown>) => {
    fileBrowserSpy(props);
    return <div data-testid="file-browser-stub" />;
  },
}));

// ---------------------------------------------------------------------------
// Mock api module so no real HTTP calls are made.
// ---------------------------------------------------------------------------

const mockTaskFiles = vi.fn().mockResolvedValue([]);
const mockUploadTaskFile = vi.fn().mockResolvedValue({});
const mockSaveTaskFile = vi.fn().mockResolvedValue({});

vi.mock("../../api", () => ({
  api: {
    taskFiles: (...args: unknown[]) => mockTaskFiles(...args),
    uploadTaskFile: (...args: unknown[]) => mockUploadTaskFile(...args),
    saveTaskFile: (...args: unknown[]) => mockSaveTaskFile(...args),
  },
  taskFileUrl: (taskId: string, path: string, dl?: boolean) =>
    `/api/tasks/${taskId}/files/${path}${dl ? "?download=true" : ""}`,
}));

// Import AFTER mocks
import { FilesPanel } from "../FilesPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
    },
  });
}

function renderPanel(taskId = "task-regression", className?: string) {
  const queryClient = makeQueryClient();
  const result = render(
    <QueryClientProvider client={queryClient}>
      <FilesPanel taskId={taskId} className={className} />
    </QueryClientProvider>,
  );
  return { queryClient, ...result };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FilesPanel regression (R6)", () => {
  afterEach(() => {
    fileBrowserSpy.mockClear();
    mockTaskFiles.mockClear();
    mockUploadTaskFile.mockClear();
    mockSaveTaskFile.mockClear();
  });

  // -----------------------------------------------------------------------
  // R6-1: Mounts with only taskId — no breadcrumb header in DOM
  // -----------------------------------------------------------------------

  it("mounts with only taskId — no <nav> breadcrumb element in DOM", () => {
    const { container } = renderPanel("task-42");
    expect(container.querySelector("nav")).toBeNull();
  });

  it("mounts with taskId + className — no breadcrumb in DOM", () => {
    const { container } = renderPanel("task-99", "custom-class");
    expect(container.querySelector("nav")).toBeNull();
  });

  // -----------------------------------------------------------------------
  // R6-2: FileBrowser receives no breadcrumb prop
  // -----------------------------------------------------------------------

  it("FileBrowser is rendered without a breadcrumb prop", async () => {
    renderPanel("task-42");

    // Flush the initial query fetch
    await act(async () => {
      await Promise.resolve();
    });

    expect(fileBrowserSpy).toHaveBeenCalled();
    const lastProps =
      fileBrowserSpy.mock.calls[fileBrowserSpy.mock.calls.length - 1][0] as Record<
        string,
        unknown
      >;
    // breadcrumb MUST be absent (undefined or not present)
    expect(lastProps.breadcrumb).toBeUndefined();
  });

  // -----------------------------------------------------------------------
  // R6-3: Upload mutation remains wired (onUpload prop is a function)
  // -----------------------------------------------------------------------

  it("FileBrowser receives onUpload callback (upload mutation wired)", async () => {
    renderPanel("task-42");

    await act(async () => {
      await Promise.resolve();
    });

    const lastProps =
      fileBrowserSpy.mock.calls[fileBrowserSpy.mock.calls.length - 1][0] as Record<
        string,
        unknown
      >;
    expect(typeof lastProps.onUpload).toBe("function");
  });

  // -----------------------------------------------------------------------
  // R6-4: Save mutation remains wired (onSave prop is a function)
  // -----------------------------------------------------------------------

  it("FileBrowser receives onSave callback (save mutation wired)", async () => {
    renderPanel("task-42");

    await act(async () => {
      await Promise.resolve();
    });

    const lastProps =
      fileBrowserSpy.mock.calls[fileBrowserSpy.mock.calls.length - 1][0] as Record<
        string,
        unknown
      >;
    expect(typeof lastProps.onSave).toBe("function");
  });

  // -----------------------------------------------------------------------
  // R6-5: 10-second refetch interval on api.taskFiles query
  // -----------------------------------------------------------------------

  it("api.taskFiles is refetched after 10 seconds (refetchInterval: 10_000)", async () => {
    vi.useFakeTimers();
    mockTaskFiles.mockResolvedValue([]);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <FilesPanel taskId="task-interval" />
      </QueryClientProvider>,
    );

    // Flush the initial fetch
    await act(async () => {
      await Promise.resolve();
    });

    const callsAfterMount = mockTaskFiles.mock.calls.length;
    expect(callsAfterMount).toBeGreaterThanOrEqual(1);

    // Advance 10 seconds + a small buffer to trigger the refetch interval
    await act(async () => {
      vi.advanceTimersByTime(10_001);
      await Promise.resolve();
    });

    expect(mockTaskFiles.mock.calls.length).toBeGreaterThan(callsAfterMount);

    vi.useRealTimers();
  });

  // -----------------------------------------------------------------------
  // R6-6: fileUrlBuilder uses taskFileUrl with the correct taskId
  // -----------------------------------------------------------------------

  it("fileUrlBuilder passed to FileBrowser builds URLs with the task's taskId", async () => {
    renderPanel("my-task-id");

    await act(async () => {
      await Promise.resolve();
    });

    const lastProps =
      fileBrowserSpy.mock.calls[fileBrowserSpy.mock.calls.length - 1][0] as Record<
        string,
        unknown
      >;
    const builder = lastProps.fileUrlBuilder as (path: string, dl?: boolean) => string;
    expect(builder("CLAUDE.md")).toContain("/api/tasks/my-task-id/files/");
    expect(builder("CLAUDE.md", true)).toContain("download=true");
  });
});
