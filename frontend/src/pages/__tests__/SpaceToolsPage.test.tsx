import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { AdoptedTool, SpaceToolsResponse, SpacesResponse } from "../../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockUnadoptMutate = vi.fn();
let mockUnadoptIsPending = false;

let mockSpaceTools: SpaceToolsResponse | undefined;
let mockSpacesResponse: SpacesResponse = { spaces: [], totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 } };

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: () => ({ data: mockSpacesResponse, isLoading: false }),
  useSpaceTools: () => ({
    data: mockSpaceTools,
    isLoading: false,
    isError: false,
  }),
  useUnadoptTool: () => ({
    mutate: mockUnadoptMutate,
    isPending: mockUnadoptIsPending,
  }),
}));

// DiscoveryPanel is not under test here — stub it out
vi.mock("../../components/DiscoveryPanel", () => ({
  DiscoveryPanel: () => <div data-testid="discovery-panel">DiscoveryPanel</div>,
}));

// ToolDetailPanel stub
vi.mock("../../components/ToolDetailPanel", () => ({
  ToolDetailPanel: () => <div data-testid="tool-detail-panel">ToolDetailPanel</div>,
}));

// PluginsPanel stub
vi.mock("../../components/PluginsPanel", () => ({
  PluginsPanel: () => <div data-testid="plugins-panel">PluginsPanel</div>,
}));

// AdoptedToolTelemetry stub — telemetry is tested separately
vi.mock("../../components/AdoptedToolTelemetry", () => ({
  AdoptedToolTelemetry: ({ name }: { name: string }) => (
    <div data-testid={`telemetry-${name}`}>Telemetry</div>
  ),
}));

import { SpaceToolsPage } from "../SpaceToolsPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeAdopted(overrides: Partial<AdoptedTool> = {}): AdoptedTool {
  return {
    source_url: "https://github.com/org/repo",
    source_slug: "github.com-org-repo",
    source_path: ".claude/agents/my-agent.md",
    source_sha: "deadbeef1234567890ab",
    adopted_at: "2026-06-01T10:00:00Z",
    base_sha: "deadbeef1234567890ab",
    local_sha: "deadbeef1234567890ab",
    evolved: false,
    kind: "agent",
    name: "my-agent",
    status: "pristine",
    ...overrides,
  };
}

function makeTools(adopted: AdoptedTool[] = []): SpaceToolsResponse {
  return {
    space_id: "space-1",
    agents: [],
    commands: [],
    skills: [],
    context_files: [],
    hooks: [],
    permissions: [],
    has_claude_md: false,
    adopted,
  };
}

