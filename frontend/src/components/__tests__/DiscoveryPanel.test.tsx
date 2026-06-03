import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DiscoveredTool, ToolSource } from "../../types";

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

let mockSources: ToolSource[] = [];
let mockTools: DiscoveredTool[] = [];
let sourcesLoading = false;
let toolsLoading = false;
const mockRefreshMutate = vi.fn();
let mockRefreshIsPending = false;
let mockRefreshIsError = false;
const mockAdoptMutate = vi.fn();
let mockAdoptIsPending = false;

vi.mock("../../hooks/useSpaces", () => ({
  useDiscoverySources: () => ({
    data: mockSources,
    isLoading: sourcesLoading,
  }),
  useDiscoveryTools: () => ({
    data: mockTools,
    isLoading: toolsLoading,
  }),
  useDiscoveryRefresh: () => ({
    mutate: mockRefreshMutate,
    isPending: mockRefreshIsPending,
    isError: mockRefreshIsError,
    error: mockRefreshIsError ? new Error("Network error") : null,
  }),
  useAdoptTool: () => ({
    mutate: mockAdoptMutate,
    isPending: mockAdoptIsPending,
  }),
}));

// Import AFTER vi.mock
import { DiscoveryPanel } from "../DiscoveryPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSource(overrides: Partial<ToolSource> = {}): ToolSource {
  return {
    url: "https://github.com/example/repo",
    branch: null,
    enabled: true,
    label: "Example Repo",
    ...overrides,
  };
}

function makeTool(overrides: Partial<DiscoveredTool> = {}): DiscoveredTool {
  return {
    source_url: "https://github.com/example/repo",
    source_slug: "github.com-example-repo",
    kind: "agent",
    name: "test-agent",
    relative_path: ".claude/agents/test-agent.md",
    description: "A test agent",
    source_sha: "abc123",
    ...overrides,
  };
}

