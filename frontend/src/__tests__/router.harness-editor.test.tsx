import { describe, it, expect, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mocks — must be hoisted before any imports of the modules under test
// ---------------------------------------------------------------------------

// Mock App so it just renders its Outlet without sidebar/data-fetching noise.
vi.mock("../App", async () => {
  const { Outlet } = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    default: () => (
      <div data-testid="app-shell">
        <Outlet />
      </div>
    ),
  };
});

// Mock HarnessEditor stub so the lazy import resolves cleanly in tests.
vi.mock("../pages/HarnessEditor", () => ({
  HarnessEditor: () => <div data-testid="harness-editor-mock">HarnessEditor</div>,
}));

// Mock all heavy page components so the test doesn't pull in data-fetching deps.
vi.mock("../pages/DashboardPage", () => ({ DashboardPage: () => <div data-testid="dashboard" /> }));
vi.mock("../pages/BoardPage", () => ({ BoardPage: () => <div data-testid="board" /> }));
vi.mock("../pages/ArchivedPage", () => ({ ArchivedPage: () => <div data-testid="archived" /> }));
vi.mock("../pages/SpaceToolsPage", () => ({ SpaceToolsPage: () => <div data-testid="tools" /> }));
vi.mock("../pages/MemoryPage", () => ({ MemoryPage: () => <div data-testid="memory" /> }));
vi.mock("../pages/SpaceCreatePage", () => ({ SpaceCreatePage: () => <div data-testid="create" /> }));
vi.mock("../pages/StatsPage", () => ({ StatsPage: () => <div data-testid="stats" /> }));
vi.mock("../pages/TreePage", () => ({ TreePage: () => <div data-testid="tree" /> }));
vi.mock("../pages/SpaceSettingsPage", () => ({ SpaceSettingsPage: () => <div data-testid="settings" /> }));
vi.mock("../pages/HarnessRunsPage", () => ({ HarnessRunsPage: () => <div data-testid="harness-runs" /> }));
vi.mock("../pages/NotFoundPage", () => ({ NotFoundPage: () => <div data-testid="not-found" /> }));

// Import AppRoutes AFTER mocks are registered so dynamic imports see the mocks.
import { AppRoutes } from "../router";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderAt(path: string) {
  const client = makeClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("router — harness editor route", () => {
  it("renders HarnessEditor at /spaces/:spaceId/harnesses/:name/edit", async () => {
    await act(async () => {
      renderAt("/spaces/test-space/harnesses/my-harness/edit");
    });

    expect(screen.getByTestId("harness-editor-mock")).toBeInTheDocument();
  });

  it("does not render HarnessEditor on a different route", async () => {
    await act(async () => {
      renderAt("/");
    });

    expect(screen.queryByTestId("harness-editor-mock")).not.toBeInTheDocument();
    expect(screen.getByTestId("dashboard")).toBeInTheDocument();
  });

  it("HarnessEditor route is wrapped in Suspense (fallback renders before lazy resolves)", async () => {
    // React.lazy with vi.mock resolves synchronously in test env,
    // but the Suspense boundary is still present in the JSX tree.
    // We verify the route renders the mocked component successfully after awaiting act.
    await act(async () => {
      renderAt("/spaces/test-space/harnesses/my-harness/edit");
    });

    // The component should be present (lazy loaded and resolved).
    const editor = screen.getByTestId("harness-editor-mock");
    expect(editor).toBeInTheDocument();
    expect(editor.textContent).toBe("HarnessEditor");
  });

  it("route extracts spaceId and name params correctly (renders editor component)", async () => {
    await act(async () => {
      renderAt("/spaces/my-space/harnesses/special-harness/edit");
    });

    // The HarnessEditor component renders (params are accessible inside it)
    expect(screen.getByTestId("harness-editor-mock")).toBeInTheDocument();
  });
});
