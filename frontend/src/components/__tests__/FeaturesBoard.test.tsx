import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { FeatureBoard } from "../../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let featureBoardResult: {
  data: FeatureBoard | null;
  isLoading: boolean;
  error: Error | null;
} = { data: null, isLoading: false, error: null };

const transitionMutate = vi.fn();

vi.mock("../../hooks/useFeatures", () => ({
  useFeatureBoard: () => featureBoardResult,
  useTransitionFeatureState: () => ({ mutate: transitionMutate }),
}));

vi.mock("../FeatureForm", () => ({
  FeatureForm: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="feature-form-mock">
      <button type="button" onClick={onClose} aria-label="Cancel">
        Cancel
      </button>
    </div>
  ),
}));

vi.mock("../FeatureDetail", () => ({
  FeatureDetail: ({ featureId, onClose }: { featureId: string; onClose: () => void }) => (
    <div data-testid="feature-detail-mock" data-feature-id={featureId}>
      <button type="button" onClick={onClose} aria-label="Close detail">
        Close
      </button>
    </div>
  ),
}));

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: () => ({
    data: { spaces: [{ id: "space-1", name: "Space One", color: "#aaa", icon: null }] },
    isLoading: false,
  }),
}));

// Capture onDragEnd so tests can fire synthetic drag events.
type DragEndHandler = (e: {
  active: { id: string };
  over: { id: string } | null;
}) => void;

let capturedOnDragEnd: DragEndHandler | null = null;

vi.mock("@dnd-kit/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@dnd-kit/core")>();
  return {
    ...actual,
    DndContext: ({
      children,
      onDragEnd,
    }: {
      children: React.ReactNode;
      onDragEnd?: DragEndHandler;
      onDragStart?: (e: unknown) => void;
      onDragCancel?: () => void;
    }) => {
      capturedOnDragEnd = onDragEnd ?? null;
      return React.createElement(React.Fragment, null, children);
    },
    DragOverlay: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
  };
});

// ---------------------------------------------------------------------------
// Imports (after vi.mock)
// ---------------------------------------------------------------------------

import { FeaturesBoard } from "../FeaturesBoard";
import { FeaturesPage } from "../../pages/FeaturesPage";
import { FEATURE_LANES } from "../../types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const emptyBoard: FeatureBoard = {
  backlog: [],
  processing: [],
  planned: [],
  waiting: [],
  done: [],
};

function makeTask(id: string, title = `Task ${id}`) {
  return {
    id,
    space_id: "space-1",
    title,
    state: "backlog" as const,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    waiting_question: null,
    brief_preview: "",
    priority: 3,
    manual_order: 0,
    agent_mode: "auto" as const,
    space_name: null,
    space_color: null,
    space_icon: null,
  };
}

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false, staleTime: Infinity } },
  });
}