function renderPanel(props: { spaceId?: string | null; adoptedKeys?: Set<string> } = {}) {
  return render(<DiscoveryPanel {...props} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DiscoveryPanel — empty state (no sources)", () => {
  beforeEach(() => {
    mockSources = [];
    mockTools = [];
    sourcesLoading = false;
    toolsLoading = false;
    mockRefreshIsPending = false;
    mockRefreshIsError = false;
    mockRefreshMutate.mockReset();
    mockAdoptMutate.mockReset();
  });

  it("renders empty state when no sources configured", () => {
    renderPanel();
    expect(screen.getByText(/No tool sources configured/i)).toBeInTheDocument();
    expect(screen.getByText(/\/data\/tool_sources\.yml/i)).toBeInTheDocument();
  });

  it("does not render Sources section or filters in empty state", () => {
    renderPanel();
    expect(screen.queryByText(/^Sources$/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});

describe("DiscoveryPanel — sources list", () => {
  beforeEach(() => {
    mockSources = [
      makeSource({ label: "My Repo", url: "https://github.com/org/my-repo" }),
      makeSource({ label: null, url: "https://github.com/org/another-repo", branch: "dev", enabled: false }),
    ];
    mockTools = [];
    sourcesLoading = false;
    toolsLoading = false;
    mockRefreshIsPending = false;
    mockRefreshIsError = false;
    mockRefreshMutate.mockReset();
    mockAdoptMutate.mockReset();
  });

  it("renders source labels", () => {
    renderPanel();
    expect(screen.getByText("My Repo")).toBeInTheDocument();
    expect(screen.getByText("github.com/org/another-repo")).toBeInTheDocument();
  });

  it("shows branch badge when set", () => {
    renderPanel();
    expect(screen.getByText("dev")).toBeInTheDocument();
  });

  it("shows 'disabled' badge for disabled sources", () => {
    renderPanel();
    expect(screen.getByText("disabled")).toBeInTheDocument();
  });

  it("renders Refresh buttons for each source", () => {
    renderPanel();
    const buttons = screen.getAllByRole("button", { name: /refresh/i });
    expect(buttons).toHaveLength(2);
  });

  it("calls refresh mutation when Refresh clicked", async () => {
    renderPanel();
    const [btn] = screen.getAllByRole("button", { name: /refresh/i });
    await userEvent.click(btn);
    expect(mockRefreshMutate).toHaveBeenCalledTimes(1);
  });

  it("disables all Refresh buttons while refreshing", () => {
    mockRefreshIsPending = true;
    renderPanel();
    const buttons = screen.getAllByRole("button", { name: /refreshing/i });
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });
});

describe("DiscoveryPanel — grouped tools", () => {
  beforeEach(() => {
    mockSources = [makeSource()];
    mockTools = [
      makeTool({ kind: "agent", name: "alpha-agent", source_slug: "repo-a" }),
      makeTool({ kind: "agent", name: "beta-agent", source_slug: "repo-b" }),
      makeTool({ kind: "skill", name: "cool-skill", description: "Does cool stuff" }),
      makeTool({ kind: "command", name: "my-command", description: null }),
    ];
    sourcesLoading = false;
    toolsLoading = false;
    mockRefreshIsPending = false;
    mockRefreshIsError = false;
    mockRefreshMutate.mockReset();
    mockAdoptMutate.mockReset();
  });

  it("renders all tools", () => {
    renderPanel();
    expect(screen.getByText("alpha-agent")).toBeInTheDocument();
    expect(screen.getByText("beta-agent")).toBeInTheDocument();
    expect(screen.getByText("cool-skill")).toBeInTheDocument();
    expect(screen.getByText("my-command")).toBeInTheDocument();
  });

  it("renders group headings for present kinds", () => {
    renderPanel();
    // Use getAllByText since the kind filter <select> also has matching <option> text
    expect(screen.getAllByText("Agents").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Skills").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Commands").length).toBeGreaterThanOrEqual(1);
    // Hooks group heading should not appear (no hook tools in this set)
    expect(
      screen.queryByRole("heading", { name: /^Hooks$/i }),
    ).not.toBeInTheDocument();
  });

  it("shows source_slug badge on each card", () => {
    renderPanel();
    expect(screen.getByText("repo-a")).toBeInTheDocument();
    expect(screen.getByText("repo-b")).toBeInTheDocument();
  });

  it("shows description when present", () => {
    renderPanel();
    expect(screen.getByText("Does cool stuff")).toBeInTheDocument();
  });

  it("shows 'No description' for tools without description", () => {
    renderPanel();
    const noDesc = screen.getAllByText(/No description/i);
    expect(noDesc.length).toBeGreaterThan(0);
  });
});

describe("DiscoveryPanel — filter by kind", () => {
  beforeEach(() => {
    mockSources = [makeSource()];
    mockTools = [
      makeTool({ kind: "agent", name: "agent-one" }),
      makeTool({ kind: "skill", name: "skill-one" }),
      makeTool({ kind: "command", name: "cmd-one" }),
    ];
    sourcesLoading = false;
    toolsLoading = false;
    mockRefreshIsPending = false;
    mockRefreshIsError = false;
  });

  it("shows all tools when kind is 'all'", () => {
    renderPanel();
    expect(screen.getByText("agent-one")).toBeInTheDocument();
    expect(screen.getByText("skill-one")).toBeInTheDocument();
    expect(screen.getByText("cmd-one")).toBeInTheDocument();
  });

  it("filters to agents only when kind filter set to agent", async () => {
    renderPanel();
    const select = screen.getByRole("combobox", { name: /filter by kind/i });
    await userEvent.selectOptions(select, "agent");
    expect(screen.getByText("agent-one")).toBeInTheDocument();
    expect(screen.queryByText("skill-one")).not.toBeInTheDocument();
    expect(screen.queryByText("cmd-one")).not.toBeInTheDocument();
  });

  it("filters to skills only when kind filter set to skill", async () => {
    renderPanel();
    const select = screen.getByRole("combobox", { name: /filter by kind/i });
    await userEvent.selectOptions(select, "skill");
    expect(screen.getByText("skill-one")).toBeInTheDocument();
    expect(screen.queryByText("agent-one")).not.toBeInTheDocument();
    expect(screen.queryByText("cmd-one")).not.toBeInTheDocument();
  });

  it("shows no-results state when filter matches nothing", async () => {
    renderPanel();
    const select = screen.getByRole("combobox", { name: /filter by kind/i });
    await userEvent.selectOptions(select, "hook");
    expect(screen.getByText(/No matching tools/i)).toBeInTheDocument();
  });
});

describe("DiscoveryPanel — free-text search", () => {
  beforeEach(() => {
    mockSources = [makeSource()];
    mockTools = [
      makeTool({ name: "awesome-agent", description: "Does awesome things" }),
      makeTool({ kind: "skill", name: "boring-skill", description: null }),
    ];
    sourcesLoading = false;
    toolsLoading = false;
    mockRefreshIsPending = false;
    mockRefreshIsError = false;
  });

  it("narrows results by name match", async () => {
    renderPanel();
    const input = screen.getByRole("searchbox", { name: /search tools/i });
    await userEvent.type(input, "awesome");
    expect(screen.getByText("awesome-agent")).toBeInTheDocument();
    expect(screen.queryByText("boring-skill")).not.toBeInTheDocument();
  });

  it("narrows results by description match", async () => {
    renderPanel();
    const input = screen.getByRole("searchbox", { name: /search tools/i });
    await userEvent.type(input, "awesome things");
    expect(screen.getByText("awesome-agent")).toBeInTheDocument();
    expect(screen.queryByText("boring-skill")).not.toBeInTheDocument();
  });

  it("shows no-results state when search matches nothing", async () => {
    renderPanel();
    const input = screen.getByRole("searchbox", { name: /search tools/i });
    await userEvent.type(input, "zzznomatch");
    expect(screen.getByText(/No matching tools/i)).toBeInTheDocument();
  });

  it("shows all tools when search is cleared", async () => {
    renderPanel();
    const input = screen.getByRole("searchbox", { name: /search tools/i });
    await userEvent.type(input, "awesome");
    expect(screen.queryByText("boring-skill")).not.toBeInTheDocument();
    await userEvent.clear(input);
    expect(screen.getByText("boring-skill")).toBeInTheDocument();
  });
});

describe("DiscoveryPanel — no tools discovered yet", () => {
  beforeEach(() => {
    mockSources = [makeSource()];
    mockTools = [];
    sourcesLoading = false;
    toolsLoading = false;
    mockRefreshIsPending = false;
    mockRefreshIsError = false;
  });

  it("shows 'no tools discovered' message when index is empty", () => {
    renderPanel();
    expect(screen.getByText(/No tools discovered yet/i)).toBeInTheDocument();
  });
});

describe("DiscoveryPanel — refresh mutation", () => {
  beforeEach(() => {
    mockSources = [makeSource()];
    mockTools = [];
    sourcesLoading = false;
    toolsLoading = false;
    mockRefreshIsPending = false;
    mockRefreshIsError = false;
    mockRefreshMutate.mockReset();
    mockAdoptMutate.mockReset();
  });

  it("shows error message when refresh fails", () => {
    mockRefreshIsError = true;
    renderPanel();
    expect(screen.getByText(/Refresh failed/i)).toBeInTheDocument();
    expect(screen.getByText(/Network error/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Adopt button behaviour
// ---------------------------------------------------------------------------

describe("DiscoveryPanel — Adopt button", () => {
  beforeEach(() => {
    mockSources = [makeSource()];
    mockTools = [
      makeTool({ kind: "agent", name: "my-agent" }),
      makeTool({ kind: "skill", name: "my-skill" }),
    ];
    sourcesLoading = false;
    toolsLoading = false;
    mockRefreshIsPending = false;
    mockRefreshIsError = false;
    mockRefreshMutate.mockReset();
    mockAdoptMutate.mockReset();
    mockAdoptIsPending = false;
  });

  it("renders Adopt button on each tool card", () => {
    renderPanel({ spaceId: "space-1" });
    const adoptBtns = screen.getAllByRole("button", { name: /adopt/i });
    // 2 adopt buttons (one per tool)
    expect(adoptBtns.length).toBeGreaterThanOrEqual(2);
  });

  it("Adopt button is disabled when no spaceId provided", () => {
    renderPanel({ spaceId: null });
    const adoptBtns = screen.getAllByRole("button", { name: /adopt my-agent/i });
    expect(adoptBtns[0]).toBeDisabled();
  });

  it("Adopt button shows 'Adopted' and is disabled when tool is already adopted", () => {
    renderPanel({
      spaceId: "space-1",
      adoptedKeys: new Set(["agent:my-agent"]),
    });
    const adoptedBtn = screen.getByRole("button", { name: /my-agent already adopted/i });
    expect(adoptedBtn).toBeDisabled();
    expect(adoptedBtn).toHaveTextContent("Adopted");
  });

  it("Adopt button is enabled for non-adopted tool when spaceId is set", () => {
    renderPanel({ spaceId: "space-1", adoptedKeys: new Set(["agent:my-agent"]) });
    // my-skill is NOT adopted — button should be enabled
    const skillBtn = screen.getByRole("button", { name: /adopt my-skill/i });
    expect(skillBtn).not.toBeDisabled();
  });

  it("calls adopt mutation with correct args when Adopt clicked", async () => {
    renderPanel({ spaceId: "space-1" });
    const btn = screen.getByRole("button", { name: /adopt my-agent/i });
    await userEvent.click(btn);
    expect(mockAdoptMutate).toHaveBeenCalledWith(
      { source_slug: "github.com-example-repo", kind: "agent", name: "my-agent" },
      expect.any(Object),
    );
  });

  it("shows hint banner when no space is selected", () => {
    renderPanel({ spaceId: null });
    expect(screen.getByText(/Select a space.*to enable Adopt/i)).toBeInTheDocument();
  });

  it("does not show hint banner when space is selected", () => {
    renderPanel({ spaceId: "space-1" });
    expect(screen.queryByText(/Select a space.*to enable Adopt/i)).not.toBeInTheDocument();
  });
});
