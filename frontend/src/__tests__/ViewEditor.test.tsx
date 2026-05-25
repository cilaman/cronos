import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within, act } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { View } from "../types";

// ---------------------------------------------------------------------------
// Mock the api module BEFORE importing modules that close over `api`.
// ---------------------------------------------------------------------------

const spaceViewsMock = vi.fn();
const createViewMock = vi.fn();
const updateViewMock = vi.fn();
const deleteViewMock = vi.fn();

vi.mock("../api", () => ({
  api: {
    spaceViews: (spaceId: string) => spaceViewsMock(spaceId),
    createView: (
      spaceId: string,
      body: Record<string, unknown>,
    ) => createViewMock(spaceId, body),
    updateView: (
      spaceId: string,
      viewId: string,
      body: Record<string, unknown>,
    ) => updateViewMock(spaceId, viewId, body),
    deleteView: (spaceId: string, viewId: string) =>
      deleteViewMock(spaceId, viewId),
  },
}));

// Import after vi.mock so the mocks apply.
import { ViewEditor } from "../components/ViewEditor";
import {
  useCreateView,
  useDeleteView,
  useUpdateView,
} from "../hooks/useViews";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const DEFAULT_VIEW: View = {
  id: "all",
  name: "All lanes",
  lanes: ["backlog", "active", "waiting", "done"],
  type_filter: null,
  default: true,
  created_at: "2026-05-25T00:00:00Z",
  updated_at: "2026-05-25T00:00:00Z",
};

const FOCUS_VIEW: View = {
  id: "focus",
  name: "Focus",
  lanes: ["active", "waiting"],
  type_filter: ["task"],
  default: false,
  created_at: "2026-05-25T00:00:00Z",
  updated_at: "2026-05-25T00:00:00Z",
};

const BACKLOG_VIEW: View = {
  id: "backlog-only",
  name: "Backlog only",
  lanes: ["backlog"],
  type_filter: ["task", "goal"],
  default: false,
  created_at: "2026-05-25T00:00:00Z",
  updated_at: "2026-05-25T00:00:00Z",
};

const SAMPLE_VIEWS: View[] = [DEFAULT_VIEW, FOCUS_VIEW, BACKLOG_VIEW];

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
}

function renderEditor(
  partial: Partial<Parameters<typeof ViewEditor>[0]> = {},
  views: View[] = SAMPLE_VIEWS,
) {
  spaceViewsMock.mockResolvedValue(views);
  const props = {
    spaceId: "space-1",
    currentViewId: null,
    onClose: vi.fn(),
    onViewChange: vi.fn(),
    ...partial,
  };
  const client = makeClient();
  // Pre-seed the ["views", spaceId] cache so useQuery returns a stable
  // (non-undefined) data reference on first render. Without this, the
  // ViewEditor's `useEffect([selectedId, views])` re-fires every render
  // (the default `views = []` from destructuring is a new array each time)
  // and the effect calls setFormRaw, producing a render loop.
  client.setQueryData(["views", props.spaceId], views);
  const utils = render(
    <QueryClientProvider client={client}>
      <ViewEditor {...props} />
    </QueryClientProvider>,
  );
  return { ...utils, props, client };
}

/** Returns the form-pane region (the right-hand pane), excluding the view list. */
function getFormPane(): HTMLElement {
  // The dialog root contains both panes; "Edit view" / "New view" appears as the
  // form's h2. Walk up to the closest pane container.
  const heading = screen.getByRole("heading", {
    name: /^(Edit view|New view)$/,
  });
  return heading.closest("div.flex.min-w-0")! as HTMLElement;
}

// ---------------------------------------------------------------------------
// ViewEditor — rendering & selection
// ---------------------------------------------------------------------------