function renderBoard(spaceId = "space-1", initialUrl = "/features") {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <FeaturesBoard spaceId={spaceId} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderPage(route = "/features") {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter initialEntries={[route]}>
        <FeaturesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderPageScoped() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter initialEntries={["/spaces/space-1/features"]}>
        <Routes>
          <Route path="/spaces/:spaceId/features" element={<FeaturesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  featureBoardResult = { data: emptyBoard, isLoading: false, error: null };
  capturedOnDragEnd = null;
  transitionMutate.mockClear();
});

// ---------------------------------------------------------------------------
// 1. Renders 5 lanes with correct FEATURE_LANES labels
// ---------------------------------------------------------------------------

describe("FeaturesBoard — 5 lanes rendered", () => {
  it("renders all 5 feature lane headings from FEATURE_LANES", () => {
    renderBoard();
    for (const { label } of FEATURE_LANES) {
      expect(screen.getByRole("heading", { name: label })).toBeInTheDocument();
    }
  });

  it("renders Backlog, Processing, Planned, Waiting, Done (exact labels)", () => {
    renderBoard();
    expect(screen.getByRole("heading", { name: "Backlog" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Processing" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Planned" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Waiting" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Done" })).toBeInTheDocument();
  });

  it("shows loading state when useFeatureBoard is loading", () => {
    featureBoardResult = { data: null, isLoading: true, error: null };
    renderBoard();
    expect(screen.getByText(/Loading features/i)).toBeInTheDocument();
  });

  it("shows error state when useFeatureBoard errors", () => {
    featureBoardResult = { data: null, isLoading: false, error: new Error("500 Oops") };
    renderBoard();
    expect(screen.getByText(/Error: 500 Oops/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. Legal drag-end transition triggers useTransitionFeatureState mutate
// ---------------------------------------------------------------------------

describe("FeaturesBoard — legal drag-end calls mutation", () => {
  it("calls mutate on a legal transition: backlog → processing", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t1")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t1" }, over: { id: "processing" } });

    expect(transitionMutate).toHaveBeenCalledTimes(1);
    expect(transitionMutate).toHaveBeenCalledWith(
      { taskId: "t1", state: "processing" },
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    );
  });

  it("calls mutate on legal transition: planned → done", () => {
    featureBoardResult = {
      data: { ...emptyBoard, planned: [makeTask("t2")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t2" }, over: { id: "done" } });

    expect(transitionMutate).toHaveBeenCalledWith(
      { taskId: "t2", state: "done" },
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    );
  });

  it("calls mutate on legal transition: done → backlog", () => {
    featureBoardResult = {
      data: { ...emptyBoard, done: [makeTask("t3")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t3" }, over: { id: "backlog" } });

    expect(transitionMutate).toHaveBeenCalledWith(
      { taskId: "t3", state: "backlog" },
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    );
  });
});

// ---------------------------------------------------------------------------
// 3. Illegal drag-end transition does NOT call mutation
// ---------------------------------------------------------------------------

describe("FeaturesBoard — illegal drag-end guard (canFeatureTransition)", () => {
  it("does NOT call mutate for illegal transition: backlog → done", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t4")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t4" }, over: { id: "done" } });

    expect(transitionMutate).not.toHaveBeenCalled();
  });

  it("does NOT call mutate for illegal transition: processing → planned", () => {
    featureBoardResult = {
      data: { ...emptyBoard, processing: [makeTask("t5")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t5" }, over: { id: "planned" } });

    expect(transitionMutate).not.toHaveBeenCalled();
  });

  it("does NOT call mutate when over is null (dropped outside)", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t6")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t6" }, over: null });

    expect(transitionMutate).not.toHaveBeenCalled();
  });

  it("does NOT call mutate when dropping on a task id (not a lane)", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t7"), makeTask("t8")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t7" }, over: { id: "t8" } });

    expect(transitionMutate).not.toHaveBeenCalled();
  });

  it("does NOT call mutate for same-lane drop (from === to)", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t9")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t9" }, over: { id: "backlog" } });

    expect(transitionMutate).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 4. FeaturesPage — space selector and scoped rendering
// ---------------------------------------------------------------------------

