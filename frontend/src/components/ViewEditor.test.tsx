/**
 * ViewEditor — I6 migration tests.
 *
 * Verifies that the delete-confirm dialog is rendered via Modal.tsx (not an
 * ad-hoc scrim div) and that the main form modal continues to work correctly
 * after the migration.
 *
 * Covers:
 * 1. Main form modal renders and form fields accept input (regression)
 * 2. Delete confirm dialog opens when delete action is triggered
 * 3. Delete confirm dialog closes on Escape (Modal.tsx handles it)
 * 4. Delete confirm dialog closes on Cancel button
 * 5. Confirming delete calls the delete handler
 * 6. Form fields inside the main modal still accept text input (focus-trap regression)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { View } from "../types";

// ---------------------------------------------------------------------------
// Mock the api module BEFORE importing modules that use it.
// ---------------------------------------------------------------------------

const spaceViewsMock = vi.fn();
const createViewMock = vi.fn();
const updateViewMock = vi.fn();
const deleteViewMock = vi.fn();

vi.mock("../api", () => ({
  api: {
    spaceViews: (spaceId: string) => spaceViewsMock(spaceId),
    createView: (spaceId: string, body: Record<string, unknown>) =>
      createViewMock(spaceId, body),
    updateView: (
      spaceId: string,
      viewId: string,
      body: Record<string, unknown>,
    ) => updateViewMock(spaceId, viewId, body),
    deleteView: (spaceId: string, viewId: string) =>
      deleteViewMock(spaceId, viewId),
  },
}));

// Import after vi.mock so mocks apply.
import { ViewEditor } from "./ViewEditor";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const VIEW_A: View = {
  id: "view-a",
  name: "All lanes",
  lanes: ["backlog", "active", "waiting", "done"],
  type_filter: null,
  default: true,
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
};

const VIEW_B: View = {
  id: "view-b",
  name: "Focus",
  lanes: ["active", "waiting"],
  type_filter: ["task"],
  default: false,
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
};

const SAMPLE_VIEWS = [VIEW_A, VIEW_B];

function makeClient(views: View[] = SAMPLE_VIEWS) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
  // Pre-seed the cache to avoid render loops caused by useViews returning a
  // new [] reference on every render while the query is loading.
  client.setQueryData(["views", "space-1"], views);
  return client;
}

function renderEditor(
  overrides: Partial<Parameters<typeof ViewEditor>[0]> = {},
  views: View[] = SAMPLE_VIEWS,
) {
  spaceViewsMock.mockResolvedValue(views);
  const onClose = vi.fn();
  const onViewChange = vi.fn();
  const client = makeClient(views);
  const utils = render(
    <QueryClientProvider client={client}>
      <ViewEditor
        spaceId="space-1"
        currentViewId={VIEW_A.id}
        onClose={onClose}
        onViewChange={onViewChange}
        {...overrides}
      />
    </QueryClientProvider>,
  );
  return { ...utils, onClose, onViewChange };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

// ---------------------------------------------------------------------------
// 1 & 6. Main form modal renders and form fields accept input (regression)
// ---------------------------------------------------------------------------

describe("ViewEditor — main form modal regression", () => {
  it("renders the main modal with the view list", async () => {
    renderEditor();
    expect(
      await screen.findByRole("dialog", { name: /Manage views/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText("All lanes")).toBeInTheDocument();
    expect(await screen.findByText("Focus")).toBeInTheDocument();
  });

  it("form name input accepts text input (focus-trap regression)", async () => {
    renderEditor();
    const nameInput = await screen.findByPlaceholderText("View name");
    // Simulate a change event to verify the input accepts input (regression
    // check that Modal.tsx's focus trap does not block input from being updated).
    fireEvent.change(nameInput, { target: { value: "Renamed view" } });
    expect(nameInput).toHaveValue("Renamed view");
  });

  it("renders Save and Cancel buttons inside the main modal", async () => {
    renderEditor();
    await screen.findByPlaceholderText("View name");
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. Delete confirm dialog opens
// ---------------------------------------------------------------------------

describe("ViewEditor — delete confirm dialog opens", () => {
  it("opens the delete confirm dialog when delete icon is clicked", async () => {
    const user = userEvent.setup();
    renderEditor();
    await screen.findByDisplayValue("All lanes");

    // VIEW_B's delete button (index 1 — second row)
    const deleteButtons = screen.getAllByRole("button", { name: /Delete view/i });
    await user.click(deleteButtons[1]);

    expect(
      await screen.findByRole("alertdialog", { name: /Confirm delete/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/permanently removed/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 3. Delete confirm dialog closes on Escape (Modal.tsx handles it)
// ---------------------------------------------------------------------------

describe("ViewEditor — delete confirm dialog Escape", () => {
  it("closes the delete confirm dialog when Escape is pressed", async () => {
    const user = userEvent.setup();
    renderEditor();
    await screen.findByDisplayValue("All lanes");

    const deleteButtons = screen.getAllByRole("button", { name: /Delete view/i });
    await user.click(deleteButtons[1]);

    expect(
      await screen.findByRole("alertdialog", { name: /Confirm delete/i }),
    ).toBeInTheDocument();

    // Modal.tsx handles Escape via document.addEventListener
    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(
        screen.queryByRole("alertdialog", { name: /Confirm delete/i }),
      ).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// 4. Delete confirm dialog closes on Cancel button
// ---------------------------------------------------------------------------

describe("ViewEditor — delete confirm dialog Cancel", () => {
  it("closes the delete confirm dialog without calling deleteView", async () => {
    const user = userEvent.setup();
    renderEditor();
    await screen.findByDisplayValue("All lanes");

    const deleteButtons = screen.getAllByRole("button", { name: /Delete view/i });
    await user.click(deleteButtons[1]);

    const alertDialog = await screen.findByRole("alertdialog", {
      name: /Confirm delete/i,
    });

    await user.click(within(alertDialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => {
      expect(
        screen.queryByRole("alertdialog", { name: /Confirm delete/i }),
      ).not.toBeInTheDocument();
    });
    expect(deleteViewMock).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 5. Confirming delete calls the delete handler
// ---------------------------------------------------------------------------

describe("ViewEditor — delete confirm dialog Delete", () => {
  it("calls deleteView.mutateAsync when Delete button is confirmed", async () => {
    deleteViewMock.mockResolvedValue(undefined);
    spaceViewsMock
      .mockResolvedValueOnce(SAMPLE_VIEWS)
      .mockResolvedValue([VIEW_A]);

    const user = userEvent.setup();
    renderEditor();
    await screen.findByDisplayValue("All lanes");

    const deleteButtons = screen.getAllByRole("button", { name: /Delete view/i });
    await user.click(deleteButtons[1]);

    const alertDialog = await screen.findByRole("alertdialog", {
      name: /Confirm delete/i,
    });

    await user.click(within(alertDialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteViewMock).toHaveBeenCalledTimes(1));
    expect(deleteViewMock).toHaveBeenCalledWith("space-1", VIEW_B.id);
  });
});
