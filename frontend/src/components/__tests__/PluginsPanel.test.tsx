import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PluginsResponse } from "../../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockInstallMutate = vi.fn();
const mockUninstallMutate = vi.fn();
const mockEnableMutate = vi.fn();
const mockDisableMutate = vi.fn();
const mockAddMutate = vi.fn();
const mockRemoveMutate = vi.fn();

let mockData: PluginsResponse | undefined = undefined;
let mockLoading = false;

vi.mock("../../hooks/usePlugins", () => ({
  usePlugins: () => ({ data: mockData, isLoading: mockLoading }),
  useInstallPlugin: () => ({ mutate: mockInstallMutate, isPending: false }),
  useUninstallPlugin: () => ({ mutate: mockUninstallMutate, isPending: false }),
  useEnablePlugin: () => ({ mutate: mockEnableMutate, isPending: false }),
  useDisablePlugin: () => ({ mutate: mockDisableMutate, isPending: false }),
  useAddMarketplace: () => ({ mutate: mockAddMutate, isPending: false }),
  useRemoveMarketplace: () => ({ mutate: mockRemoveMutate, isPending: false }),
}));

import { PluginsPanel } from "../PluginsPanel";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const INSTALLED_PLUGIN = {
  id: "plugin-1",
  name: "My Plugin",
  marketplace: "core",
  version: "1.2.0",
  scope: "user" as const,
  enabled: true,
  components: [
    { name: "my-agent", kind: "agent" as const },
    { name: "my-skill", kind: "skill" as const },
    { name: "my-cmd", kind: "command" as const },
  ],
};

const DISABLED_PLUGIN = {
  id: "plugin-2",
  name: "Disabled Plugin",
  marketplace: null,
  version: null,
  scope: "user" as const,
  enabled: false,
  components: [],
};

const AVAILABLE_PLUGIN = {
  pluginId: "avail-1",
  name: "Available Plugin",
  description: "A great plugin",
  marketplaceName: "core",
  source: "https://example.com/plugin",
  installCount: 42,
};

const MARKETPLACE = { name: "core", source: "https://marketplace.example.com" };

function resp(overrides: Partial<PluginsResponse> = {}): PluginsResponse {
  return { installed: [], available: [], marketplaces: [], ...overrides };
}

function renderPanel() {
  return render(<PluginsPanel />);
}

beforeEach(() => {
  mockData = undefined;
  mockLoading = false;
  vi.spyOn(window, "confirm").mockReturnValue(true);
  mockInstallMutate.mockReset();
  mockUninstallMutate.mockReset();
  mockEnableMutate.mockReset();
  mockDisableMutate.mockReset();
  mockAddMutate.mockReset();
  mockRemoveMutate.mockReset();
});

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------

it("shows loading indicator while data is loading", () => {
  mockLoading = true;
  renderPanel();
  expect(screen.getByText(/loading plugins/i)).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Empty states — all three sections
// ---------------------------------------------------------------------------

describe("empty states", () => {
  beforeEach(() => { mockData = resp(); });

  it("renders all three section headers", () => {
    renderPanel();
    expect(screen.getByText("Installed")).toBeInTheDocument();
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByText("Marketplaces")).toBeInTheDocument();
  });

  it("shows empty-state message for each empty section", () => {
    renderPanel();
    expect(screen.getByText(/no plugins installed/i)).toBeInTheDocument();
    expect(screen.getByText(/no plugins available/i)).toBeInTheDocument();
    expect(screen.getByText(/no marketplaces configured/i)).toBeInTheDocument();
  });

  it("renders Add marketplace form even when marketplace list is empty", () => {
    renderPanel();
    expect(screen.getByPlaceholderText(/marketplace.example.com/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^add$/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Installed section
// ---------------------------------------------------------------------------

describe("installed section — populated", () => {
  beforeEach(() => {
    mockData = resp({ installed: [INSTALLED_PLUGIN, DISABLED_PLUGIN] });
  });

  it("renders plugin names and version badge", () => {
    renderPanel();
    expect(screen.getByText("My Plugin")).toBeInTheDocument();
    expect(screen.getByText("Disabled Plugin")).toBeInTheDocument();
    expect(screen.getByText("v1.2.0")).toBeInTheDocument();
  });

  it("shows 'Enabled' state and 'Disabled' state for respective plugins", () => {
    renderPanel();
    // aria-label buttons: "Disable My Plugin" and "Enable Disabled Plugin"
    expect(screen.getByRole("button", { name: /disable my plugin/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /enable disabled plugin/i })).toBeInTheDocument();
  });

  it("calls useDisablePlugin when clicking toggle on enabled plugin", async () => {
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /disable my plugin/i }));
    expect(mockDisableMutate).toHaveBeenCalledWith("plugin-1");
    expect(mockEnableMutate).not.toHaveBeenCalled();
  });

  it("calls useEnablePlugin when clicking toggle on disabled plugin", async () => {
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /enable disabled plugin/i }));
    expect(mockEnableMutate).toHaveBeenCalledWith("plugin-2");
    expect(mockDisableMutate).not.toHaveBeenCalled();
  });

  it("renders Uninstall button for each installed plugin", () => {
    renderPanel();
    expect(screen.getAllByRole("button", { name: /uninstall/i })).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// Uninstall confirmation gate
// ---------------------------------------------------------------------------

describe("uninstall confirmation", () => {
  beforeEach(() => { mockData = resp({ installed: [INSTALLED_PLUGIN] }); });

  it("calls window.confirm before uninstalling", async () => {
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /uninstall my plugin/i }));
    expect(window.confirm).toHaveBeenCalled();
  });

  it("calls useUninstallPlugin when confirm returns true", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /uninstall my plugin/i }));
    expect(mockUninstallMutate).toHaveBeenCalledWith("plugin-1");
  });

  it("does NOT call useUninstallPlugin when confirm returns false", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /uninstall my plugin/i }));
    expect(mockUninstallMutate).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Component list — expand with icons