describe("FeaturesPage — space selector", () => {
  it("renders a space filter dropdown on the unscoped /features route", () => {
    renderPage("/features");
    // The SpaceFilterDropdown renders a button (the trigger) visible in the toolbar
    expect(screen.getByRole("button", { name: /all spaces|space one/i })).toBeInTheDocument();
  });

  it("renders FeaturesBoard when spaces are loaded (auto-selects first space)", () => {
    featureBoardResult = { data: emptyBoard, isLoading: false, error: null };
    renderPage("/features");
    // With useSpaces mocked to return space-1, auto-select fires and board renders
    expect(screen.getByRole("heading", { name: "Backlog" })).toBeInTheDocument();
  });

  it("renders FeaturesBoard when spaceId is provided via route param", () => {
    featureBoardResult = { data: emptyBoard, isLoading: false, error: null };
    renderPageScoped();
    expect(screen.getByRole("heading", { name: "Backlog" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Processing" })).toBeInTheDocument();
  });

  it("does not render space dropdown on the scoped route", () => {
    featureBoardResult = { data: emptyBoard, isLoading: false, error: null };
    renderPageScoped();
    // Scoped page has no SpaceFilterDropdown; no "All spaces" button
    expect(screen.queryByRole("button", { name: /all spaces/i })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 5. FeaturesBoard — card click opens FeatureDetail via URL param
// ---------------------------------------------------------------------------

describe("FeaturesBoard — card click opens FeatureDetail", () => {
  it("renders FeatureDetail when URL has ?feature=<id>", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t10", "My Feature")] },
      isLoading: false,
      error: null,
    };
    renderBoard("space-1", "/features?feature=t10");
    expect(screen.getByTestId("feature-detail-mock")).toBeInTheDocument();
    expect(screen.getByTestId("feature-detail-mock").getAttribute("data-feature-id")).toBe("t10");
  });

  it("does NOT render FeatureDetail when URL has no ?feature param", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t11", "Another Feature")] },
      isLoading: false,
      error: null,
    };
    renderBoard("space-1", "/features");
    expect(screen.queryByTestId("feature-detail-mock")).not.toBeInTheDocument();
  });

  it("clicking a card sets ?feature=<id> in URL and renders FeatureDetail", async () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t12", "Clickable Feature")] },
      isLoading: false,
      error: null,
    };
    renderBoard("space-1", "/features");

    expect(screen.queryByTestId("feature-detail-mock")).not.toBeInTheDocument();

    const user = userEvent.setup();
    const card = screen.getByText("Clickable Feature").closest('[role="button"]');
    expect(card).toBeTruthy();
    await user.click(card!);

    expect(screen.getByTestId("feature-detail-mock")).toBeInTheDocument();
    expect(screen.getByTestId("feature-detail-mock").getAttribute("data-feature-id")).toBe("t12");
  });

  it("closing the FeatureDetail removes it from the DOM", async () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t13", "Closeable Feature")] },
      isLoading: false,
      error: null,
    };
    renderBoard("space-1", "/features?feature=t13");

    expect(screen.getByTestId("feature-detail-mock")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Close detail" }));

    expect(screen.queryByTestId("feature-detail-mock")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 6. Toast feedback for drag-end transitions
// ---------------------------------------------------------------------------

describe("FeaturesBoard — toast feedback on drag-end", () => {
  it("shows a success toast when mutate onSuccess fires", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t20")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t20" }, over: { id: "processing" } });

    const callbacks = transitionMutate.mock.calls[0][1] as {
      onSuccess: () => void;
      onError: (err: Error) => void;
    };
    act(() => { callbacks.onSuccess(); });

    expect(screen.getByRole("alert")).toHaveTextContent("Feature moved to Processing");
  });

  it("shows a 409 error toast when mutate onError fires with a 409 message", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t21")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t21" }, over: { id: "processing" } });

    const callbacks = transitionMutate.mock.calls[0][1] as {
      onSuccess: () => void;
      onError: (err: Error) => void;
    };
    act(() => { callbacks.onError(new Error("409 Conflict: {\"detail\":\"illegal transition\"}")); });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Cannot move to Processing from current state",
    );
  });

  it("shows a generic error toast when mutate onError fires with a non-409 error", () => {
    featureBoardResult = {
      data: { ...emptyBoard, backlog: [makeTask("t22")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t22" }, over: { id: "processing" } });

    const callbacks = transitionMutate.mock.calls[0][1] as {
      onSuccess: () => void;
      onError: (err: Error) => void;
    };
    act(() => { callbacks.onError(new Error("500 Internal Server Error")); });

    expect(screen.getByRole("alert")).toHaveTextContent("Failed to update feature state");
  });
});

// ---------------------------------------------------------------------------
// 7. FeaturesBoard — FeatureForm modal open/close
// ---------------------------------------------------------------------------

describe("FeaturesBoard — FeatureForm modal", () => {
  it("FeatureForm modal is not shown initially", () => {
    featureBoardResult = { data: emptyBoard, isLoading: false, error: null };
    renderBoard();
    expect(screen.queryByTestId("feature-form-mock")).not.toBeInTheDocument();
  });

  it("clicking the New task button on the Backlog lane opens FeatureForm modal", async () => {
    featureBoardResult = { data: emptyBoard, isLoading: false, error: null };
    renderBoard();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "New task" }));
    expect(screen.getByTestId("feature-form-mock")).toBeInTheDocument();
  });

  it("clicking Cancel in FeatureForm closes the modal", async () => {
    featureBoardResult = { data: emptyBoard, isLoading: false, error: null };
    renderBoard();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "New task" }));
    expect(screen.getByTestId("feature-form-mock")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByTestId("feature-form-mock")).not.toBeInTheDocument();
  });
});
