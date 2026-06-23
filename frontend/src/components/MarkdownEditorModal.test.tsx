/**
 * Tests for MarkdownEditorModal — I4 migration to Modal.tsx contract.
 *
 * Focus areas:
 *  (a) dirty=false + Escape closes (onClose called via Modal.tsx dismissable=true)
 *  (b) dirty=true  + Escape does NOT close (dismissable=false blocks it)
 *  (c) dirty=true  + scrim click does NOT close
 *  (d) dirty=true  + clicking the X button DOES call onClose (X is never gated)
 *  (e) dirty=false + scrim click closes
 *  (f) renders file path in header
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ── Module mocks ──────────────────────────────────────────────────────────────

vi.mock("../hooks/useTheme", () => ({
  useTheme: () => ["dark", vi.fn()] as [string, (t: string) => void],
}));

// Mock the heavy MDEditor so tests are fast and jsdom-safe
vi.mock("@uiw/react-md-editor", () => {
  function MDEditor({ value, onChange }: { value: string; onChange: (v: string | undefined) => void }) {
    return (
      <textarea
        data-testid="md-editor"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  MDEditor.Markdown = ({ source }: { source: string }) => (
    <div data-testid="md-preview">{source}</div>
  );
  return { default: MDEditor };
});

// Silence CSS import from @uiw/react-md-editor
vi.mock("@uiw/react-md-editor/markdown-editor.css", () => ({}));

// ── Import after mocks ────────────────────────────────────────────────────────

import { MarkdownEditorModal } from "./MarkdownEditorModal";
import type { TaskFile } from "../types";

// ── Helpers ───────────────────────────────────────────────────────────────────

const FILE: TaskFile = {
  path: "notes/README.md",
  name: "README.md",
  size: 0,
  modified_at: "2026-01-01T00:00:00Z",
  is_dir: false,
  category: "text",
};

const FILE_URL = "http://localhost/files/notes/README.md";
const FILE_CONTENT = "# Hello\n\nWorld.";

function mockFetch(content = FILE_CONTENT, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status: ok ? 200 : 404,
      statusText: ok ? "OK" : "Not Found",
      text: () => Promise.resolve(content),
    }),
  );
}

function renderModal(onClose = vi.fn(), onSave?: () => Promise<void>) {
  return render(
    <MarkdownEditorModal
      file={FILE}
      fileUrl={FILE_URL}
      onClose={onClose}
      onSave={onSave}
    />,
  );
}

// Wait for the async fetch to settle and component to re-render
async function waitForContent() {
  await waitFor(() =>
    expect(screen.queryByText("Loading…")).not.toBeInTheDocument(),
  );
}

// Make the editor dirty by typing into the textarea
async function makeDirty() {
  await waitForContent();
  const editor = screen.getByTestId("md-editor");
  await act(async () => {
    fireEvent.change(editor, { target: { value: FILE_CONTENT + " edited" } });
  });
}

beforeEach(() => {
  mockFetch();
  vi.restoreAllMocks();
  // Re-stub after restoreAllMocks
  mockFetch();
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("MarkdownEditorModal — renders file path", () => {
  it("shows the file path in the header", async () => {
    renderModal();
    await waitForContent();
    expect(screen.getByText("notes/README.md")).toBeInTheDocument();
  });
});

describe("MarkdownEditorModal — (a) dirty=false + Escape closes", () => {
  it("calls onClose when Escape is pressed and content is clean", async () => {
    const onClose = vi.fn();
    renderModal(onClose);
    await waitForContent();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});

describe("MarkdownEditorModal — (b) dirty=true + Escape does NOT close", () => {
  it("does NOT call onClose when Escape is pressed with unsaved changes", async () => {
    const onClose = vi.fn();
    renderModal(onClose);
    await makeDirty();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("MarkdownEditorModal — (c) dirty=true + scrim click does NOT close", () => {
  it("does NOT call onClose when scrim is clicked with unsaved changes", async () => {
    const onClose = vi.fn();
    renderModal(onClose);
    await makeDirty();

    await userEvent.click(screen.getByTestId("modal-scrim"));
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("MarkdownEditorModal — (d) dirty=true + X button DOES close", () => {
  it("calls onClose when X button is clicked even with unsaved changes", async () => {
    const onClose = vi.fn();
    renderModal(onClose);
    await makeDirty();

    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

describe("MarkdownEditorModal — (e) dirty=false + scrim click closes", () => {
  it("calls onClose when scrim is clicked and content is clean", async () => {
    const onClose = vi.fn();
    renderModal(onClose);
    await waitForContent();

    await userEvent.click(screen.getByTestId("modal-scrim"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

describe("MarkdownEditorModal — fetch error", () => {
  it("shows error message when fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        text: () => Promise.resolve(""),
      }),
    );
    renderModal();
    await waitFor(() =>
      expect(screen.getByText(/404 Not Found/)).toBeInTheDocument(),
    );
  });
});

describe("MarkdownEditorModal — X button present (uses Modal contract)", () => {
  it("renders an X close button provided by Modal.tsx", async () => {
    renderModal();
    await waitForContent();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });
});
