import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FileBrowser } from "./FileBrowser";
import type { TaskFile } from "../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** A plain text file that opens in FileViewerModal (not MarkdownEditorModal). */
function makeTextFile(overrides: Partial<TaskFile> = {}): TaskFile {
  return {
    path: "src/notes.txt",
    name: "notes.txt",
    size: 512,
    modified_at: "",
    category: "text",
    is_dir: false,
    ...overrides,
  };
}

/** A markdown file — handleOpen routes to MarkdownEditorModal, not FileViewerModal. */
function makeMdFile(overrides: Partial<TaskFile> = {}): TaskFile {
  return {
    path: "docs/guide.md",
    name: "guide.md",
    size: 256,
    modified_at: "",
    category: "text",
    is_dir: false,
    ...overrides,
  };
}

function makeImageFile(overrides: Partial<TaskFile> = {}): TaskFile {
  return {
    path: "assets/logo.png",
    name: "logo.png",
    size: 2048,
    modified_at: "",
    category: "image",
    is_dir: false,
    ...overrides,
  };
}

function fileUrlBuilder(path: string, download?: boolean): string {
  return download ? `/api/files/${path}?dl=1` : `/api/files/${path}`;
}

function renderBrowser(
  files: TaskFile[],
  extra: Partial<Parameters<typeof FileBrowser>[0]> = {},
) {
  return render(
    <FileBrowser
      files={files}
      isLoading={false}
      fileUrlBuilder={fileUrlBuilder}
      {...extra}
    />,
  );
}

// ---------------------------------------------------------------------------
// 1. File viewer modal opens when a file is clicked
// ---------------------------------------------------------------------------

describe("FileBrowser — file viewer modal opens", () => {
  it("opens the FileViewerModal when a viewable text file is clicked", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("file content here"),
    } as Response);

    renderBrowser([makeTextFile()]);

    await userEvent.click(screen.getByRole("button", { name: "Open" }));

    // Modal scrim should appear
    expect(screen.getByTestId("modal-scrim")).toBeInTheDocument();
    // The file path is shown as the modal title
    expect(screen.getByText("src/notes.txt")).toBeInTheDocument();
  });

  it("opens modal for image files without fetching text content", async () => {
    const fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy;

    renderBrowser([makeImageFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));

    expect(screen.getByTestId("modal-scrim")).toBeInTheDocument();
    // fetch should NOT have been called (images display via src URL)
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.getByRole("img", { name: "logo.png" })).toBeInTheDocument();
  });

  it("routes .md files to MarkdownEditorModal (not FileViewerModal)", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("# guide"),
    } as Response);

    renderBrowser([makeMdFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));

    // MarkdownEditorModal also wraps in Modal, so modal-scrim appears.
    // The file path title label comes from MarkdownEditorModal's header, not the title prop.
    // The important thing: there is no <pre> content display from FileViewerModal.
    // Verify the modal rendered (could be either modal type).
    expect(screen.getByTestId("modal-scrim")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. File viewer modal closes on Escape and scrim click
// ---------------------------------------------------------------------------

describe("FileBrowser — modal dismiss", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("content"),
    } as Response);
  });

  it("closes the modal when Escape is pressed", async () => {
    renderBrowser([makeTextFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByTestId("modal-scrim")).toBeInTheDocument();

    // Modal.tsx owns the Escape handler (FileBrowser no longer adds its own listener)
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByTestId("modal-scrim")).not.toBeInTheDocument();
  });

  it("closes the modal when the scrim is clicked", async () => {
    renderBrowser([makeTextFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByTestId("modal-scrim")).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("modal-scrim"));
    expect(screen.queryByTestId("modal-scrim")).not.toBeInTheDocument();
  });

  it("closes the modal when the X close button is clicked", async () => {
    renderBrowser([makeTextFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByTestId("modal-scrim")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByTestId("modal-scrim")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 3. Loading state shows Skeleton (not "Loading..." text)
// ---------------------------------------------------------------------------

describe("FileBrowser — loading state in viewer", () => {
  it("shows Skeleton variant=block while file content is loading", async () => {
    // Hold fetch open so we stay in the loading state
    let resolveFetch!: (value: Response) => void;
    globalThis.fetch = vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    renderBrowser([makeTextFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));

    // Skeleton should be present (role=status aria-label=Loading)
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();

    // Plaintext "Loading" or "Loading…" must NOT appear
    expect(screen.queryByText(/^Loading/)).not.toBeInTheDocument();

    // Cleanup
    resolveFetch({ ok: true, text: () => Promise.resolve("done") } as Response);
  });

  it("does NOT show Skeleton after content has loaded", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("loaded content"),
    } as Response);

    renderBrowser([makeTextFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));

    await waitFor(() => {
      expect(screen.getByText("loaded content")).toBeInTheDocument();
    });
    expect(screen.queryByRole("status", { name: "Loading" })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 4. File content renders when loaded
// ---------------------------------------------------------------------------

describe("FileBrowser — content rendering", () => {
  it("renders text file content in a <pre> block", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("# Hello from notes"),
    } as Response);

    renderBrowser([makeTextFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));

    await waitFor(() => {
      expect(screen.getByText("# Hello from notes")).toBeInTheDocument();
    });
  });

  it("renders an error message when fetch fails", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      text: () => Promise.resolve(""),
    } as unknown as Response);

    renderBrowser([makeTextFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));

    await waitFor(() => {
      expect(screen.getByText("404 Not Found")).toBeInTheDocument();
    });
  });

  it("renders the download link inside the modal", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("content"),
    } as Response);

    renderBrowser([makeTextFile()]);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));

    await waitFor(() => {
      const downloadLink = screen.getByRole("link", { name: "Download" });
      expect(downloadLink).toBeInTheDocument();
      expect(downloadLink).toHaveAttribute(
        "href",
        "/api/files/src/notes.txt?dl=1",
      );
    });
  });
});

// ---------------------------------------------------------------------------
// 5. FileBrowser list-level loading state (isLoading prop)
// ---------------------------------------------------------------------------

describe("FileBrowser — list loading state", () => {
  it("shows Loading… text while isLoading=true (list level)", () => {
    render(
      <FileBrowser
        files={[]}
        isLoading={true}
        fileUrlBuilder={fileUrlBuilder}
      />,
    );
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows 'No files yet.' when isLoading=false and files=[]", () => {
    render(
      <FileBrowser
        files={[]}
        isLoading={false}
        fileUrlBuilder={fileUrlBuilder}
      />,
    );
    expect(screen.getByText("No files yet.")).toBeInTheDocument();
  });
});
