import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AutopilotMode, Space } from "../types";

// ---------------------------------------------------------------------------
// Mock hooks consumed by SpaceSettingsPage. The AutopilotPanel only needs
// useSpace() to return the current space and useUpdateSpace().mutateAsync to
// be a spy we can assert on.
// ---------------------------------------------------------------------------

let currentSpace: Space | null = null;
const updateMutateAsync = vi.fn().mockResolvedValue(undefined);
let updatePending = false;
let updateError: Error | null = null;

vi.mock("../hooks/useSpaces", () => ({
  useSpace: () => ({ data: currentSpace, isLoading: false }),
  useUpdateSpace: () => ({
    mutateAsync: updateMutateAsync,
    isPending: updatePending,
    error: updateError,
  }),
  useDeleteSpace: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }),
  useLinkSpaceRepo: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }),
  useUnlinkSpaceRepo: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }),
  useImportSpace: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }),
}));

// SpaceForm is a heavy form; we don't need its internals to test the autopilot
// panel — render it as a stub that just shows the rightSlot (where the
// AutopilotPanel lives).
vi.mock("../components/spaces/SpaceForm", () => ({
  SpaceForm: ({ rightSlot }: { rightSlot?: React.ReactNode }) => (
    <div data-testid="space-form-stub">{rightSlot}</div>
  ),
}));

vi.mock("../api", () => ({
  api: {
    exportSpace: vi.fn(),
  },
}));

// Import AFTER vi.mock so the mocks resolve.
import { SpaceSettingsPage } from "../pages/SpaceSettingsPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSpace(overrides: Partial<Space> = {}): Space {
  return {
    id: "space-1",
    name: "Demo Space",
    color: "#15803D",
    icon: null,
    description: "",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    git_repo_url: null,
    git_branch: null,
    git_share_cronos: false,
    agent_defaults: {},
    autopilot: "disabled",
    ...overrides,
  };
}

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/spaces/space-1/settings"]}>
        <Routes>
          <Route path="/spaces/:spaceId/settings" element={<SpaceSettingsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  updateMutateAsync.mockClear();
  updatePending = false;
  updateError = null;
  currentSpace = makeSpace();
});

// ---------------------------------------------------------------------------
// AutopilotPanel — visible structure
// ---------------------------------------------------------------------------

describe("SpaceSettingsPage — AutopilotPanel structure", () => {
  it("renders the Autopilot heading", () => {
    currentSpace = makeSpace({ autopilot: "disabled" });
    renderPage();
    expect(screen.getByText("Autopilot")).toBeInTheDocument();
  });

  it("renders all three options: Disabled, Enabled, Paused", () => {
    currentSpace = makeSpace();
    renderPage();
    expect(screen.getByRole("button", { name: "Disabled" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enabled" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Paused" })).toBeInTheDocument();
  });

  it("marks 'Disabled' active when space.autopilot === 'disabled'", () => {
    currentSpace = makeSpace({ autopilot: "disabled" });
    renderPage();
    const btn = screen.getByRole("button", { name: "Disabled" });
    // The active button gets `bg-accent text-canvas`; inactive ones use bg-surface-2.
    expect(btn.className).toContain("bg-accent");
    expect(screen.getByRole("button", { name: "Enabled" }).className).not.toContain("bg-accent");
    expect(screen.getByRole("button", { name: "Paused" }).className).not.toContain("bg-accent");
  });

  it("marks 'Enabled' active when space.autopilot === 'enabled'", () => {
    currentSpace = makeSpace({ autopilot: "enabled" });
    renderPage();
    expect(screen.getByRole("button", { name: "Enabled" }).className).toContain("bg-accent");
    expect(screen.getByRole("button", { name: "Disabled" }).className).not.toContain("bg-accent");
  });

  it("marks 'Paused' active when space.autopilot === 'paused'", () => {
    currentSpace = makeSpace({ autopilot: "paused" });
    renderPage();
    expect(screen.getByRole("button", { name: "Paused" }).className).toContain("bg-accent");
    expect(screen.getByRole("button", { name: "Disabled" }).className).not.toContain("bg-accent");
  });

  it("falls back to 'Disabled' active when space.autopilot is missing (undefined)", () => {
    // Simulate a space coming from an older serializer that omits autopilot.
    currentSpace = makeSpace({ autopilot: undefined as unknown as AutopilotMode });
    renderPage();
    expect(screen.getByRole("button", { name: "Disabled" }).className).toContain("bg-accent");
  });
});

// ---------------------------------------------------------------------------
// AutopilotPanel — click → mutation
// ---------------------------------------------------------------------------

describe("SpaceSettingsPage — AutopilotPanel mutation behavior", () => {
  it("clicking 'Enabled' from a disabled space calls mutateAsync with {autopilot:'enabled'}", async () => {
    currentSpace = makeSpace({ autopilot: "disabled" });
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Enabled" }));
    expect(updateMutateAsync).toHaveBeenCalledTimes(1);
    expect(updateMutateAsync).toHaveBeenCalledWith({ autopilot: "enabled" });
  });

  it("clicking 'Paused' from an enabled space calls mutateAsync with {autopilot:'paused'}", async () => {
    currentSpace = makeSpace({ autopilot: "enabled" });
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Paused" }));
    expect(updateMutateAsync).toHaveBeenCalledTimes(1);
    expect(updateMutateAsync).toHaveBeenCalledWith({ autopilot: "paused" });
  });

  it("clicking 'Disabled' from a paused space calls mutateAsync with {autopilot:'disabled'}", async () => {
    currentSpace = makeSpace({ autopilot: "paused" });
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Disabled" }));
    expect(updateMutateAsync).toHaveBeenCalledTimes(1);
    expect(updateMutateAsync).toHaveBeenCalledWith({ autopilot: "disabled" });
  });

  it("clicking the currently-active option is a no-op (no mutation)", async () => {
    currentSpace = makeSpace({ autopilot: "enabled" });
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Enabled" }));
    expect(updateMutateAsync).not.toHaveBeenCalled();
  });

  it("buttons are disabled while the mutation is pending", () => {
    currentSpace = makeSpace({ autopilot: "disabled" });
    updatePending = true;
    renderPage();
    expect(screen.getByRole("button", { name: "Disabled" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Enabled" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Paused" })).toBeDisabled();
  });

  it("clicking a disabled (pending) button does NOT call mutateAsync", async () => {
    currentSpace = makeSpace({ autopilot: "disabled" });
    updatePending = true;
    renderPage();
    const user = userEvent.setup();
    // userEvent respects the disabled attribute and won't fire the click.
    await user.click(screen.getByRole("button", { name: "Enabled" }));
    expect(updateMutateAsync).not.toHaveBeenCalled();
  });

  it("renders the mutation error message when updateSpace.error is set", () => {
    currentSpace = makeSpace({ autopilot: "disabled" });
    updateError = new Error("server exploded");
    renderPage();
    expect(screen.getByText("server exploded")).toBeInTheDocument();
  });

  it("does NOT render any error message when updateSpace.error is null", () => {
    currentSpace = makeSpace({ autopilot: "disabled" });
    updateError = null;
    renderPage();
    expect(screen.queryByText(/exploded/)).not.toBeInTheDocument();
  });
});
