import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { FileBrowser } from "../FileBrowser";
import type { TaskFile } from "../../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../MarkdownEditorModal", () => ({
  MarkdownEditorModal: () => null,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const noopUrlBuilder = (path: string, _download?: boolean) => `/files/${path}`;

const sampleFiles: TaskFile[] = [
  {
    name: "README.md",
    path: "README.md",
    size: 1024,
    modified_at: "2026-01-01T00:00:00Z",
    is_dir: false,
    category: "text",
  },
];

function renderBrowser(props: Partial<Parameters<typeof FileBrowser>[0]> = {}) {
  return render(
    <FileBrowser
      files={sampleFiles}
      isLoading={false}
      fileUrlBuilder={noopUrlBuilder}
      {...props}
    />,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FileBrowser", () => {
  it("(a) breadcrumb prop omitted — no nav element in DOM", () => {
    const { container } = renderBrowser();
    expect(container.querySelector("nav")).toBeNull();
  });

  it("(b) breadcrumb prop = string — rendered above file list in nav element", () => {
    renderBrowser({ breadcrumb: "Space Alpha / task-001" });
    const nav = screen.getByRole("navigation");
    expect(nav).toBeTruthy();
    expect(nav.textContent).toContain("Space Alpha / task-001");
    // File list still renders after the breadcrumb
    expect(screen.getByText("README.md")).toBeTruthy();
  });

  it("(c) breadcrumb prop = JSX node — rendered in nav element", () => {
    const BreadcrumbNode = (
      <span data-testid="bc-node">
        <strong>Space</strong> / task-002
      </span>
    );
    renderBrowser({ breadcrumb: BreadcrumbNode });
    const nav = screen.getByRole("navigation");
    expect(nav).toBeTruthy();
    expect(screen.getByTestId("bc-node")).toBeTruthy();
    expect(nav.textContent).toContain("task-002");
  });

  it("(d) loading state renders without breadcrumb or file rows", () => {
    const { container } = renderBrowser({ isLoading: true, files: [], breadcrumb: undefined });
    expect(container.querySelector("nav")).toBeNull();
    expect(screen.getByText("Loading…")).toBeTruthy();
  });

  it("(d) empty files with no breadcrumb — no nav element, shows empty state", () => {
    const { container } = renderBrowser({ files: [], breadcrumb: undefined });
    expect(container.querySelector("nav")).toBeNull();
    expect(screen.getByText("No files yet.")).toBeTruthy();
  });

  it("breadcrumb above file list — nav precedes file list in DOM order", () => {
    const { container } = renderBrowser({ breadcrumb: "Breadcrumb text" });
    const nav = container.querySelector("nav");
    const list = container.querySelector("ul");
    expect(nav).toBeTruthy();
    expect(list).toBeTruthy();
    // nav should come before the ul in DOM order
    const position = nav!.compareDocumentPosition(list!);
    // DOCUMENT_POSITION_FOLLOWING = 4 means list comes after nav
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