function renderPage(spaceId = "space-1") {
  return render(
    <MemoryRouter initialEntries={[`/spaces/${spaceId}/tools`]}>
      <Routes>
        <Route path="/spaces/:spaceId/tools" element={<SpaceToolsPage />} />
        <Route path="/tools" element={<SpaceToolsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Status pill tests
// ---------------------------------------------------------------------------

describe("SpaceToolsPage — Adopted section status pills", () => {
  beforeEach(() => {
    mockUnadoptMutate.mockReset();
    mockUnadoptIsPending = false;
    mockSpacesResponse = {
      spaces: [{ id: "space-1", name: "Test Space", color: "#15803D", icon: null, task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 }, last_activity_at: null, autopilot: "disabled" }],
      totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
    };
  });

  it("shows PRISTINE pill for pristine tool", () => {
    mockSpaceTools = makeTools([makeAdopted({ status: "pristine" })]);
    renderPage();
    expect(screen.getByTestId("status-pill-pristine")).toBeInTheDocument();
    expect(screen.getByTestId("status-pill-pristine")).toHaveTextContent("pristine");
  });

  it("shows EDITED pill for edited tool", () => {
    mockSpaceTools = makeTools([makeAdopted({ status: "edited", name: "edited-agent" })]);
    renderPage();
    expect(screen.getByTestId("status-pill-edited")).toBeInTheDocument();
    expect(screen.getByTestId("status-pill-edited")).toHaveTextContent("edited");
  });

  it("shows EVOLVED pill for evolved tool", () => {
    mockSpaceTools = makeTools([makeAdopted({ status: "evolved", name: "evolved-agent", evolved: true })]);
    renderPage();
    expect(screen.getByTestId("status-pill-evolved")).toBeInTheDocument();
    expect(screen.getByTestId("status-pill-evolved")).toHaveTextContent("evolved");
  });

  it("renders all three pills when three adopted tools with different statuses exist", () => {
    mockSpaceTools = makeTools([
      makeAdopted({ name: "a1", status: "pristine" }),
      makeAdopted({ name: "a2", status: "edited" }),
      makeAdopted({ name: "a3", status: "evolved", evolved: true }),
    ]);
    renderPage();
    expect(screen.getByTestId("status-pill-pristine")).toBeInTheDocument();
    expect(screen.getByTestId("status-pill-edited")).toBeInTheDocument();
    expect(screen.getByTestId("status-pill-evolved")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Adopted section rendering
// ---------------------------------------------------------------------------

describe("SpaceToolsPage — Adopted section", () => {
  beforeEach(() => {
    mockUnadoptMutate.mockReset();
    mockUnadoptIsPending = false;
    mockSpacesResponse = {
      spaces: [{ id: "space-1", name: "Test Space", color: "#15803D", icon: null, task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 }, last_activity_at: null, autopilot: "disabled" }],
      totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
    };
  });

  it("does not render Adopted section when no tools adopted", () => {
    mockSpaceTools = makeTools([]);
    renderPage();
    // The section header "Adopted" would be present if any tools adopted
    expect(screen.queryByRole("button", { name: /unadopt/i })).not.toBeInTheDocument();
  });

  it("renders tool name and kind badge in adopted section", () => {
    mockSpaceTools = makeTools([makeAdopted({ kind: "agent", name: "my-agent" })]);
    renderPage();
    expect(screen.getByText("my-agent")).toBeInTheDocument();
    expect(screen.getByText("agent")).toBeInTheDocument();
  });

  it("renders source sha link", () => {
    mockSpaceTools = makeTools([makeAdopted({ source_sha: "deadbeef1234567890ab" })]);
    renderPage();
    // Short SHA (7 chars)
    expect(screen.getByText("deadbee")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /deadbee/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("deadbeef1234567890ab"));
  });

  it("source link strips .git suffix from source_url", () => {
    mockSpaceTools = makeTools([
      makeAdopted({ source_url: "https://github.com/org/repo.git", source_sha: "abc1234" }),
    ]);
    renderPage();
    const link = screen.getByRole("link", { name: /abc1234/i });
    expect(link.getAttribute("href")).not.toContain(".git/tree");
    expect(link.getAttribute("href")).toContain("github.com/org/repo/tree/abc1234");
  });
});

// ---------------------------------------------------------------------------
// Unadopt confirm dialog
// ---------------------------------------------------------------------------

describe("SpaceToolsPage — Unadopt confirm dialog", () => {
  beforeEach(() => {
    mockUnadoptMutate.mockReset();
    mockUnadoptIsPending = false;
    mockSpaceTools = makeTools([makeAdopted({ kind: "agent", name: "my-agent" })]);
    mockSpacesResponse = {
      spaces: [{ id: "space-1", name: "Test Space", color: "#15803D", icon: null, task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 }, last_activity_at: null, autopilot: "disabled" }],
      totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
    };
  });

  it("renders Unadopt button in adopted section", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /unadopt my-agent/i })).toBeInTheDocument();
  });

  it("shows confirm dialog when Unadopt clicked", () => {
    renderPage();
    const btn = screen.getByRole("button", { name: /unadopt my-agent/i });
    fireEvent.click(btn);
    expect(screen.getByText(/Remove\?/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /yes, remove/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("calls unadopt mutation on confirm", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /unadopt my-agent/i }));
    fireEvent.click(screen.getByRole("button", { name: /yes, remove/i }));
    expect(mockUnadoptMutate).toHaveBeenCalledWith(
      { kind: "agent", name: "my-agent" },
      expect.any(Object),
    );
  });

  it("dismisses confirm dialog on cancel without calling mutation", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /unadopt my-agent/i }));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(mockUnadoptMutate).not.toHaveBeenCalled();
    // Dialog should be gone
    expect(screen.queryByText(/Remove\?/i)).not.toBeInTheDocument();
  });

  it("shows Unadopt button again after cancel", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /unadopt my-agent/i }));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.getByRole("button", { name: /unadopt my-agent/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Plugins tab (R5)
// ---------------------------------------------------------------------------

describe("SpaceToolsPage — Plugins tab", () => {
  beforeEach(() => {
    mockUnadoptMutate.mockReset();
    mockUnadoptIsPending = false;
    mockSpaceTools = makeTools([]);
    mockSpacesResponse = {
      spaces: [{ id: "space-1", name: "Test Space", color: "#15803D", icon: null, task_counts: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 }, last_activity_at: null, autopilot: "disabled" }],
      totals: { backlog: 0, active: 0, waiting: 0, done: 0, archived: 0 },
    };
  });

  it("renders a Plugins tab button in the tab switcher", () => {
    renderPage();
    expect(screen.getByRole("tab", { name: /plugins/i })).toBeInTheDocument();
  });

  it("mounts PluginsPanel when the Plugins tab is selected", () => {
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: /plugins/i }));
    expect(screen.getByTestId("plugins-panel")).toBeInTheDocument();
  });

  it("does not render PluginsPanel when a different tab is active", () => {
    renderPage();
    // Default tab is 'installed', not 'plugins'
    expect(screen.queryByTestId("plugins-panel")).not.toBeInTheDocument();
  });

  it("hides the space selector when the Plugins tab is active", () => {
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: /plugins/i }));
    // The select element for choosing a space should not be present
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("shows the space selector on the Installed tab but not on the Plugins tab", () => {
    renderPage();
    // Installed tab (default): selector present
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    // Switch to Plugins tab: selector gone
    fireEvent.click(screen.getByRole("tab", { name: /plugins/i }));
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