describe("ViewEditor — rendering & selection", () => {
  beforeEach(() => {
    spaceViewsMock.mockReset();
    createViewMock.mockReset();
    updateViewMock.mockReset();
    deleteViewMock.mockReset();
  });

  it("renders the modal with the view list populated from useViews data", async () => {
    renderEditor();

    // The dialog itself.
    expect(
      await screen.findByRole("dialog", { name: /Manage views/i }),
    ).toBeInTheDocument();

    // Each view name appears in the left pane.
    for (const v of SAMPLE_VIEWS) {
      expect(await screen.findByText(v.name)).toBeInTheDocument();
    }
  });

  it("lazy-initialises selection to the default view when views load", async () => {
    renderEditor({ currentViewId: "focus" });

    // After the views resolve, the form should show the DEFAULT view ("All
    // lanes") — not the currently-active board view ("focus"). The init
    // effect prefers v.default.
    const form = await screen.findByDisplayValue("All lanes");
    expect(form).toBeInTheDocument();
    // Header should read "Edit view" (not "New view").
    expect(
      screen.getByRole("heading", { name: "Edit view" }),
    ).toBeInTheDocument();
  });

  it("selecting a view loads its values into the form", async () => {
    renderEditor();
    const user = userEvent.setup();

    // Wait for the initial selection to settle on the default.
    await screen.findByDisplayValue("All lanes");

    // Act — click the "Focus" row in the left pane.
    await user.click(screen.getByText("Focus"));

    // Name input reflects Focus.
    expect(await screen.findByDisplayValue("Focus")).toBeInTheDocument();

    // The Focus view has lanes ["active","waiting"] and type_filter ["task"].
    // In the form, the lane checkboxes use labels "To Do", "Active",
    // "Waiting", "Done" (declared in LANE_OPTS).
    const form = getFormPane();
    const lanesCheckboxes = within(form)
      .getAllByRole("checkbox")
      .filter((c) => {
        const label = c.closest("label")?.textContent ?? "";
        return ["To Do", "Active", "Waiting", "Done"].includes(label.trim());
      });
    const byLabel = Object.fromEntries(
      lanesCheckboxes.map((c) => [c.closest("label")!.textContent!.trim(), c]),
    );
    expect((byLabel["To Do"] as HTMLInputElement).checked).toBe(false);
    expect((byLabel["Active"] as HTMLInputElement).checked).toBe(true);
    expect((byLabel["Waiting"] as HTMLInputElement).checked).toBe(true);
    expect((byLabel["Done"] as HTMLInputElement).checked).toBe(false);

    // type_filter is ["task"] → "All types" unchecked, "Task" checked,
    // "Goal"/"Issue" unchecked.
    const allTypes = within(form).getByLabelText(/^All types$/);
    const taskCb = within(form).getByLabelText(/^Task$/);
    const goalCb = within(form).getByLabelText(/^Goal$/);
    const issueCb = within(form).getByLabelText(/^Issue$/);
    expect((allTypes as HTMLInputElement).checked).toBe(false);
    expect((taskCb as HTMLInputElement).checked).toBe(true);
    expect((goalCb as HTMLInputElement).checked).toBe(false);
    expect((issueCb as HTMLInputElement).checked).toBe(false);
  });

  it("'+ New view' button switches to a blank form with all lanes selected and no type filter", async () => {
    renderEditor();
    const user = userEvent.setup();
    await screen.findByDisplayValue("All lanes");

    // Act — click "New view" in the left-pane header.
    await user.click(screen.getByRole("button", { name: /New view/i }));

    // Header now reads "New view".
    expect(
      await screen.findByRole("heading", { name: "New view" }),
    ).toBeInTheDocument();

    // Name input is empty.
    const form = getFormPane();
    const nameInput = within(form).getByPlaceholderText(
      "View name",
    ) as HTMLInputElement;
    expect(nameInput.value).toBe("");

    // All four lane checkboxes are checked.
    for (const label of ["To Do", "Active", "Waiting", "Done"]) {
      const cb = within(form).getByLabelText(new RegExp(`^${label}$`));
      expect((cb as HTMLInputElement).checked).toBe(true);
    }

    // "All types" is checked, the type sub-rows are NOT rendered.
    expect(
      (within(form).getByLabelText(/^All types$/) as HTMLInputElement).checked,
    ).toBe(true);
    expect(within(form).queryByLabelText(/^Task$/)).toBeNull();

    // Default checkbox unchecked.
    expect(
      (within(form).getByLabelText(/^Default view$/) as HTMLInputElement)
        .checked,
    ).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// ViewEditor — validation & save
// ---------------------------------------------------------------------------

describe("ViewEditor — validation & save", () => {
  beforeEach(() => {
    spaceViewsMock.mockReset();
    createViewMock.mockReset();
    updateViewMock.mockReset();
    deleteViewMock.mockReset();
  });

  it("save with blank name shows 'Name is required.' error and does not call the api", async () => {
    renderEditor();
    const user = userEvent.setup();

    // Switch to "New view" so the name is empty.
    await screen.findByDisplayValue("All lanes");
    await user.click(screen.getByRole("button", { name: /New view/i }));
    await screen.findByRole("heading", { name: "New view" });

    // Act — click Save.
    const form = getFormPane();
    await user.click(within(form).getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Name is required.")).toBeInTheDocument();
    expect(createViewMock).not.toHaveBeenCalled();
    expect(updateViewMock).not.toHaveBeenCalled();
  });

  it("save with zero lanes shows 'At least one lane must be selected.' error", async () => {
    renderEditor();
    const user = userEvent.setup();

    // Default view is loaded — uncheck every lane.
    await screen.findByDisplayValue("All lanes");
    const form = getFormPane();
    for (const label of ["To Do", "Active", "Waiting", "Done"]) {
      const cb = within(form).getByLabelText(new RegExp(`^${label}$`));
      await user.click(cb);
    }

    await user.click(within(form).getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("At least one lane must be selected."),
    ).toBeInTheDocument();
    expect(updateViewMock).not.toHaveBeenCalled();
  });

  it("save with duplicate name shows the duplicate-name error", async () => {
    renderEditor();
    const user = userEvent.setup();
    await screen.findByDisplayValue("All lanes");

    // Switch to "New view" and type the name of an existing view.
    await user.click(screen.getByRole("button", { name: /New view/i }));
    await screen.findByRole("heading", { name: "New view" });

    const form = getFormPane();
    const nameInput = within(form).getByPlaceholderText("View name");
    await user.type(nameInput, "  Focus  "); // whitespace + different case mix

    await user.click(within(form).getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText(/A view named "Focus" already exists\./),
    ).toBeInTheDocument();
    expect(createViewMock).not.toHaveBeenCalled();
  });

  it("valid save on a new view calls createView with trimmed name and clears dirty state", async () => {
    const created: View = {
      ...DEFAULT_VIEW,
      id: "new-1",
      name: "New View",
      default: false,
    };
    createViewMock.mockResolvedValue(created);
    // After creation, useViews refetches — return the new view as a list member.
    spaceViewsMock
      .mockResolvedValueOnce(SAMPLE_VIEWS)
      .mockResolvedValue([...SAMPLE_VIEWS, created]);

    renderEditor();
    const user = userEvent.setup();
    await screen.findByDisplayValue("All lanes");

    // Switch to "New view".
    await user.click(screen.getByRole("button", { name: /New view/i }));
    await screen.findByRole("heading", { name: "New view" });

    // Type the name with surrounding whitespace; save should trim it.
    const form = getFormPane();
    const nameInput = within(form).getByPlaceholderText("View name");
    await user.type(nameInput, "  New View  ");

    // Footer says "Unsaved changes" before save.
    expect(screen.getByText(/Unsaved changes/)).toBeInTheDocument();

    await user.click(within(form).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(createViewMock).toHaveBeenCalledTimes(1));
    const [, body] = createViewMock.mock.calls[0];
    expect(body).toEqual({
      name: "New View",
      lanes: ["backlog", "active", "waiting", "done"],
      type_filter: null,
      default: false,
    });

    // Dirty state cleared → "Unsaved changes" indicator gone.
    await waitFor(() => {
      expect(screen.queryByText(/Unsaved changes/)).not.toBeInTheDocument();
    });
  });

  it("valid save on an existing view calls updateView with the view id", async () => {
    const updated: View = { ...FOCUS_VIEW, name: "Focus Renamed" };
    updateViewMock.mockResolvedValue(updated);

    renderEditor();
    const user = userEvent.setup();
    await screen.findByDisplayValue("All lanes");

    // Select Focus.
    await user.click(screen.getByText("Focus"));
    await screen.findByDisplayValue("Focus");

    const form = getFormPane();
    const nameInput = within(form).getByPlaceholderText("View name");
    await user.clear(nameInput);
    await user.type(nameInput, "Focus Renamed");

    await user.click(within(form).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(updateViewMock).toHaveBeenCalledTimes(1));
    const [, viewId, body] = updateViewMock.mock.calls[0];
    expect(viewId).toBe("focus");
    expect(body.name).toBe("Focus Renamed");
    expect(body.lanes).toEqual(["active", "waiting"]);
    expect(body.type_filter).toEqual(["task"]);
    expect(body.default).toBe(false);

    // createView should NOT have been called for an existing view.
    expect(createViewMock).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// ViewEditor — duplicate & set default
// ---------------------------------------------------------------------------

describe("ViewEditor — duplicate & set default", () => {
  beforeEach(() => {
    spaceViewsMock.mockReset();
    createViewMock.mockReset();
    updateViewMock.mockReset();
    deleteViewMock.mockReset();
  });

  it("duplicate button calls createView with name + ' (copy)' and default: false", async () => {
    const copy: View = {
      ...FOCUS_VIEW,
      id: "focus-copy",
      name: "Focus (copy)",
      default: false,
    };
    createViewMock.mockResolvedValue(copy);

    renderEditor();
    const user = userEvent.setup();
    await screen.findByDisplayValue("All lanes");

    // Click the duplicate icon-button on the "Focus" row.
    const dupButtons = screen.getAllByRole("button", {
      name: /Duplicate view/i,
    });
    // Three rows → three duplicate buttons; the one for "Focus" is index 1.
    await user.click(dupButtons[1]);

    await waitFor(() => expect(createViewMock).toHaveBeenCalledTimes(1));
    const [, body] = createViewMock.mock.calls[0];
    expect(body).toEqual({
      name: "Focus (copy)",
      lanes: ["active", "waiting"],
      type_filter: ["task"],
      default: false,
    });
  });

  it("set-default button on a non-default view calls updateView with {default: true}", async () => {
    updateViewMock.mockResolvedValue({ ...FOCUS_VIEW, default: true });
    renderEditor();
    const user = userEvent.setup();
    await screen.findByDisplayValue("All lanes");

    // The default row has aria-label "Default view" (idempotent); non-default
    // rows have aria-label "Set as default".
    const setDefaultButtons = screen.getAllByRole("button", {
      name: /Set as default/i,
    });
    // Two non-default views (Focus, Backlog only) → two buttons.
    await user.click(setDefaultButtons[0]);

    await waitFor(() => expect(updateViewMock).toHaveBeenCalledTimes(1));
    const [, viewId, body] = updateViewMock.mock.calls[0];
    expect(viewId).toBe("focus");
    expect(body).toEqual({ default: true });
  });
});

// ---------------------------------------------------------------------------
// ViewEditor — delete
// ---------------------------------------------------------------------------

describe("ViewEditor — delete", () => {
  beforeEach(() => {
    spaceViewsMock.mockReset();
    createViewMock.mockReset();
    updateViewMock.mockReset();
    deleteViewMock.mockReset();
  });

  it("delete button is disabled when only 1 view exists", async () => {
    renderEditor({}, [DEFAULT_VIEW]);
    await screen.findByDisplayValue("All lanes");

    const deleteBtn = screen.getByRole("button", { name: /Delete view/i });
    expect(deleteBtn).toBeDisabled();
  });

  it("delete button opens confirm dialog; cancel closes it without calling deleteView", async () => {
    renderEditor();
    const user = userEvent.setup();
    await screen.findByDisplayValue("All lanes");

    const deleteButtons = screen.getAllByRole("button", {
      name: /Delete view/i,
    });
    await user.click(deleteButtons[1]); // delete Focus

    // The confirm alertdialog appears.
    const confirm = await screen.findByRole("alertdialog", {
      name: /Confirm delete/i,
    });
    expect(within(confirm).getByText(/Focus/)).toBeInTheDocument();

    // Cancel.
    await user.click(within(confirm).getByRole("button", { name: "Cancel" }));

    await waitFor(() => {
      expect(
        screen.queryByRole("alertdialog", { name: /Confirm delete/i }),
      ).not.toBeInTheDocument();
    });
    expect(deleteViewMock).not.toHaveBeenCalled();
  });

  it("confirming delete calls deleteView with the view id", async () => {
    deleteViewMock.mockResolvedValue(undefined);
    // After delete, the view list shrinks.
    spaceViewsMock
      .mockResolvedValueOnce(SAMPLE_VIEWS)
      .mockResolvedValue([DEFAULT_VIEW, BACKLOG_VIEW]);

    renderEditor();
    const user = userEvent.setup();
    await screen.findByDisplayValue("All lanes");

    const deleteButtons = screen.getAllByRole("button", {
      name: /Delete view/i,
    });
    await user.click(deleteButtons[1]); // delete Focus

    const confirm = await screen.findByRole("alertdialog", {
      name: /Confirm delete/i,
    });
    await user.click(within(confirm).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteViewMock).toHaveBeenCalledTimes(1));
    expect(deleteViewMock).toHaveBeenCalledWith("space-1", "focus");
  });

  it("after delete: onViewChange(null) is called when the deleted view was the active board view", async () => {
    deleteViewMock.mockResolvedValue(undefined);
    const onViewChange = vi.fn();
    spaceViewsMock
      .mockResolvedValueOnce(SAMPLE_VIEWS)
      .mockResolvedValue([DEFAULT_VIEW, BACKLOG_VIEW]);

    renderEditor({ currentViewId: "focus", onViewChange });
    const user = userEvent.setup();
    // Wait for initial render & init.
    await screen.findByDisplayValue("All lanes");

    const deleteButtons = screen.getAllByRole("button", {
      name: /Delete view/i,
    });
    await user.click(deleteButtons[1]); // Focus row

    const confirm = await screen.findByRole("alertdialog", {
      name: /Confirm delete/i,
    });
    await user.click(within(confirm).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(onViewChange).toHaveBeenCalledTimes(1));
    expect(onViewChange).toHaveBeenCalledWith(null);
  });

  it("after delete: onViewChange is NOT called when the deleted view is not the active board view", async () => {
    deleteViewMock.mockResolvedValue(undefined);
    const onViewChange = vi.fn();
    spaceViewsMock
      .mockResolvedValueOnce(SAMPLE_VIEWS)
      .mockResolvedValue([DEFAULT_VIEW, FOCUS_VIEW]);

    // currentViewId = "focus" but we delete the BACKLOG_ONLY view.
    renderEditor({ currentViewId: "focus", onViewChange });
    const user = userEvent.setup();
    await screen.findByDisplayValue("All lanes");

    const deleteButtons = screen.getAllByRole("button", {
      name: /Delete view/i,
    });
    await user.click(deleteButtons[2]); // Backlog only

    const confirm = await screen.findByRole("alertdialog", {
      name: /Confirm delete/i,
    });
    await user.click(within(confirm).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteViewMock).toHaveBeenCalled());
    expect(onViewChange).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// useViews — mutations invalidate ["views", spaceId] AND ["board"]
// ---------------------------------------------------------------------------

describe("useViews mutations also invalidate ['board'] queries", () => {
  beforeEach(() => {
    spaceViewsMock.mockReset();
    createViewMock.mockReset();
    updateViewMock.mockReset();
    deleteViewMock.mockReset();
  });

  function wrapper(client: QueryClient) {
    return ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client }, children);
  }

  it("useCreateView invalidates both ['views', spaceId] and ['board'] on success", async () => {
    createViewMock.mockResolvedValue({ ...DEFAULT_VIEW, id: "new" });
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateView("space-1"), {
      wrapper: wrapper(client),
    });
    result.current.mutate({
      name: "x",
      lanes: ["backlog"],
      type_filter: null,
      default: false,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const keys = invalidateSpy.mock.calls.map((c) =>
      JSON.stringify((c[0] as { queryKey: unknown }).queryKey),
    );
    expect(keys).toContain(JSON.stringify(["views", "space-1"]));
    expect(keys).toContain(JSON.stringify(["board"]));
  });

  it("useUpdateView invalidates both ['views', spaceId] and ['board'] on success", async () => {
    updateViewMock.mockResolvedValue({ ...FOCUS_VIEW, name: "Focus 2" });
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateView("space-1"), {
      wrapper: wrapper(client),
    });
    result.current.mutate({ viewId: "focus", name: "Focus 2" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const keys = invalidateSpy.mock.calls.map((c) =>
      JSON.stringify((c[0] as { queryKey: unknown }).queryKey),
    );
    expect(keys).toContain(JSON.stringify(["views", "space-1"]));
    expect(keys).toContain(JSON.stringify(["board"]));
  });

  it("useDeleteView invalidates both ['views', spaceId] and ['board'] on success", async () => {
    deleteViewMock.mockResolvedValue(undefined);
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeleteView("space-1"), {
      wrapper: wrapper(client),
    });
    result.current.mutate("focus");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const keys = invalidateSpy.mock.calls.map((c) =>
      JSON.stringify((c[0] as { queryKey: unknown }).queryKey),
    );
    expect(keys).toContain(JSON.stringify(["views", "space-1"]));
    expect(keys).toContain(JSON.stringify(["board"]));
  });

  it("useDeleteView does NOT invalidate anything if the api call fails", async () => {
    deleteViewMock.mockRejectedValue(new Error("404: not found"));
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeleteView("space-1"), {
      wrapper: wrapper(client),
    });
    result.current.mutate("focus");
    await waitFor(() => expect(result.current.isError).toBe(true));

    // The onSuccess invalidations must not fire on error.
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Defensive cleanup: jsdom carries window-level event listeners across tests.
// ViewEditor attaches a keydown handler; ensure unmount happens before the
// next test to avoid stray Esc / Cmd+S handlers firing.
// ---------------------------------------------------------------------------

afterEach(() => {
  // No-op: @testing-library/react autoCleanup handles unmount.
  // This block exists to document the constraint for future maintainers.
  void act;
});