// ---------------------------------------------------------------------------

describe("component list expand with icons", () => {
  beforeEach(() => { mockData = resp({ installed: [INSTALLED_PLUGIN] }); });

  it("component list is collapsed by default (items not visible)", () => {
    renderPanel();
    expect(screen.queryByText("my-agent")).not.toBeInTheDocument();
  });

  it("expands and shows all components when toggle clicked", async () => {
    renderPanel();
    await userEvent.click(
      screen.getByRole("button", { name: /expand components for my plugin/i }),
    );
    expect(screen.getByText("my-agent")).toBeInTheDocument();
    expect(screen.getByText("my-skill")).toBeInTheDocument();
    expect(screen.getByText("my-cmd")).toBeInTheDocument();
  });

  it("shows correct icons for agent (🤖), skill (⚡), command (⌘)", async () => {
    renderPanel();
    await userEvent.click(
      screen.getByRole("button", { name: /expand components for my plugin/i }),
    );
    const items = screen.getAllByRole("listitem");
    const get = (name: string) => items.find((li) => li.textContent?.includes(name));
    expect(get("my-agent")?.textContent).toContain("🤖");
    expect(get("my-skill")?.textContent).toContain("⚡");
    expect(get("my-cmd")?.textContent).toContain("⌘");
  });

  it("collapses list again on second click", async () => {
    renderPanel();
    const toggle = screen.getByRole("button", { name: /expand components for my plugin/i });
    await userEvent.click(toggle);
    await userEvent.click(toggle);
    expect(screen.queryByText("my-agent")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Available section
// ---------------------------------------------------------------------------

describe("available section", () => {
  beforeEach(() => { mockData = resp({ available: [AVAILABLE_PLUGIN] }); });

  it("renders available plugin name and description", () => {
    renderPanel();
    expect(screen.getByText("Available Plugin")).toBeInTheDocument();
    expect(screen.getByText("A great plugin")).toBeInTheDocument();
  });

  it("calls useInstallPlugin with pluginId when Install clicked", async () => {
    renderPanel();
    await userEvent.click(
      screen.getByRole("button", { name: /install available plugin/i }),
    );
    expect(mockInstallMutate).toHaveBeenCalledWith({ pluginId: "avail-1" });
  });
});

// ---------------------------------------------------------------------------
// Marketplaces section — add + remove
// ---------------------------------------------------------------------------

describe("marketplaces section", () => {
  beforeEach(() => { mockData = resp({ marketplaces: [MARKETPLACE] }); });

  it("renders marketplace name and source URL", () => {
    renderPanel();
    expect(screen.getByText("core")).toBeInTheDocument();
    expect(screen.getByText("https://marketplace.example.com")).toBeInTheDocument();
  });

  it("calls useRemoveMarketplace with name when Remove clicked", async () => {
    renderPanel();
    await userEvent.click(
      screen.getByRole("button", { name: /remove marketplace core/i }),
    );
    expect(mockRemoveMutate).toHaveBeenCalledWith("core");
  });

  it("calls useAddMarketplace with source URL when form submitted", async () => {
    mockAddMutate.mockImplementation((_url: string, opts?: { onSuccess?: () => void }) => {
      opts?.onSuccess?.();
    });
    renderPanel();
    await userEvent.type(
      screen.getByPlaceholderText(/marketplace.example.com/i),
      "https://new.marketplace.com",
    );
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    expect(mockAddMutate).toHaveBeenCalledWith(
      "https://new.marketplace.com",
      expect.any(Object),
    );
  });

  it("clears URL input after successful add", async () => {
    mockAddMutate.mockImplementation((_url: string, opts?: { onSuccess?: () => void }) => {
      opts?.onSuccess?.();
    });
    renderPanel();
    const input = screen.getByPlaceholderText(/marketplace.example.com/i);
    await userEvent.type(input, "https://new.marketplace.com");
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    expect(input).toHaveValue("");
  });
});

// ---------------------------------------------------------------------------
// Section count badges
// ---------------------------------------------------------------------------

it("section headers show count badges padded to 2 chars", () => {
  mockData = resp({
    installed: [INSTALLED_PLUGIN],
    available: [AVAILABLE_PLUGIN],
    marketplaces: [MARKETPLACE],
  });
  renderPanel();
  const badges = screen.getAllByText("01");
  expect(badges).toHaveLength(3);
});
