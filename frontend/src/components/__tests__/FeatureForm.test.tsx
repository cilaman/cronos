import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const createMutate = vi.fn();
let mockCreateResult = {
  mutate: createMutate,
  isPending: false,
  error: null as Error | null,
};

vi.mock("../../hooks/useFeatures", () => ({
  useCreateFeature: () => mockCreateResult,
}));

// ---------------------------------------------------------------------------
// Imports (after vi.mock)
// ---------------------------------------------------------------------------

import { FeatureForm } from "../FeatureForm";

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false, staleTime: Infinity } },
  });
}

function renderForm(spaceId = "space-1", onClose = vi.fn()) {
  return {
    onClose,
    ...render(
      <QueryClientProvider client={makeQC()}>
        <MemoryRouter>
          <FeatureForm spaceId={spaceId} onClose={onClose} />
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  createMutate.mockClear();
  mockCreateResult = { mutate: createMutate, isPending: false, error: null };
});

// ---------------------------------------------------------------------------
// 1. Initial render
// ---------------------------------------------------------------------------

describe("FeatureForm — initial render", () => {
  it("renders a title input", () => {
    renderForm();
    // Both title input and brief textarea are textboxes; query by accessible name
    expect(screen.getByRole("textbox", { name: "Title" })).toBeInTheDocument();
  });

  it("renders Feature and Fix type toggle buttons", () => {
    renderForm();
    // Buttons inside FormField <label> get composite accessible names due to ARIA algorithm.
    // "Feature" btn (first in label) gets name "Type Fix"; use text query instead.
    const allButtons = screen.getAllByRole("button");
    expect(allButtons.some((b) => b.textContent?.trim() === "Feature")).toBe(true);
    expect(allButtons.some((b) => b.textContent?.trim() === "Fix")).toBe(true);
  });

  it("renders priority buttons P1 through P5", () => {
    renderForm();
    // First priority button in FormField label gets a composite accessible name;
    // match by text content to avoid ARIA quirk.
    const allButtons = screen.getAllByRole("button");
    for (const label of ["P1", "P2", "P3", "P4", "P5"]) {
      expect(allButtons.some((b) => b.textContent?.trim() === label)).toBe(true);
    }
  });

  it("submit button is disabled when title is empty", () => {
    renderForm();
    expect(screen.getByRole("button", { name: "Add Feature" })).toBeDisabled();
  });

  it("heading defaults to 'New Feature'", () => {
    renderForm();
    // CSS text-transform does not affect the DOM accessible name
    expect(screen.getByRole("heading", { name: "New Feature" })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. Type toggle
// ---------------------------------------------------------------------------

describe("FeatureForm — type toggle", () => {
  it("clicking Fix changes heading to 'New Fix'", async () => {
    renderForm();
    const user = userEvent.setup();
    // "Fix" is the second button in the Type FormField label → accessible name "Fix"
    await user.click(screen.getByRole("button", { name: "Fix" }));
    expect(screen.getByRole("heading", { name: "New Fix" })).toBeInTheDocument();
  });

  it("clicking Fix changes submit button label to 'Add Fix'", async () => {
    renderForm();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Fix" }));
    expect(screen.getByRole("button", { name: "Add Fix" })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 3. Form submission
// ---------------------------------------------------------------------------

describe("FeatureForm — form submission", () => {
  it("submit button enabled after typing a title", async () => {
    renderForm();
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox", { name: "Title" }), "My feature");
    expect(screen.getByRole("button", { name: "Add Feature" })).not.toBeDisabled();
  });

  it("calls mutate with correct payload on submit (default type=feature, priority=3)", async () => {
    renderForm();
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox", { name: "Title" }), "My feature");
    await user.click(screen.getByRole("button", { name: "Add Feature" }));
    expect(createMutate).toHaveBeenCalledWith(
      expect.objectContaining({ title: "My feature", type: "feature", priority: 3 }),
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("calls mutate with type=fix when Fix type is selected", async () => {
    renderForm();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Fix" }));
    await user.type(screen.getByRole("textbox", { name: "Title" }), "A bug fix");
    await user.click(screen.getByRole("button", { name: "Add Fix" }));
    expect(createMutate).toHaveBeenCalledWith(
      expect.objectContaining({ title: "A bug fix", type: "fix", priority: 3 }),
      expect.any(Object),
    );
  });

  it("calls mutate with priority=1 after clicking P1", async () => {
    renderForm();
    const user = userEvent.setup();
    // P1 is the first button in Priority FormField label → gets composite accessible name.
    // Find it by text content and click directly.
    const p1Btn = screen.getAllByRole("button").find((b) => b.textContent?.trim() === "P1");
    expect(p1Btn).toBeDefined();
    await user.click(p1Btn!);
    await user.type(screen.getByRole("textbox", { name: "Title" }), "Urgent feature");
    await user.click(screen.getByRole("button", { name: "Add Feature" }));
    expect(createMutate).toHaveBeenCalledWith(
      expect.objectContaining({ priority: 1 }),
      expect.any(Object),
    );
  });

  it("calls onClose when mutate onSuccess fires", async () => {
    const { onClose } = renderForm();
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox", { name: "Title" }), "My feature");
    await user.click(screen.getByRole("button", { name: "Add Feature" }));
    const [, callbacks] = createMutate.mock.calls[0] as [unknown, { onSuccess: () => void }];
    act(() => {
      callbacks.onSuccess();
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not call mutate when title is blank (only whitespace)", async () => {
    renderForm();
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox", { name: "Title" }), "   ");
    // Submit stays disabled when trimmed title is empty
    expect(screen.getByRole("button", { name: "Add Feature" })).toBeDisabled();
    expect(createMutate).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 4. Error display
// ---------------------------------------------------------------------------

describe("FeatureForm — error display", () => {
  it("shows error message when mutation has an error", () => {
    mockCreateResult = {
      mutate: createMutate,
      isPending: false,
      error: new Error("Space must be linked."),
    };
    renderForm();
    expect(screen.getByText("Space must be linked.")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 5. Escape key and Cancel
// ---------------------------------------------------------------------------

describe("FeatureForm — close behavior", () => {
  it("pressing Escape calls onClose", async () => {
    const { onClose } = renderForm();
    const user = userEvent.setup();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clicking Cancel button calls onClose", async () => {
    const { onClose } = renderForm();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clicking the × close button calls onClose", async () => {
    const { onClose } = renderForm();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
