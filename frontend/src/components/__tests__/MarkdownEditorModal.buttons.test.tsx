/**
 * I5 button-focus guard: MarkdownEditorModal.buttons.test.tsx
 *
 * Asserts that:
 * 1. Mode-toggle (Edit / Preview / Split) buttons are real <button> elements
 *    with the segmented archetype focus ring.
 * 2. Save button is a real <button> with the secondary variant.
 * 3. Close button is a real <button> with aria-label="Close editor".
 * 4. All buttons expose focus-visible:ring-accent class from the primitives.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import type { TaskFile } from "../../types";

// ---------------------------------------------------------------------------
// Mock @uiw/react-md-editor — it has non-jsdom CSS imports that fail in tests
// ---------------------------------------------------------------------------
vi.mock("@uiw/react-md-editor", () => ({
  default: ({ value }: { value: string }) => (
    <div data-testid="md-editor">{value}</div>
  ),
  Markdown: ({ source }: { source: string }) => (
    <div data-testid="md-preview">{source}</div>
  ),
}));
vi.mock("@uiw/react-md-editor/markdown-editor.css", () => ({}));

// ---------------------------------------------------------------------------
// Mock useTheme — we don't need real theme logic in button tests
// ---------------------------------------------------------------------------
vi.mock("../../hooks/useTheme", () => ({
  useTheme: () => ["light", vi.fn()],
}));

// ---------------------------------------------------------------------------
// Stub global.fetch so the useEffect doesn't crash
// ---------------------------------------------------------------------------
beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    text: async () => "# Hello",
  }) as unknown as typeof fetch;
});

// Import AFTER mocks so they apply
import { MarkdownEditorModal } from "../MarkdownEditorModal";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const sampleFile: TaskFile = {
  name: "README.md",
  path: "README.md",
  size: 512,
  modified_at: "2026-01-01T00:00:00Z",
  is_dir: false,
  category: "text",
};

function renderModal(props: Partial<Parameters<typeof MarkdownEditorModal>[0]> = {}) {
  const onClose = vi.fn();
  render(
    <MarkdownEditorModal
      file={sampleFile}
      fileUrl="http://test/README.md"
      onClose={onClose}
      {...props}
    />,
  );
  return { onClose };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MarkdownEditorModal button semantics (I5)", () => {
  it("renders mode-toggle buttons as real <button> elements", async () => {
    renderModal();
    await act(async () => { await Promise.resolve(); });

    // Edit and Preview are always visible; Split is hidden on mobile via CSS
    const editBtn = screen.getByRole("button", { name: "Edit" });
    const previewBtn = screen.getByRole("button", { name: "Preview" });
    expect(editBtn.tagName).toBe("BUTTON");
    expect(previewBtn.tagName).toBe("BUTTON");
  });

  it("mode-toggle buttons carry focus-visible:ring-accent class", async () => {
    renderModal();
    await act(async () => { await Promise.resolve(); });

    const editBtn = screen.getByRole("button", { name: "Edit" });
    expect(editBtn.className).toContain("focus-visible:ring-accent");
  });

  it("mode-toggle buttons carry focus:outline-none class", async () => {
    renderModal();
    await act(async () => { await Promise.resolve(); });

    const editBtn = screen.getByRole("button", { name: "Edit" });
    expect(editBtn.className).toContain("focus:outline-none");
  });

  it("close button is a real <button> with aria-label='Close editor'", async () => {
    renderModal();
    await act(async () => { await Promise.resolve(); });

    const closeBtn = screen.getByRole("button", { name: "Close editor" });
    expect(closeBtn.tagName).toBe("BUTTON");
  });

  it("close button carries focus-visible ring class", async () => {
    renderModal();
    await act(async () => { await Promise.resolve(); });

    const closeBtn = screen.getByRole("button", { name: "Close editor" });
    expect(closeBtn.className).toContain("focus-visible:ring-accent");
  });

  it("save button renders as real <button> when onSave prop is provided", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderModal({ onSave });
    await act(async () => { await Promise.resolve(); });

    const saveBtn = screen.getByRole("button", { name: /save/i });
    expect(saveBtn.tagName).toBe("BUTTON");
  });

  it("save button carries focus-visible ring class", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderModal({ onSave });
    await act(async () => { await Promise.resolve(); });

    const saveBtn = screen.getByRole("button", { name: /save/i });
    expect(saveBtn.className).toContain("focus-visible:ring-accent");
  });

  it("save button is disabled when content is not dirty", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderModal({ onSave });
    // After initial fetch, content is loaded but dirty=false → button disabled
    await act(async () => { await Promise.resolve(); });

    const saveBtn = screen.getByRole("button", { name: /save/i });
    expect(saveBtn).toBeDisabled();
  });

  it("save button is absent when onSave prop is omitted", async () => {
    renderModal(); // no onSave
    await act(async () => { await Promise.resolve(); });

    // Only close button + mode-toggle buttons present
    const saveBtn = screen.queryByRole("button", { name: /save/i });
    expect(saveBtn).toBeNull();
  });

  it("no raw inline <button> elements remain (all migrated to Button/IconButton primitives)", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const { container } = render(
      <MarkdownEditorModal
        file={sampleFile}
        fileUrl="http://test/README.md"
        onClose={vi.fn()}
        onSave={onSave}
      />,
    );
    await act(async () => { await Promise.resolve(); });

    // Every <button> in the modal must now come from Button or IconButton
    // primitives — both apply the focus ring. Verify all buttons have the ring.
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBeGreaterThan(0);
    buttons.forEach((btn) => {
      expect(btn.className).toContain("focus-visible:ring-accent");
    });
  });
});
