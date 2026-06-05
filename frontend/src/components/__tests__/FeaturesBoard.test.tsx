import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
  useCreateFeature: () => ({ mutate: vi.fn(), isPending: false }),
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

function renderBoard(spaceId = "space-1") {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
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
    expect(transitionMutate).toHaveBeenCalledWith({ taskId: "t1", state: "processing" });
  });

  it("calls mutate on legal transition: planned → done", () => {
    featureBoardResult = {
      data: { ...emptyBoard, planned: [makeTask("t2")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t2" }, over: { id: "done" } });

    expect(transitionMutate).toHaveBeenCalledWith({ taskId: "t2", state: "done" });
  });

  it("calls mutate on legal transition: done → backlog", () => {
    featureBoardResult = {
      data: { ...emptyBoard, done: [makeTask("t3")] },
      isLoading: false,
      error: null,
    };
    renderBoard();

    capturedOnDragEnd!({ active: { id: "t3" }, over: { id: "backlog" } });

    expect(transitionMutate).toHaveBeenCalledWith({ taskId: "t3", state: "backlog" });
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
// 4. null spaceId renders empty-state message (FeaturesPage without route param)
// ---------------------------------------------------------------------------

describe("FeaturesPage — null spaceId empty-state", () => {
  it("renders empty-state when no spaceId is in route or localStorage", () => {
    // jsdom localStorage is empty; no route param → effectiveSpaceId is null
    renderPage("/features");
    expect(screen.getByText(/Pick a space from the sidebar/i)).toBeInTheDocument();
  });

  it("does not render FeaturesBoard when effectiveSpaceId is null", () => {
    renderPage("/features");
    // Lanes must NOT render when there is no space
    expect(screen.queryByRole("heading", { name: "Backlog" })).not.toBeInTheDocument();
  });

  it("renders FeaturesBoard when spaceId is provided via route param", () => {
    featureBoardResult = { data: emptyBoard, isLoading: false, error: null };
    renderPageScoped();
    expect(screen.getByRole("heading", { name: "Backlog" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Processing" })).toBeInTheDocument();
  });
});
